AWS_RESOURCE_CATALOG = {
    's3': {
        'serviceName': 'S3',
        'description': 'Buckets reales de S3.',
        'resources': [
            {'id': 'buckets', 'label': 'Buckets', 'command': ['s3api', 'list-buckets'], 'resultPath': 'Buckets'},
        ],
    },
    'dynamodb': {
        'serviceName': 'DynamoDB',
        'description': 'Tablas reales de DynamoDB.',
        'resources': [
            {'id': 'tables', 'label': 'Tables', 'command': ['dynamodb', 'list-tables'], 'resultPath': 'TableNames'},
        ],
    },
    'sns': {
        'serviceName': 'SNS',
        'description': 'Topics y suscripciones reales de SNS.',
        'resources': [
            {'id': 'topics', 'label': 'Topics', 'command': ['sns', 'list-topics'], 'resultPath': 'Topics'},
            {'id': 'subscriptions', 'label': 'Subscriptions', 'command': ['sns', 'list-subscriptions'], 'resultPath': 'Subscriptions'},
        ],
    },
    'sqs': {
        'serviceName': 'SQS',
        'description': 'Colas reales de SQS.',
        'resources': [
            {'id': 'queues', 'label': 'Queues', 'command': ['sqs', 'list-queues'], 'resultPath': 'QueueUrls'},
        ],
    },
    'events': {
        'serviceName': 'EventBridge',
        'description': 'Event buses y reglas reales de EventBridge.',
        'resources': [
            {'id': 'event-buses', 'label': 'Event buses', 'command': ['events', 'list-event-buses'], 'resultPath': 'EventBuses'},
            {'id': 'rules', 'label': 'Rules', 'command': ['events', 'list-rules'], 'resultPath': 'Rules'},
        ],
    },
    'iam': {
        'serviceName': 'IAM',
        'description': 'Usuarios, roles y políticas reales de IAM.',
        'resources': [
            {'id': 'users', 'label': 'Users', 'command': ['iam', 'list-users'], 'resultPath': 'Users'},
            {'id': 'roles', 'label': 'Roles', 'command': ['iam', 'list-roles'], 'resultPath': 'Roles'},
            {'id': 'policies', 'label': 'Policies', 'command': ['iam', 'list-policies', '--scope', 'Local'], 'resultPath': 'Policies'},
        ],
    },
    'sts': {
        'serviceName': 'STS',
        'description': 'Identidad de cuenta real de STS.',
        'resources': [
            {'id': 'caller-identity', 'label': 'Caller identity', 'command': ['sts', 'get-caller-identity'], 'resultPath': None},
        ],
    },
    'kms': {
        'serviceName': 'KMS',
        'description': 'Claves y alias reales de KMS.',
        'resources': [
            {'id': 'keys', 'label': 'Keys', 'command': ['kms', 'list-keys'], 'resultPath': 'Keys'},
            {'id': 'aliases', 'label': 'Aliases', 'command': ['kms', 'list-aliases'], 'resultPath': 'Aliases'},
        ],
    },
    'secretsmanager': {
        'serviceName': 'Secrets Manager',
        'description': 'Secretos reales de Secrets Manager.',
        'resources': [
            {'id': 'secrets', 'label': 'Secrets', 'command': ['secretsmanager', 'list-secrets'], 'resultPath': 'SecretList'},
        ],
    },
    'ec2': {
        'serviceName': 'EC2',
        'description': 'Instancias, VPCs y grupos de seguridad reales de EC2.',
        'resources': [
            {'id': 'instances', 'label': 'Instances', 'command': ['ec2', 'describe-instances'], 'resultPath': 'Reservations'},
            {'id': 'vpcs', 'label': 'VPCs', 'command': ['ec2', 'describe-vpcs'], 'resultPath': 'Vpcs'},
            {'id': 'security-groups', 'label': 'Security groups', 'command': ['ec2', 'describe-security-groups'], 'resultPath': 'SecurityGroups'},
        ],
    },
    'rds': {
        'serviceName': 'RDS',
        'description': 'Instancias y clusters reales de RDS.',
        'resources': [
            {'id': 'db-instances', 'label': 'DB Instances', 'command': ['rds', 'describe-db-instances'], 'resultPath': 'DBInstances'},
            {'id': 'db-clusters', 'label': 'DB Clusters', 'command': ['rds', 'describe-db-clusters'], 'resultPath': 'DBClusters'},
        ],
    },
    'elasticache': {
        'serviceName': 'ElastiCache',
        'description': 'Clusters reales de ElastiCache.',
        'resources': [
            {'id': 'cache-clusters', 'label': 'Cache clusters', 'command': ['elasticache', 'describe-cache-clusters'], 'resultPath': 'CacheClusters'},
        ],
    },
    'lambda': {
        'serviceName': 'Lambda',
        'description': 'Funciones y capas reales de Lambda.',
        'resources': [
            {'id': 'functions', 'label': 'Functions', 'command': ['lambda', 'list-functions'], 'resultPath': 'Functions'},
            {'id': 'layers', 'label': 'Layers', 'command': ['lambda', 'list-layers'], 'resultPath': 'Layers'},
        ],
    },
    'ecs': {
        'serviceName': 'ECS',
        'description': 'Clusters y tareas reales de ECS.',
        'resources': [
            {'id': 'clusters', 'label': 'Clusters', 'command': ['ecs', 'list-clusters'], 'resultPath': 'clusterArns'},
            {'id': 'task-definitions', 'label': 'Task definitions', 'command': ['ecs', 'list-task-definitions'], 'resultPath': 'taskDefinitionArns'},
        ],
    },
    'ecr': {
        'serviceName': 'ECR',
        'description': 'Repositorios reales de ECR.',
        'resources': [
            {'id': 'repositories', 'label': 'Repositories', 'command': ['ecr', 'describe-repositories'], 'resultPath': 'repositories'},
        ],
    },
    'cloudformation': {
        'serviceName': 'CloudFormation',
        'description': 'Stacks reales de CloudFormation.',
        'resources': [
            {'id': 'stacks', 'label': 'Stacks', 'command': ['cloudformation', 'describe-stacks'], 'resultPath': 'Stacks'},
        ],
    },
    'cloudwatch': {
        'serviceName': 'CloudWatch',
        'description': 'Métricas y alarmas reales de CloudWatch.',
        'resources': [
            {'id': 'metrics', 'label': 'Metrics', 'command': ['cloudwatch', 'list-metrics'], 'resultPath': 'Metrics'},
            {'id': 'alarms', 'label': 'Alarms', 'command': ['cloudwatch', 'describe-alarms'], 'resultPath': 'MetricAlarms'},
        ],
    },
    'logs': {
        'serviceName': 'CloudWatch Logs',
        'description': 'Log groups reales de CloudWatch Logs.',
        'resources': [
            {'id': 'log-groups', 'label': 'Log groups', 'command': ['logs', 'describe-log-groups'], 'resultPath': 'logGroups'},
        ],
    },
    'kinesis': {
        'serviceName': 'Kinesis',
        'description': 'Data streams reales de Kinesis.',
        'resources': [
            {'id': 'streams', 'label': 'Streams', 'command': ['kinesis', 'list-streams'], 'resultPath': 'StreamNames'},
        ],
    },
    'glue': {
        'serviceName': 'Glue',
        'description': 'Bases de datos y jobs reales de Glue.',
        'resources': [
            {'id': 'databases', 'label': 'Databases', 'command': ['glue', 'get-databases'], 'resultPath': 'DatabaseList'},
            {'id': 'jobs', 'label': 'Jobs', 'command': ['glue', 'get-jobs'], 'resultPath': 'Jobs'},
        ],
    },
    'apigateway': {
        'serviceName': 'API Gateway',
        'description': 'APIs reales de API Gateway.',
        'resources': [
            {'id': 'rest-apis', 'label': 'REST APIs', 'command': ['apigateway', 'get-rest-apis'], 'resultPath': 'items'},
            {'id': 'v2-apis', 'label': 'HTTP/WebSocket APIs', 'command': ['apigatewayv2', 'get-apis'], 'resultPath': 'Items'},
        ],
    },
    'route53': {
        'serviceName': 'Route 53',
        'description': 'Hosted zones reales de Route 53.',
        'resources': [
            {'id': 'hosted-zones', 'label': 'Hosted zones', 'command': ['route53', 'list-hosted-zones'], 'resultPath': 'HostedZones'},
        ],
    },
    'stepfunctions': {
        'serviceName': 'Step Functions',
        'description': 'State machines reales de Step Functions.',
        'resources': [
            {'id': 'state-machines', 'label': 'State machines', 'command': ['stepfunctions', 'list-state-machines'], 'resultPath': 'stateMachines'},
        ],
    },
    'cognito': {
        'serviceName': 'Cognito',
        'description': 'User pools reales de Cognito.',
        'resources': [
            {'id': 'user-pools', 'label': 'User pools', 'command': ['cognito-idp', 'list-user-pools', '--max-results', '10'], 'resultPath': 'UserPools'},
            {'id': 'identity-pools', 'label': 'Identity pools', 'command': ['cognito-identity', 'list-identity-pools', '--max-results', '10'], 'resultPath': 'IdentityPools'},
        ],
    },
    'ses': {
        'serviceName': 'SES',
        'description': 'Identidades reales de SES.',
        'resources': [
            {'id': 'identities', 'label': 'Identities', 'command': ['ses', 'list-identities'], 'resultPath': 'Identities'},
        ],
    },
    'athena': {
        'serviceName': 'Athena',
        'description': 'Workgroups y catálogos reales de Athena.',
        'resources': [
            {'id': 'workgroups', 'label': 'Workgroups', 'command': ['athena', 'list-work-groups'], 'resultPath': 'WorkGroups'},
            {'id': 'catalogs', 'label': 'Data catalogs', 'command': ['athena', 'list-data-catalogs'], 'resultPath': 'DataCatalogsSummary'},
        ],
    },
    'cloudfront': {
        'serviceName': 'CloudFront',
        'description': 'Distribuciones reales de CloudFront.',
        'resources': [
            {'id': 'distributions', 'label': 'Distributions', 'command': ['cloudfront', 'list-distributions'], 'resultPath': 'DistributionList.Items'},
        ],
    },
    'wafv2': {
        'serviceName': 'WAFv2',
        'description': 'Web ACLs reales de WAFv2.',
        'resources': [
            {'id': 'web-acls', 'label': 'Web ACLs', 'command': ['wafv2', 'list-web-acls', '--scope', 'REGIONAL'], 'resultPath': 'WebACLs'},
        ],
    },
    'scheduler': {
        'serviceName': 'EventBridge Scheduler',
        'description': 'Schedules y groups reales de EventBridge Scheduler.',
        'resources': [
            {'id': 'schedules', 'label': 'Schedules', 'command': ['scheduler', 'list-schedules'], 'resultPath': 'Schedules'},
            {'id': 'schedule-groups', 'label': 'Schedule groups', 'command': ['scheduler', 'list-schedule-groups'], 'resultPath': 'ScheduleGroups'},
        ],
    },
    'firehose': {
        'serviceName': 'Data Firehose',
        'description': 'Delivery streams reales de Firehose.',
        'resources': [
            {'id': 'delivery-streams', 'label': 'Delivery streams', 'command': ['firehose', 'list-delivery-streams'], 'resultPath': 'DeliveryStreamNames'},
        ],
    },
    'appconfig': {
        'serviceName': 'AppConfig',
        'description': 'Aplicaciones reales de AppConfig.',
        'resources': [
            {'id': 'applications', 'label': 'Applications', 'command': ['appconfig', 'list-applications'], 'resultPath': 'Items'},
            {'id': 'deployment-strategies', 'label': 'Deployment strategies', 'command': ['appconfig', 'list-deployment-strategies'], 'resultPath': 'Items'},
        ],
    },
    'appconfigdata': {
        'serviceName': 'AppConfig Data',
        'description': 'Data plane de AppConfig.',
        'resources': [],
    },
    'bedrockruntime': {
        'serviceName': 'Bedrock Runtime',
        'description': 'Runtime local stub de Bedrock.',
        'resources': [],
    },
    'codebuild': {
        'serviceName': 'CodeBuild',
        'description': 'Proyectos y builds reales de CodeBuild.',
        'resources': [
            {'id': 'projects', 'label': 'Projects', 'command': ['codebuild', 'list-projects'], 'resultPath': 'projects'},
            {'id': 'builds', 'label': 'Builds', 'command': ['codebuild', 'list-builds'], 'resultPath': 'ids'},
        ],
    },
    'codeartifact': {
        'serviceName': 'CodeArtifact',
        'description': 'Dominios y repositorios de CodeArtifact.',
        'resources': [
            {'id': 'domains', 'label': 'Domains', 'command': ['codeartifact', 'list-domains'], 'resultPath': 'domains'},
            {'id': 'repositories', 'label': 'Repositories', 'command': ['codeartifact', 'list-repositories'], 'resultPath': 'repositories'},
        ],
    },
    'codepipeline': {
        'serviceName': 'CodePipeline',
        'description': 'Pipelines reales de CodePipeline.',
        'resources': [
            {'id': 'pipelines', 'label': 'Pipelines', 'command': ['codepipeline', 'list-pipelines'], 'resultPath': 'pipelines'},
        ],
    },
    'codedeploy': {
        'serviceName': 'CodeDeploy',
        'description': 'Aplicaciones reales de CodeDeploy.',
        'resources': [
            {'id': 'applications', 'label': 'Applications', 'command': ['deploy', 'list-applications'], 'resultPath': 'applications'},
            {'id': 'deployment-configs', 'label': 'Deployment configs', 'command': ['deploy', 'list-deployment-configs'], 'resultPath': 'deploymentConfigsList'},
            {'id': 'deployments', 'label': 'Deployments', 'command': ['deploy', 'list-deployments'], 'resultPath': 'deployments'},
        ],
    },
    'appsync': {
        'serviceName': 'AppSync',
        'description': 'GraphQL APIs reales de AppSync.',
        'resources': [
            {'id': 'graphql-apis', 'label': 'GraphQL APIs', 'command': ['appsync', 'list-graphql-apis'], 'resultPath': 'graphqlApis'},
        ],
    },
    'marketplace': {
        'serviceName': 'Software Marketplace',
        'description': 'Catálogo real de AWS Marketplace.',
        'resources': [
            {'id': 'ami-products', 'label': 'AMI products', 'command': ['marketplace-catalog', 'list-entities', '--catalog', 'AWSMarketplace', '--entity-type', 'AmiProduct'], 'resultPath': 'EntitySummaryList'},
        ],
    },
    'roadmap': {
        'serviceName': 'Roadmap',
        'description': 'No hay backend operativo configurado para roadmap dentro de Floci.',
        'resources': [],
    },
    'redshift': {
        'serviceName': 'Redshift',
        'description': 'Clusters reales de Redshift.',
        'resources': [
            {'id': 'clusters', 'label': 'Clusters', 'command': ['redshift', 'describe-clusters'], 'resultPath': 'Clusters'},
        ],
    },
    'opensearch': {
        'serviceName': 'OpenSearch',
        'description': 'Dominios reales de OpenSearch.',
        'resources': [
            {'id': 'domains', 'label': 'Domains', 'command': ['opensearch', 'list-domain-names'], 'resultPath': 'DomainNames'},
        ],
    },
    'msk': {
        'serviceName': 'MSK',
        'description': 'Clusters reales de Kafka/MSK.',
        'resources': [
            {'id': 'clusters', 'label': 'Clusters', 'command': ['kafka', 'list-clusters'], 'resultPath': 'ClusterInfoList'},
        ],
    },
    'sagemaker': {
        'serviceName': 'SageMaker',
        'description': 'Modelos y endpoints reales de SageMaker.',
        'resources': [
            {'id': 'models', 'label': 'Models', 'command': ['sagemaker', 'list-models'], 'resultPath': 'Models'},
            {'id': 'endpoints', 'label': 'Endpoints', 'command': ['sagemaker', 'list-endpoints'], 'resultPath': 'Endpoints'},
        ],
    },
    'iotcore': {
        'serviceName': 'IoT Core',
        'description': 'Things reales de IoT Core.',
        'resources': [
            {'id': 'things', 'label': 'Things', 'command': ['iot', 'list-things'], 'resultPath': 'things'},
        ],
    },
    'batch': {
        'serviceName': 'AWS Batch',
        'description': 'Colas y compute environments reales de AWS Batch.',
        'resources': [
            {'id': 'job-queues', 'label': 'Job queues', 'command': ['batch', 'describe-job-queues'], 'resultPath': 'jobQueues'},
            {'id': 'compute-environments', 'label': 'Compute environments', 'command': ['batch', 'describe-compute-environments'], 'resultPath': 'computeEnvironments'},
        ],
    },
    'autoscaling': {
        'serviceName': 'Auto Scaling',
        'description': 'Auto Scaling groups y launch configurations reales.',
        'resources': [
            {'id': 'auto-scaling-groups', 'label': 'Auto Scaling groups', 'command': ['autoscaling', 'describe-auto-scaling-groups'], 'resultPath': 'AutoScalingGroups'},
            {'id': 'launch-configurations', 'label': 'Launch configurations', 'command': ['autoscaling', 'describe-launch-configurations'], 'resultPath': 'LaunchConfigurations'},
        ],
    },
    'transitgateway': {
        'serviceName': 'Transit Gateway',
        'description': 'Transit gateways reales leídos desde EC2.',
        'resources': [
            {'id': 'transit-gateways', 'label': 'Transit gateways', 'command': ['ec2', 'describe-transit-gateways'], 'resultPath': 'TransitGateways'},
        ],
    },
    'beanstalk': {
        'serviceName': 'Elastic Beanstalk',
        'description': 'Aplicaciones y entornos reales de Elastic Beanstalk.',
        'resources': [
            {'id': 'applications', 'label': 'Applications', 'command': ['elasticbeanstalk', 'describe-applications'], 'resultPath': 'Applications'},
            {'id': 'environments', 'label': 'Environments', 'command': ['elasticbeanstalk', 'describe-environments'], 'resultPath': 'Environments'},
        ],
    },
    'efs': {
        'serviceName': 'EFS',
        'description': 'File systems reales de EFS.',
        'resources': [
            {'id': 'file-systems', 'label': 'File systems', 'command': ['efs', 'describe-file-systems'], 'resultPath': 'FileSystems'},
        ],
    },
    'neptune': {
        'serviceName': 'Neptune',
        'description': 'Clusters reales de Neptune.',
        'resources': [
            {'id': 'clusters', 'label': 'DB clusters', 'command': ['neptune', 'describe-db-clusters'], 'resultPath': 'DBClusters'},
        ],
    },
    'cloudtrail': {
        'serviceName': 'CloudTrail',
        'description': 'Trails y eventos reales de CloudTrail.',
        'resources': [
            {'id': 'trails', 'label': 'Trails', 'command': ['cloudtrail', 'describe-trails'], 'resultPath': 'trailList'},
            {'id': 'events', 'label': 'Events', 'command': ['cloudtrail', 'lookup-events'], 'resultPath': 'Events'},
        ],
    },
    'identitycenter': {
        'serviceName': 'IAM Identity Center',
        'description': 'Instancias reales de IAM Identity Center.',
        'resources': [
            {'id': 'instances', 'label': 'Instances', 'command': ['sso-admin', 'list-instances'], 'resultPath': 'Instances'},
        ],
    },
    'elb': {
        'serviceName': 'Elastic Load Balancing',
        'description': 'Load balancers reales de ELBv2.',
        'resources': [
            {'id': 'elbv2', 'label': 'ELBv2 load balancers', 'command': ['elbv2', 'describe-load-balancers'], 'resultPath': 'LoadBalancers'},
        ],
    },
    'apprunner': {
        'serviceName': 'App Runner',
        'description': 'Servicios reales de App Runner.',
        'resources': [
            {'id': 'services', 'label': 'Services', 'command': ['apprunner', 'list-services'], 'resultPath': 'ServiceSummaryList'},
        ],
    },
    'backup': {
        'serviceName': 'Backup',
        'description': 'Vaults y planes reales de AWS Backup.',
        'resources': [
            {'id': 'vaults', 'label': 'Backup vaults', 'command': ['backup', 'list-backup-vaults'], 'resultPath': 'BackupVaultList'},
            {'id': 'plans', 'label': 'Backup plans', 'command': ['backup', 'list-backup-plans'], 'resultPath': 'BackupPlansList'},
        ],
    },
    'transfer': {
        'serviceName': 'Transfer Family',
        'description': 'Servidores reales de AWS Transfer Family.',
        'resources': [
            {'id': 'servers', 'label': 'Servers', 'command': ['transfer', 'list-servers'], 'resultPath': 'Servers'},
        ],
    },
    'textract': {
        'serviceName': 'Textract',
        'description': 'API stub de Textract para desarrollo local.',
        'resources': [],
    },
    'pricing': {
        'serviceName': 'Pricing',
        'description': 'Catalogo de servicios y productos del endpoint Pricing local.',
        'resources': [
            {'id': 'services', 'label': 'Services', 'command': ['pricing', 'describe-services'], 'resultPath': 'Services'},
            {'id': 'ec2-products', 'label': 'EC2 products', 'command': ['pricing', 'get-products', '--service-code', 'AmazonEC2', '--max-results', '10'], 'resultPath': 'PriceList'},
        ],
    },
    'costexplorer': {
        'serviceName': 'Cost Explorer',
        'description': 'Costes sintetizados desde el estado local de Floci.',
        'resources': [],
    },
    'cur': {
        'serviceName': 'Cost and Usage Reports',
        'description': 'Definiciones reales de Cost and Usage Reports.',
        'resources': [
            {'id': 'report-definitions', 'label': 'Report definitions', 'command': ['cur', 'describe-report-definitions'], 'resultPath': 'ReportDefinitions'},
        ],
    },
    'bcmdataexports': {
        'serviceName': 'BCM Data Exports',
        'description': 'Exports reales de Billing and Cost Management Data Exports.',
        'resources': [
            {'id': 'exports', 'label': 'Exports', 'command': ['bcm-data-exports', 'list-exports'], 'resultPath': 'Exports'},
        ],
    },
    'awsq': {
        'serviceName': 'AWS Q Developer',
        'description': 'Aplicaciones reales de Amazon Q Business.',
        'resources': [
            {'id': 'applications', 'label': 'Applications', 'command': ['qbusiness', 'list-applications'], 'resultPath': 'applications'},
        ],
    },
    'ssm': {
        'serviceName': 'SSM Parameters',
        'description': 'Parámetros reales de Systems Manager Parameter Store.',
        'resources': [
            {'id': 'parameters', 'label': 'Parameters', 'command': ['ssm', 'describe-parameters'], 'resultPath': 'Parameters'},
        ],
    },
}
