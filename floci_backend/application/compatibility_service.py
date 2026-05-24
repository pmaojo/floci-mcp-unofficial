from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from floci_backend.config import config
from floci_backend.infrastructure.json_state_store import JsonStateStore
from floci_backend.application.recipe_service import RecipeService

class CodeArtifactDomain(BaseModel):
    name: str
    arn: str
    owner: str
    status: str
    createdTime: str

class CodeArtifactRepository(BaseModel):
    name: str
    arn: str
    domainName: str
    administratorAccount: str
    createdTime: str

class CodeArtifactState(BaseModel):
    domains: List[CodeArtifactDomain] = []
    repositories: List[CodeArtifactRepository] = []

class GenericCompatibilityRecord(BaseModel):
    id: str
    name: str
    arn: str
    status: str
    createdTime: str
    resourceType: Optional[str] = None

class GenericCompatibilityState(BaseModel):
    resources: Dict[str, List[GenericCompatibilityRecord]] = {}

ACCOUNT_ID = '000000000000'

GENERIC_COMPATIBILITY_CATALOG = {
    's3': {'serviceName': 'S3 Buckets', 'description': 'Compatibilidad local persistente para buckets S3.', 'resources': [{'id': 'buckets', 'label': 'Buckets'}]},
    'dynamodb': {'serviceName': 'DynamoDB', 'description': 'Compatibilidad local persistente para tablas DynamoDB.', 'resources': [{'id': 'tables', 'label': 'Tables'}, {'id': 'limits', 'label': 'Account limits'}]},
    'sts': {'serviceName': 'STS', 'description': 'Compatibilidad local persistente para STS.', 'resources': [{'id': 'caller-identity', 'label': 'Caller identity'}]},
    'ses': {'serviceName': 'SES Sink', 'description': 'Compatibilidad local persistente para SES.', 'resources': [{'id': 'identities', 'label': 'Identities'}, {'id': 'send-statistics', 'label': 'Send statistics'}, {'id': 'v2-identities', 'label': 'SES v2 identities'}, {'id': 'v2-templates', 'label': 'SES v2 templates'}]},
    'ec2': {'serviceName': 'EC2 Inventory', 'description': 'Compatibilidad local persistente para inventario EC2.', 'resources': [{'id': 'instances', 'label': 'Instances'}, {'id': 'vpcs', 'label': 'VPCs'}, {'id': 'subnets', 'label': 'Subnets'}, {'id': 'security-groups', 'label': 'Security groups'}, {'id': 'key-pairs', 'label': 'Key pairs'}]},
    'apigateway': {'serviceName': 'API Gateway', 'description': 'Compatibilidad local persistente para APIs.', 'resources': [{'id': 'rest-apis', 'label': 'REST APIs'}, {'id': 'v2-apis', 'label': 'HTTP/WebSocket APIs'}]},
    'route53': {'serviceName': 'Route 53', 'description': 'Compatibilidad local persistente para Route 53.', 'resources': [{'id': 'hosted-zones', 'label': 'Hosted zones'}, {'id': 'resolver-rules', 'label': 'Resolver rules'}]},
    'stepfunctions': {'serviceName': 'Step Functions', 'description': 'Compatibilidad local persistente para Step Functions.', 'resources': [{'id': 'state-machines', 'label': 'State machines'}, {'id': 'activities', 'label': 'Activities'}]},
    'cognito': {'serviceName': 'Cognito', 'description': 'Compatibilidad local persistente para Cognito.', 'resources': [{'id': 'user-pools', 'label': 'User pools'}, {'id': 'identity-pools', 'label': 'Identity pools'}]},
    'athena': {'serviceName': 'Athena', 'description': 'Compatibilidad local persistente para Athena.', 'resources': [{'id': 'workgroups', 'label': 'Workgroups'}, {'id': 'catalogs', 'label': 'Data catalogs'}, {'id': 'queries', 'label': 'Query executions'}]},
    'cloudfront': {'serviceName': 'CloudFront', 'description': 'Compatibilidad local persistente para CloudFront.', 'resources': [{'id': 'distributions', 'label': 'Distributions'}, {'id': 'functions', 'label': 'Functions'}]},
    'cloudwatchmetrics': {'serviceName': 'CloudWatch Metrics', 'description': 'Compatibilidad local persistente para CloudWatch.', 'resources': [{'id': 'metrics', 'label': 'Metrics'}, {'id': 'alarms', 'label': 'Alarms'}]},
    'scheduler': {'serviceName': 'EventBridge Scheduler', 'description': 'Compatibilidad local persistente para EventBridge Scheduler.', 'resources': [{'id': 'schedule-groups', 'label': 'Schedule groups'}, {'id': 'schedules', 'label': 'Schedules'}]},
    'firehose': {'serviceName': 'Data Firehose', 'description': 'Compatibilidad local persistente para Firehose.', 'resources': [{'id': 'delivery-streams', 'label': 'Delivery streams'}]},
    'appconfig': {'serviceName': 'AppConfig', 'description': 'Compatibilidad local persistente para AppConfig.', 'resources': [{'id': 'applications', 'label': 'Applications'}, {'id': 'deployment-strategies', 'label': 'Deployment strategies'}]},
    'appconfigdata': {'serviceName': 'AppConfig Data', 'description': 'Compatibilidad local persistente para AppConfig Data.', 'resources': [{'id': 'configuration-sessions', 'label': 'Configuration sessions'}]},
    'bedrockruntime': {'serviceName': 'Bedrock Runtime', 'description': 'Compatibilidad local persistente para Bedrock.', 'resources': [{'id': 'model-invocations', 'label': 'Model invocations'}]},
    'ssm': {'serviceName': 'SSM Parameters', 'description': 'Compatibilidad local persistente para SSM.', 'resources': [{'id': 'parameters', 'label': 'Parameters'}]},
    'codebuild': {'serviceName': 'CodeBuild', 'description': 'Compatibilidad local persistente para CodeBuild.', 'resources': [{'id': 'projects', 'label': 'Projects'}, {'id': 'builds', 'label': 'Builds'}]},
    'codepipeline': {'serviceName': 'CodePipeline', 'description': 'Compatibilidad local persistente para CodePipeline.', 'resources': [{'id': 'pipelines', 'label': 'Pipelines'}]},
    'codedeploy': {'serviceName': 'CodeDeploy', 'description': 'Compatibilidad local persistente para CodeDeploy.', 'resources': [{'id': 'applications', 'label': 'Applications'}, {'id': 'deployment-configs', 'label': 'Deployment configs'}, {'id': 'deployments', 'label': 'Deployments'}]},
    'appsync': {'serviceName': 'AppSync', 'description': 'Compatibilidad local persistente para AppSync.', 'resources': [{'id': 'graphql-apis', 'label': 'GraphQL APIs'}]},
    'marketplace': {'serviceName': 'Software Marketplace', 'description': 'Catalogo local persistente para marketplace.', 'resources': [{'id': 'ami-products', 'label': 'AMI products'}]},
    'roadmap': {'serviceName': 'Roadmap', 'description': 'Compatibilidad local persistente para Roadmap.', 'resources': [{'id': 'items', 'label': 'Roadmap items'}]},
    'redshift': {'serviceName': 'Redshift', 'description': 'Compatibilidad local persistente para Redshift.', 'resources': [{'id': 'clusters', 'label': 'Clusters'}]},
    'opensearch': {'serviceName': 'OpenSearch', 'description': 'Compatibilidad local persistente para OpenSearch.', 'resources': [{'id': 'domains', 'label': 'Domains'}]},
    'msk': {'serviceName': 'MSK', 'description': 'Compatibilidad local persistente para MSK.', 'resources': [{'id': 'clusters', 'label': 'Clusters'}]},
    'sagemaker': {'serviceName': 'SageMaker', 'description': 'Compatibilidad local persistente para SageMaker.', 'resources': [{'id': 'models', 'label': 'Models'}, {'id': 'endpoints', 'label': 'Endpoints'}]},
    'iotcore': {'serviceName': 'IoT Core', 'description': 'Compatibilidad local persistente para IoT Core.', 'resources': [{'id': 'things', 'label': 'Things'}]},
    'batch': {'serviceName': 'AWS Batch', 'description': 'Compatibilidad local persistente para AWS Batch.', 'resources': [{'id': 'job-queues', 'label': 'Job queues'}, {'id': 'compute-environments', 'label': 'Compute environments'}]},
    'autoscaling': {'serviceName': 'Auto Scaling', 'description': 'Compatibilidad local persistente para Auto Scaling.', 'resources': [{'id': 'auto-scaling-groups', 'label': 'Auto Scaling groups'}, {'id': 'launch-configurations', 'label': 'Launch configurations'}]},
    'transitgateway': {'serviceName': 'Transit Gateway', 'description': 'Compatibilidad local persistente para Transit Gateway.', 'resources': [{'id': 'transit-gateways', 'label': 'Transit gateways'}]},
    'beanstalk': {'serviceName': 'Elastic Beanstalk', 'description': 'Compatibilidad local persistente para Elastic Beanstalk.', 'resources': [{'id': 'applications', 'label': 'Applications'}, {'id': 'environments', 'label': 'Environments'}]},
    'efs': {'serviceName': 'EFS', 'description': 'Compatibilidad local persistente para EFS.', 'resources': [{'id': 'file-systems', 'label': 'File systems'}]},
    'neptune': {'serviceName': 'Neptune', 'description': 'Compatibilidad local persistente para Neptune.', 'resources': [{'id': 'clusters', 'label': 'DB clusters'}]},
    'cloudtrail': {'serviceName': 'CloudTrail', 'description': 'Compatibilidad local persistente para CloudTrail.', 'resources': [{'id': 'trails', 'label': 'Trails'}, {'id': 'events', 'label': 'Events'}]},
    'identitycenter': {'serviceName': 'IAM Identity Center', 'description': 'Compatibilidad local persistente para Identity Center.', 'resources': [{'id': 'instances', 'label': 'Instances'}]},
    'elb': {'serviceName': 'Elastic Load Balancing', 'description': 'Compatibilidad local persistente para ELB.', 'resources': [{'id': 'elbv2', 'label': 'ELBv2 load balancers'}, {'id': 'classic-elb', 'label': 'Classic load balancers'}]},
    'apprunner': {'serviceName': 'App Runner', 'description': 'Compatibilidad local persistente para App Runner.', 'resources': [{'id': 'services', 'label': 'Services'}]},
    'backup': {'serviceName': 'Backup', 'description': 'Compatibilidad local persistente para AWS Backup.', 'resources': [{'id': 'vaults', 'label': 'Backup vaults'}, {'id': 'plans', 'label': 'Backup plans'}]},
    'transfer': {'serviceName': 'Transfer Family', 'description': 'Compatibilidad local persistente para Transfer Family.', 'resources': [{'id': 'servers', 'label': 'Servers'}]},
    'textract': {'serviceName': 'Textract', 'description': 'Compatibilidad local persistente para Textract.', 'resources': [{'id': 'jobs', 'label': 'Jobs'}]},
    'pricing': {'serviceName': 'Pricing', 'description': 'Compatibilidad local persistente para Pricing.', 'resources': [{'id': 'services', 'label': 'Services'}, {'id': 'ec2-products', 'label': 'EC2 products'}]},
    'costexplorer': {'serviceName': 'Cost Explorer', 'description': 'Compatibilidad local persistente para Cost Explorer.', 'resources': [{'id': 'cost-and-usage', 'label': 'Cost and usage'}, {'id': 'dimension-values', 'label': 'Dimension values'}]},
    'cur': {'serviceName': 'Cost and Usage Reports', 'description': 'Compatibilidad local persistente para CUR.', 'resources': [{'id': 'report-definitions', 'label': 'Report definitions'}]},
    'bcmdataexports': {'serviceName': 'BCM Data Exports', 'description': 'Compatibilidad local persistente para BCM.', 'resources': [{'id': 'exports', 'label': 'Exports'}]},
    'awsq': {'serviceName': 'AWS Q Developer', 'description': 'Compatibilidad local persistente para AWS Q.', 'resources': [{'id': 'applications', 'label': 'Applications'}]},
}

