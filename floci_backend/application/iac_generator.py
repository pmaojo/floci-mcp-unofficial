import boto3
import json
from floci_backend.config import config

class IacGenerator:
    def __init__(self):
        self.endpoint_url = config.aws_endpoint_url
        self.region = config.aws_region
        self.access_key = config.aws_access_key_id
        self.secret_key = config.aws_secret_access_key

    def _get_client(self, service_name: str):
        return boto3.client(
            service_name,
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        )

    def export_to_terraform(self) -> str:
        s3_client = self._get_client('s3')
        sqs_client = self._get_client('sqs')
        dynamodb_client = self._get_client('dynamodb')
        lambda_client = self._get_client('lambda')
        kms_client = self._get_client('kms')

        terraform_code = [
            'provider "aws" {',
            f'  region = "{self.region}"',
            '}',
            ''
        ]

        # S3
        try:
            buckets = s3_client.list_buckets().get('Buckets', [])
            for bucket in buckets:
                name = bucket['Name']
                terraform_code.extend([
                    f'resource "aws_s3_bucket" "{name.replace("-", "_")}" {{',
                    f'  bucket = "{name}"',
                    '}',
                    ''
                ])
        except Exception:
            pass

        # SQS
        try:
            queues = sqs_client.list_queues().get('QueueUrls', [])
            for q_url in queues:
                q_name = q_url.split('/')[-1]
                terraform_code.extend([
                    f'resource "aws_sqs_queue" "{q_name.replace("-", "_")}" {{',
                    f'  name = "{q_name}"',
                    '}',
                    ''
                ])
        except Exception:
            pass

        # DynamoDB
        try:
            tables = dynamodb_client.list_tables().get('TableNames', [])
            for table in tables:
                table_info = dynamodb_client.describe_table(TableName=table).get('Table', {})
                hash_key = None
                for key_schema in table_info.get('KeySchema', []):
                    if key_schema['KeyType'] == 'HASH':
                        hash_key = key_schema['AttributeName']
                        break

                terraform_code.extend([
                    f'resource "aws_dynamodb_table" "{table.replace("-", "_")}" {{',
                    f'  name = "{table}"',
                    '  billing_mode = "PAY_PER_REQUEST"'
                ])
                if hash_key:
                    terraform_code.extend([
                        f'  hash_key = "{hash_key}"',
                        '  attribute {',
                        f'    name = "{hash_key}"',
                        '    type = "S"',
                        '  }'
                    ])
                terraform_code.extend([
                    '}',
                    ''
                ])
        except Exception:
            pass

        # Lambda
        try:
            functions = lambda_client.list_functions().get('Functions', [])
            for func in functions:
                f_name = func['FunctionName']
                handler = func.get('Handler', 'index.handler')
                runtime = func.get('Runtime', 'python3.9')
                terraform_code.extend([
                    f'resource "aws_lambda_function" "{f_name.replace("-", "_")}" {{',
                    f'  function_name = "{f_name}"',
                    f'  handler = "{handler}"',
                    f'  runtime = "{runtime}"',
                    '  role = "arn:aws:iam::123456789012:role/mock-role"',
                    '}',
                    ''
                ])
        except Exception:
            pass

        # KMS
        try:
            keys = kms_client.list_keys().get('Keys', [])
            for i, key in enumerate(keys):
                terraform_code.extend([
                    f'resource "aws_kms_key" "key_{i}" {{',
                    f'  description = "KMS key {key["KeyId"]}"',
                    '}',
                    ''
                ])
        except Exception:
            pass

        return "\n".join(terraform_code)

    def export_to_cdk(self) -> str:
        raise NotImplementedError("CDK export is not implemented yet.")
