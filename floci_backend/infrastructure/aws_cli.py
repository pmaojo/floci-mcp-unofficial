import asyncio
import json
import os
from typing import Any, Dict, List
from floci_backend.config import config

class AwsCliError(Exception):
    def __init__(self, message: str, stdout: str, stderr: str, exit_code: int):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code

class AwsCli:
    async def run(self, args: List[str]) -> Dict[str, str]:
        final_args = self._with_endpoint(args)

        env = os.environ.copy()
        env['AWS_ACCESS_KEY_ID'] = config.aws_access_key_id
        env['AWS_SECRET_ACCESS_KEY'] = config.aws_secret_access_key
        env['AWS_DEFAULT_REGION'] = config.aws_region
        env['AWS_EC2_METADATA_DISABLED'] = 'true'

        process = await asyncio.create_subprocess_exec(
            'aws', *final_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        stdout, stderr = await process.communicate()
        stdout_str = stdout.decode()
        stderr_str = stderr.decode()

        if process.returncode == 0:
            return {'stdout': stdout_str, 'stderr': stderr_str}

        message = stderr_str.strip() or stdout_str.strip() or 'AWS CLI command failed'
        raise AwsCliError(message, stdout_str, stderr_str, process.returncode)

    async def run_json(self, args: List[str]) -> Any:
        result = await self.run([*args, '--output', 'json'])
        trimmed = result['stdout'].strip()
        if not trimmed:
            return {}
        return json.loads(trimmed)

    def _with_endpoint(self, args: List[str]) -> List[str]:
        if args and args[0] == '--version':
            return args
        return ['--endpoint-url', config.aws_endpoint_url, *args]
