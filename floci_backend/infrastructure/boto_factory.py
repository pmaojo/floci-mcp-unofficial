"""Fábrica de clientes boto3 apuntando al emulador local de Floci.

Centraliza la construcción de clientes para que los servicios de la capa de
aplicación no repitan la configuración de endpoint/credenciales. Para el modo
híbrido (Área 5) acepta overrides explícitos que apuntan a una cuenta AWS real.
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
    """Crea un cliente boto3.

    Sin argumentos apunta al emulador local. Pasando credenciales/endpoint
    explícitos se puede apuntar a una cuenta AWS real (cloud proxying, seeding).
    Pasar ``endpoint_url=""`` fuerza el endpoint real de AWS (sin override local).
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
