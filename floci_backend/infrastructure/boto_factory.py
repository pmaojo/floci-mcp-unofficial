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
):
    """Create a boto3 client.

    With no arguments it points at the local emulator. Passing explicit
    credentials/endpoint lets it target a real AWS account (cloud proxying,
    seeding). Passing ``endpoint_url=""`` forces the real AWS endpoint (no local
    override).
    """
    resolved_endpoint = endpoint_url if endpoint_url is not None else config.aws_endpoint_url
    if resolved_endpoint == "":
        resolved_endpoint = None

    return boto3.client(
        service_name,
        endpoint_url=resolved_endpoint,
        region_name=region_name or config.aws_region,
        aws_access_key_id=aws_access_key_id or config.aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key or config.aws_secret_access_key,
    )
