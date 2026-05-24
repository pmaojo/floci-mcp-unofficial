import json
import os
import shutil
import tempfile
from typing import Dict, Any, List, Optional
from floci_backend.config import config
from floci_backend.infrastructure.aws_cli import AwsCli, AwsCliError
from floci_backend.infrastructure.lambda_package import prepare_lambda_package, get_runtime_templates

class LambdaService:
    def __init__(self, aws_cli: AwsCli):
        self.aws_cli = aws_cli

    async def get_capabilities(self) -> Dict[str, Any]:
        return {
            'endpointUrl': config.aws_endpoint_url,
            'defaultRegion': config.aws_region,
            'defaultRoleArn': config.default_lambda_role_arn,
            'runtimes': [
                {'value': 'nodejs18.x', 'label': 'Node.js 18.x', 'supportsTemplate': True},
                {'value': 'python3.9', 'label': 'Python 3.9', 'supportsTemplate': True},
                {'value': 'go1.x', 'label': 'Go 1.x', 'supportsTemplate': False},
                {'value': 'java11', 'label': 'Java 11', 'supportsTemplate': False},
                {'value': 'provided.al2', 'label': 'Custom Runtime (provided.al2)', 'supportsTemplate': False},
            ],
            'templates': get_runtime_templates(),
            'sourceModes': ['template', 'inline', 'files', 'zipBase64'],
        }

    async def list_functions(self) -> Dict[str, Any]:
        return await self.aws_cli.run_json(['lambda', 'list-functions'])

    async def create_function(self, request: Dict[str, Any]) -> Dict[str, Any]:
        self._assert_required(request.get('functionName'), 'functionName')
        self._assert_required(request.get('runtime'), 'runtime')
        self._assert_required(request.get('handler'), 'handler')

        deployment_package = prepare_lambda_package(request['runtime'], request.get('code', {}))
        try:
            args = [
                'lambda', 'create-function',
                '--function-name', request['functionName'],
                '--runtime', request['runtime'],
                '--handler', request['handler'],
                '--role', request.get('role', config.default_lambda_role_arn),
                '--zip-file', self._to_aws_file_uri(deployment_package.zip_path, True),
            ]
            self._push_optional(args, '--description', request.get('description'))
            self._push_optional(args, '--timeout', request.get('timeout'))
            self._push_optional(args, '--memory-size', request.get('memorySize'))

            return await self.aws_cli.run_json(args)
        finally:
            deployment_package.cleanup()

    async def update_function_code(self, function_name: str, request: Dict[str, Any]) -> Dict[str, Any]:
        self._assert_required(function_name, 'functionName')

        deployment_package = prepare_lambda_package(request.get('runtime', ''), request.get('code', {}))
        try:
            return await self.aws_cli.run_json([
                'lambda', 'update-function-code',
                '--function-name', function_name,
                '--zip-file', self._to_aws_file_uri(deployment_package.zip_path, True),
            ])
        finally:
            deployment_package.cleanup()

    async def update_function_configuration(self, function_name: str, request: Dict[str, Any]) -> Dict[str, Any]:
        self._assert_required(function_name, 'functionName')

        args = ['lambda', 'update-function-configuration', '--function-name', function_name]
        self._push_optional(args, '--runtime', request.get('runtime'))
        self._push_optional(args, '--handler', request.get('handler'))
        self._push_optional(args, '--role', request.get('role'))
        self._push_optional(args, '--description', request.get('description'))
        self._push_optional(args, '--timeout', request.get('timeout'))
        self._push_optional(args, '--memory-size', request.get('memorySize'))

        if request.get('environmentVariables'):
            variables = ','.join(f"{k}={v}" for k, v in request['environmentVariables'].items())
            args.extend(['--environment', f"Variables={{{variables}}}"])

        return await self.aws_cli.run_json(args)

    async def invoke_function(self, function_name: str, request: Dict[str, Any]) -> Dict[str, Any]:
        self._assert_required(function_name, 'functionName')

        working_directory = tempfile.mkdtemp(prefix='floci-lambda-invoke-')
        payload_path = os.path.join(working_directory, 'payload.json')
        response_path = os.path.join(working_directory, 'response.json')

        try:
            with open(payload_path, 'w', encoding='utf-8') as f:
                json.dump(request.get('payload', {}), f)

            args = [
                'lambda', 'invoke',
                '--function-name', function_name,
                '--payload', self._to_aws_file_uri(payload_path, False),
                '--cli-binary-format', 'raw-in-base64-out',
            ]
            self._push_optional(args, '--invocation-type', request.get('invocationType'))
            args.append(response_path)

            metadata = await self.aws_cli.run_json(args)

            try:
                with open(response_path, 'r', encoding='utf-8') as f:
                    raw_payload = f.read()
            except FileNotFoundError:
                raw_payload = ''

            return {
                'metadata': metadata,
                'payload': self._parse_json_or_text(raw_payload),
            }
        finally:
            shutil.rmtree(working_directory, ignore_errors=True)

    async def delete_function(self, function_name: str) -> Dict[str, Any]:
        self._assert_required(function_name, 'functionName')
        return await self.aws_cli.run_json(['lambda', 'delete-function', '--function-name', function_name])

    async def get_logs(self, function_name: str) -> Dict[str, Any]:
        self._assert_required(function_name, 'functionName')
        log_group_name = f"/aws/lambda/{function_name}"

        try:
            streams = await self.aws_cli.run_json([
                'logs', 'describe-log-streams',
                '--log-group-name', log_group_name,
                '--order-by', 'LastEventTime',
                '--descending',
                '--max-items', '5',
            ])

            events = []
            for stream in streams.get('logStreams', []):
                if not stream.get('logStreamName'):
                    continue
                response = await self.aws_cli.run_json([
                    'logs', 'get-log-events',
                    '--log-group-name', log_group_name,
                    '--log-stream-name', stream['logStreamName'],
                    '--limit', '50',
                ])
                events.extend(response.get('events', []))

            return {'logGroupName': log_group_name, 'events': events}
        except Exception as error:
            message = str(error)
            if isinstance(error, AwsCliError):
                message = error.stderr.strip() or str(error)
            return {'logGroupName': log_group_name, 'events': [], 'warning': message}

    def _assert_required(self, value: Any, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required")

    def _push_optional(self, args: List[str], key: str, value: Any) -> None:
        if value is None or value == '':
            return
        args.extend([key, str(value)])

    def _to_aws_file_uri(self, file_path: str, binary: bool) -> str:
        # Create file URI similar to pathToFileURL in node
        abs_path = os.path.abspath(file_path).replace('\\', '/')
        if not abs_path.startswith('/'):
            abs_path = '/' + abs_path
        uri = f"file://{abs_path}"
        return uri.replace('file://', 'fileb://') if binary else uri

    def _parse_json_or_text(self, value: str) -> Any:
        if not value.strip():
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