def normalize_name(value: str) -> str:
    return value.strip().lower()

def code_artifact_domain_arn(domain_name: str) -> str:
    return f"arn:aws:codeartifact:{config.aws_region}:{ACCOUNT_ID}:domain/{domain_name}"

def code_artifact_repository_arn(domain_name: str, repository_name: str) -> str:
    return f"arn:aws:codeartifact:{config.aws_region}:{ACCOUNT_ID}:repository/{domain_name}/{repository_name}"

def generic_arn(service_key: str, resource_id: str, name: str) -> str:
    return f"arn:aws:{service_key}:{config.aws_region}:{ACCOUNT_ID}:{resource_id}/{name}"

def make_resource(id: str, label: str, command: str, items: List[Any]) -> Dict[str, Any]:
    return {
        'id': id,
        'label': label,
        'status': 'ok',
        'source': 'sidecar-compat',
        'command': command,
        'count': len(items),
        'items': items,
        'payload': {'items': items}
    }

class CompatibilityService:
    def __init__(self, recipe_service: RecipeService = None):
        self.code_artifact_store = JsonStateStore[CodeArtifactState](
            'codeartifact.json',
            CodeArtifactState,
            {'domains': [], 'repositories': []}
        )
        self.recipe_service = recipe_service or RecipeService()

    def can_handle(self, service_key: str) -> bool:
        return service_key == 'codeartifact' or service_key in GENERIC_COMPATIBILITY_CATALOG

    def should_bypass_native(self, service_key: str) -> bool:
        return service_key in ['codeartifact', 'marketplace', 'transfer', 'iotcore']

    def can_handle_resource(self, service_key: str, resource_id: str) -> bool:
        if service_key == 'codeartifact':
            return resource_id in ['domains', 'repositories']
        catalog = GENERIC_COMPATIBILITY_CATALOG.get(service_key)
        if catalog:
            return any(r['id'] == resource_id for r in catalog['resources'])
        return False

    async def get_overview(self, service_key: str) -> Optional[Dict[str, Any]]:
        if service_key == 'codeartifact':
            return await self._get_code_artifact_overview()
        if service_key in GENERIC_COMPATIBILITY_CATALOG:
            return await self._get_generic_overview(service_key)
        return None

    async def get_resource(self, service_key: str, resource_id: str) -> Optional[Dict[str, Any]]:
        if service_key == 'codeartifact':
            state = await self.code_artifact_store.read()
            if resource_id == 'domains':
                return make_resource('domains', 'Domains', 'sidecar compat codeartifact list-domains', [d.model_dump() for d in state.domains])
            if resource_id == 'repositories':
                return make_resource('repositories', 'Repositories', 'sidecar compat codeartifact list-repositories', [r.model_dump() for r in state.repositories])
            return None

        if service_key == 'transfer' and resource_id == 'servers':
            try:
                installations = await self.recipe_service.get_installations()
            except Exception:
                installations = {}

            transfer_inst = installations.get('transfer')
            if transfer_inst and transfer_inst.get('status') == 'RUNNING':
                vars_dict = transfer_inst.get('vars', {})
                sftp_port = vars_dict.get('SFTP_PORT', 2222)
                sftp_user = vars_dict.get('SFTP_USER', 'floci')
                sftp_pass = vars_dict.get('SFTP_PASSWORD', 'flocipass')
                server_item = {
                    'ServerId': 's-sftp-emulator',
                    'Arn': f"arn:aws:transfer:{config.aws_region}:{ACCOUNT_ID}:server/s-sftp-emulator",
                    'EndpointType': 'PUBLIC',
                    'State': 'ONLINE',
                    'UserCount': 1,
                    'Protocol': 'SFTP',
                    'EndpointDetails': f"User: {sftp_user} | Pass: {sftp_pass} | Port: {sftp_port}",
                    'CreatedTime': transfer_inst.get('installedAt', datetime.utcnow().isoformat() + "Z")
                }
                return make_resource('servers', 'Servers', 'aws transfer list-servers', [server_item])
            else:
                server_item = {
                    'ServerId': 's-sftp-emulator-offline',
                    'Arn': f"arn:aws:transfer:{config.aws_region}:{ACCOUNT_ID}:server/s-sftp-emulator-offline",
                    'EndpointType': 'PUBLIC',
                    'State': 'OFFLINE (Launch recipe in Software Marketplace)',
                    'UserCount': 0,
                    'Protocol': 'SFTP',
                    'EndpointDetails': 'No active listener running',
                    'CreatedTime': '-'
                }
                return make_resource('servers', 'Servers', 'aws transfer list-servers', [server_item])

        if service_key == 'iotcore' and resource_id == 'things':
            try:
                installations = await self.recipe_service.get_installations()
            except Exception:
                installations = {}

            iot_inst = installations.get('iotcore')
            is_running = iot_inst and iot_inst.get('status') == 'RUNNING'
            mqtt_port = iot_inst.get('vars', {}).get('MQTT_PORT', 1883) if iot_inst else 1883

            store = self._generic_store('iotcore')
            state = await store.read()
            things = state.resources.get('things', [])

            enriched_things = []
            for thing in things:
                enriched_things.append({
                    'ThingName': thing.name,
                    'Arn': thing.arn,
                    'Status': 'ONLINE' if is_running else 'OFFLINE (Broker not running)',
                    'BrokerAddress': f"localhost:{mqtt_port}" if is_running else '-',
                    'Protocol': 'MQTT (mosquitto)' if is_running else '-',
                    'CreatedTime': thing.createdTime
                })

            if len(enriched_things) == 0 and is_running:
                enriched_things.append({
                    'ThingName': 'default-floci-device',
                    'Arn': f"arn:aws:iot:{config.aws_region}:{ACCOUNT_ID}:thing/default-floci-device",
                    'Status': 'ONLINE',
                    'BrokerAddress': f"localhost:{mqtt_port}",
                    'Protocol': 'MQTT (mosquitto)',
                    'CreatedTime': iot_inst.get('installedAt', datetime.utcnow().isoformat() + "Z")
                })

            return make_resource('things', 'Things', 'aws iot list-things', enriched_things)

        definition = GENERIC_COMPATIBILITY_CATALOG.get(service_key)
        resource_def = next((r for r in definition['resources'] if r['id'] == resource_id), None) if definition else None

        if not definition or not resource_def:
            return None

        state = await self._generic_store(service_key).read()
        items = [r.model_dump() for r in state.resources.get(resource_id, [])]
        return make_resource(resource_def['id'], resource_def['label'], f"sidecar compat {service_key} {resource_def['id']}", items)

    async def create_code_artifact_domain(self, name: str) -> Dict[str, Any]:
        clean_name = normalize_name(name)
        if not clean_name:
            raise ValueError('Domain name is required')

        def mutator(state: CodeArtifactState) -> CodeArtifactState:
            if not any(d.name == clean_name for d in state.domains):
                state.domains.append(CodeArtifactDomain(
                    name=clean_name,
                    arn=code_artifact_domain_arn(clean_name),
                    owner=ACCOUNT_ID,
                    status='Active',
                    createdTime=datetime.utcnow().isoformat() + "Z"
                ))
            return state

        await self.code_artifact_store.update(mutator)
        return await self._get_code_artifact_overview()

    async def create_code_artifact_repository(self, domain_name: str, repository_name: str) -> Dict[str, Any]:
        clean_domain_name = normalize_name(domain_name)
        clean_repository_name = normalize_name(repository_name)
        if not clean_domain_name or not clean_repository_name:
            raise ValueError('Domain and repository names are required')

        def mutator(state: CodeArtifactState) -> CodeArtifactState:
            if not any(d.name == clean_domain_name for d in state.domains):
                state.domains.append(CodeArtifactDomain(
                    name=clean_domain_name,
                    arn=code_artifact_domain_arn(clean_domain_name),
                    owner=ACCOUNT_ID,
                    status='Active',
                    createdTime=datetime.utcnow().isoformat() + "Z"
                ))

            if not any(r.domainName == clean_domain_name and r.name == clean_repository_name for r in state.repositories):
                state.repositories.append(CodeArtifactRepository(
                    name=clean_repository_name,
                    arn=code_artifact_repository_arn(clean_domain_name, clean_repository_name),
                    domainName=clean_domain_name,
                    administratorAccount=ACCOUNT_ID,
                    createdTime=datetime.utcnow().isoformat() + "Z"
                ))
            return state

        await self.code_artifact_store.update(mutator)
        return await self._get_code_artifact_overview()

    async def delete_code_artifact_repository(self, domain_name: str, repository_name: str) -> Dict[str, Any]:
        clean_domain_name = normalize_name(domain_name)
        clean_repository_name = normalize_name(repository_name)

        def mutator(state: CodeArtifactState) -> CodeArtifactState:
            state.repositories = [r for r in state.repositories if not (r.domainName == clean_domain_name and r.name == clean_repository_name)]
            return state

        await self.code_artifact_store.update(mutator)
        return await self._get_code_artifact_overview()

    async def create_generic_resource(self, service_key: str, resource_id: str, name: str) -> Dict[str, Any]:
        definition = GENERIC_COMPATIBILITY_CATALOG.get(service_key)
        resource_def = next((r for r in definition['resources'] if r['id'] == resource_id), None) if definition else None
        clean_name = normalize_name(name)

        if not definition or not resource_def:
            raise ValueError(f"Unsupported compatibility resource: {service_key}/{resource_id}")
        if not clean_name:
            raise ValueError('Resource name is required')

        def mutator(state: GenericCompatibilityState) -> GenericCompatibilityState:
            records = state.resources.get(resource_id, [])
            if not any(r.name == clean_name for r in records):
                records.append(GenericCompatibilityRecord(
                    id=f"{resource_id}-{clean_name}",
                    name=clean_name,
                    arn=generic_arn(service_key, resource_id, clean_name),
                    status='Active',
                    createdTime=datetime.utcnow().isoformat() + "Z",
                    resourceType=resource_def['label']
                ))
                state.resources[resource_id] = records
            return state

        await self._generic_store(service_key).update(mutator)
        return await self._get_generic_overview(service_key)

    async def delete_generic_resource(self, service_key: str, resource_id: str, name: str) -> Dict[str, Any]:
        definition = GENERIC_COMPATIBILITY_CATALOG.get(service_key)
        clean_name = normalize_name(name)

        if not definition or not any(r['id'] == resource_id for r in definition['resources']):
            raise ValueError(f"Unsupported compatibility resource: {service_key}/{resource_id}")

        def mutator(state: GenericCompatibilityState) -> GenericCompatibilityState:
            records = state.resources.get(resource_id, [])
            state.resources[resource_id] = [r for r in records if r.name != clean_name and r.id != clean_name]
            return state

        await self._generic_store(service_key).update(mutator)
        return await self._get_generic_overview(service_key)

    async def _get_code_artifact_overview(self) -> Dict[str, Any]:
        state = await self.code_artifact_store.read()
        return {
            'serviceKey': 'codeartifact',
            'serviceName': 'CodeArtifact',
            'description': 'Compatibilidad local persistente para dominios y repositorios CodeArtifact.',
            'endpointUrl': config.aws_endpoint_url,
            'region': config.aws_region,
            'generatedAt': datetime.utcnow().isoformat() + "Z",
            'source': 'sidecar-compat',
            'resources': [
                make_resource('domains', 'Domains', 'sidecar compat codeartifact list-domains', [d.model_dump() for d in state.domains]),
                make_resource('repositories', 'Repositories', 'sidecar compat codeartifact list-repositories', [r.model_dump() for r in state.repositories]),
            ]
        }

    async def _get_generic_overview(self, service_key: str) -> Dict[str, Any]:
        definition = GENERIC_COMPATIBILITY_CATALOG.get(service_key)
        resources = []
        for r_def in definition['resources']:
            res = await self.get_resource(service_key, r_def['id'])
            if res:
                resources.append(res)

        return {
            'serviceKey': service_key,
            'serviceName': definition['serviceName'],
            'description': definition['description'],
            'endpointUrl': config.aws_endpoint_url,
            'region': config.aws_region,
            'generatedAt': datetime.utcnow().isoformat() + "Z",
            'source': 'sidecar-compat',
            'resources': resources
        }

    def _generic_store(self, service_key: str) -> JsonStateStore[GenericCompatibilityState]:
        return JsonStateStore[GenericCompatibilityState](f"{service_key}.json", GenericCompatibilityState, {'resources': {}})
