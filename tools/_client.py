"""Utilidades compartidas: cliente boto3 y transporte hacia el backend FastAPI."""
import base64
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import boto3
import httpx

from floci_backend.config import config
from floci_backend.server import app

__all__ = ["make_client", "clean", "backend", "config"]


def make_client(service: str):
    """Crea un cliente boto3 apuntando al emulador de Floci."""
    return boto3.client(
        service,
        endpoint_url=config.aws_endpoint_url,
        region_name=config.aws_region,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
    )


def clean(obj: Any) -> Any:
    """Convierte tipos boto3 no serializables (datetime, Decimal, bytes) a JSON-safe."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(i) for i in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode()
    return obj


async def backend(method: str, path: str, json_data: dict | None = None) -> Any:
    """Llama al backend FastAPI en memoria via ASGI transport (sin red)."""
    headers: dict[str, str] = {}
    if token := os.environ.get("SIDECAR_TOKEN"):
        headers["x-floci-sidecar-token"] = token

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        match method.upper():
            case "GET":
                resp = await client.get(path, headers=headers)
            case "POST":
                resp = await client.post(path, headers=headers, json=json_data)
            case "PUT":
                resp = await client.put(path, headers=headers, json=json_data)
            case "DELETE":
                resp = await client.delete(path, headers=headers)
            case _:
                raise ValueError(f"Método HTTP no soportado: {method}")

        resp.raise_for_status()
        return resp.json()
