from datetime import datetime
from typing import Dict, Any, List

from floci_backend.config import config
from floci_backend.infrastructure.aws_cli import AwsCli, AwsCliError
from floci_backend.application.aws_resource_catalog import AWS_RESOURCE_CATALOG
from floci_backend.application.compatibility_service import CompatibilityService

class AwsResourceService:
    def __init__(self, aws_cli: AwsCli, compatibility_service: CompatibilityService):
        self.aws_cli = aws_cli
        self.compatibility_service = compatibility_service

    def list_services(self) -> List[Dict[str, Any]]:
        return [
            {
                'key': key,
                'serviceName': service['serviceName'],
                'description': service['description'],
                'resources': [{'id': r['id'], 'label': r['label']} for r in service.get('resources', [])]
            }
            for key, service in AWS_RESOURCE_CATALOG.items()
        ]

    async def get_overview(self, service_key: str) -> Dict[str, Any]:
        service = AWS_RESOURCE_CATALOG.get(service_key)
        if not service:
            raise ValueError(f"Unknown AWS service key: {service_key}")

        # Check compat bypass
        if (len(service.get('resources', [])) == 0 or self.compatibility_service.should_bypass_native(service_key)) and self.compatibility_service.can_handle(service_key):
            compatibility_overview = await self.compatibility_service.get_overview(service_key)
            if compatibility_overview:
                return compatibility_overview

        resources = []
        for resource in service.get('resources', []):
            res = await self._read_resource(service_key, resource)
            resources.append(res)

        return {
            'serviceKey': service_key,
            'serviceName': service['serviceName'],
            'description': service['description'],
            'endpointUrl': config.aws_endpoint_url,
            'region': config.aws_region,
            'generatedAt': datetime.utcnow().isoformat() + "Z",
            'resources': resources,
        }

    async def _read_resource(self, service_key: str, resource: Dict[str, Any]) -> Dict[str, Any]:
        command = resource['command']
        cmd_str = ' '.join(['aws'] + command)
        try:
            payload = await self.aws_cli.run_json(command)
            extracted = self._get_path(payload, resource.get('resultPath'))
            items = self._normalize_items(extracted)

            return {
                'id': resource['id'],
                'label': resource['label'],
                'status': 'ok',
                'command': cmd_str,
                'count': len(items),
                'items': items,
                'payload': payload,
            }
        except Exception as error:
            message = self._format_aws_error(error)
            if self._is_unsupported_operation(message) and self.compatibility_service.can_handle_resource(service_key, resource['id']):
                compatibility_resource = await self.compatibility_service.get_resource(service_key, resource['id'])
                if compatibility_resource:
                    return compatibility_resource

            status = 'unsupported' if self._is_unsupported_operation(message) else 'error'
            return {
                'id': resource['id'],
                'label': resource['label'],
                'status': status,
                'command': cmd_str,
                'count': 0,
                'items': [],
                'error': message,
            }

    def _get_path(self, payload: Any, path: str) -> Any:
        if not path:
            return payload
        current = payload
        for segment in path.split('.'):
            if isinstance(current, dict) and segment in current:
                current = current[segment]
            else:
                return None
        return current

    def _normalize_items(self, value: Any) -> List[Any]:
        if isinstance(value, list):
            return value
        if value is None:
            return []
        return [value]

    def _format_aws_error(self, error: Exception) -> str:
        if isinstance(error, AwsCliError):
            return error.stderr.strip() or error.stdout.strip() or str(error)
        return str(error) or 'AWS CLI command failed'

    def _is_unsupported_operation(self, message: str) -> bool:
        normalized = message.lower()
        fragments = [
            'unknown operation',
            'unsupportedoperation',
            'is not supported',
            'invalidaction',
            'nosuchbucket',
            'invalidargument',
        ]
        return any(fragment in normalized for fragment in fragments)
