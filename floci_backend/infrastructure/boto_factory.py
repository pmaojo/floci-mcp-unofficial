"""boto3 client factory pointing at Floci's local emulator.

Centralizes client construction so application-layer services don't repeat the
endpoint/credentials configuration. For hybrid mode (Area 5) it accepts explicit
overrides that target a real AWS account.
"""
import boto3
from typing import Optional
from floci_backend.config import config


def make_client(
    service_name: str,
    *,
    endpoint_url: Optional[str] = None,
    region_name: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
):
    """Create a boto3 client.

    With no arguments it points at the local emulator using Floci's static test
    credentials. Passing ``endpoint_url=""`` targets the real AWS endpoint.

    Credential resolution:
      - Explicit ``aws_access_key_id``/``aws_secret_access_key`` (optionally with a
        session token) always win.
      - Otherwise, for the local emulator we inject the static ``test``/``test``
        credentials so LocalStack works out of the box.
      - For real AWS with no explicit credentials we pass nothing, letting boto3's
        default provider chain resolve them (env vars, shared config/credentials,
        AWS profiles, SSO/STS temporary credentials, instance-role metadata, ...).
    """
    resolved_endpoint = endpoint_url if endpoint_url is not None else config.aws_endpoint_url
    targeting_real_aws = resolved_endpoint == ""
    if targeting_real_aws:
        resolved_endpoint = None

    client_kwargs: dict = {
        "endpoint_url": resolved_endpoint,
        "region_name": region_name or config.aws_region,
    }

    if aws_access_key_id and aws_secret_access_key:
        client_kwargs["aws_access_key_id"] = aws_access_key_id
        client_kwargs["aws_secret_access_key"] = aws_secret_access_key
        if aws_session_token:
            client_kwargs["aws_session_token"] = aws_session_token
    elif not targeting_real_aws:
        # Local emulator: static credentials keep LocalStack happy.
        client_kwargs["aws_access_key_id"] = config.aws_access_key_id
        client_kwargs["aws_secret_access_key"] = config.aws_secret_access_key
    # else: real AWS without explicit credentials -> defer to boto3's provider chain.

    return boto3.client(service_name, **client_kwargs)
