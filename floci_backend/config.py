import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class SidecarConfig(BaseSettings):
    host: str = os.getenv('SIDECAR_HOST', '127.0.0.1')
    port: int = int(os.getenv('SIDECAR_PORT', '4317'))
    aws_endpoint_url: str = os.getenv('AWS_ENDPOINT_URL', 'http://localhost:4566')
    aws_region: str = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    aws_access_key_id: str = os.getenv('AWS_ACCESS_KEY_ID', 'test')
    aws_secret_access_key: str = os.getenv('AWS_SECRET_ACCESS_KEY', 'test')
    default_lambda_role_arn: str = os.getenv('LAMBDA_DEFAULT_ROLE_ARN', 'arn:aws:iam::000000000000:role/lambda-role')
    state_dir: str = os.getenv('SIDECAR_STATE_DIR', '.sidecar-state')
    token: str = os.getenv('SIDECAR_TOKEN', '')
    allowed_origins: list[str] = [origin.strip() for origin in os.getenv('SIDECAR_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') if origin.strip()]
    max_body_mb: int = int(os.getenv('SIDECAR_MAX_BODY_MB', '60'))

config = SidecarConfig()
SIDECAR_TOKEN_HEADER = 'x-floci-sidecar-token'
