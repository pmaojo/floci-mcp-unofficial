import asyncio
import json
import os
from typing import Dict, Any, List
from floci_backend.config import config
from floci_backend.infrastructure.aws_cli import AwsCli

class EksService:
    def __init__(self, aws_cli: AwsCli):
        self.aws_cli = aws_cli

    async def get_overview(self) -> Dict[str, Any]:
        list_response = await self.aws_cli.run_json(['eks', 'list-clusters'])
        cluster_names = list_response.get('clusters', [])

        clusters = await asyncio.gather(*(self._describe_cluster(name) for name in cluster_names))
        kubernetes = await self._list_kubernetes_pods()

        return {
            'endpointUrl': config.aws_endpoint_url,
            'region': config.aws_region,
            'clusters': list(clusters),
            'kubernetes': kubernetes,
        }

    async def _describe_cluster(self, name: str) -> Dict[str, Any]:
        description_task = self.aws_cli.run_json(['eks', 'describe-cluster', '--name', name])
        fargate_profiles_task = self._list_fargate_profiles(name)

        description, fargate_profiles = await asyncio.gather(description_task, fargate_profiles_task)
        cluster = description.get('cluster', {'name': name})

        vpc_config = cluster.get('resourcesVpcConfig', {})

        return {
            'name': cluster.get('name', name),
            'arn': cluster.get('arn'),
            'createdAt': cluster.get('createdAt'),
            'version': cluster.get('version'),
            'endpoint': cluster.get('endpoint'),
            'roleArn': cluster.get('roleArn'),
            'status': cluster.get('status'),
            'platformVersion': cluster.get('platformVersion'),
            'vpcId': vpc_config.get('vpcId'),
            'subnetIds': vpc_config.get('subnetIds', []),
            'securityGroupIds': vpc_config.get('securityGroupIds', []),
            'fargateProfiles': fargate_profiles,
        }

    async def _list_fargate_profiles(self, cluster_name: str) -> List[str]:
        try:
            response = await self.aws_cli.run_json([
                'eks', 'list-fargate-profiles', '--cluster-name', cluster_name
            ])
            return response.get('fargateProfileNames', [])
        except Exception:
            return []

    async def _list_kubernetes_pods(self) -> Dict[str, Any]:
        kubeconfig = os.environ.get('KUBECONFIG')

        if not kubeconfig:
            return {
                'available': False,
                'reason': 'KUBECONFIG is not configured in the sidecar container.',
                'pods': [],
            }

        try:
            env = os.environ.copy()
            env['KUBECONFIG'] = kubeconfig
            result = await self._run_process('kubectl', ['get', 'pods', '--all-namespaces', '-o', 'json'], env)
            payload = json.loads(result['stdout'] or '{}')

            pods = []
            for pod in payload.get('items', []):
                status = pod.get('status', {})
                metadata = pod.get('metadata', {})
                spec = pod.get('spec', {})
                container_statuses = status.get('containerStatuses', [])

                restarts = sum(c.get('restartCount', 0) for c in container_statuses)

                containers = [{
                    'name': c.get('name', ''),
                    'ready': bool(c.get('ready', False)),
                    'restarts': c.get('restartCount', 0),
                } for c in container_statuses]

                pods.append({
                    'name': metadata.get('name', ''),
                    'namespace': metadata.get('namespace', 'default'),
                    'status': status.get('phase', 'Unknown'),
                    'restarts': restarts,
                    'createdAt': metadata.get('creationTimestamp'),
                    'nodeName': spec.get('nodeName'),
                    'podIp': status.get('podIP'),
                    'containers': containers,
                })

            return {
                'available': True,
                'source': kubeconfig,
                'pods': pods,
            }
        except Exception as error:
            return {
                'available': False,
                'reason': str(error) or 'kubectl failed while reading pods.',
                'pods': [],
            }

    async def _run_process(self, command: str, args: List[str], env: Dict[str, str]) -> Dict[str, str]:
        process = await asyncio.create_subprocess_exec(
            command, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        stdout, stderr = await process.communicate()
        stdout_str = stdout.decode()
        stderr_str = stderr.decode()

        if process.returncode == 0:
            return {'stdout': stdout_str, 'stderr': stderr_str}

        message = stderr_str.strip() or stdout_str.strip() or f"{command} exited with {process.returncode}"
        raise Exception(message)
