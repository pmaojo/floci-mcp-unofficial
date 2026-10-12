"""Sending AWS operations to Floci with boto3."""
import os
import threading
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, ParamValidationError
from botocore.validate import validate_parameters

from floci_generic.domain.payload import plain
from floci_generic.domain.classify import to_snake


class BotoAwsTransport:
    """Implements ports.AwsTransport against the endpoint in AWS_ENDPOINT_URL (Floci)."""

    def __init__(self, models: Any, env: dict | None = None) -> None:
        self._models = models
        self._env = env if env is not None else os.environ
        self._clients: dict[str, Any] = {}
        self._lock = threading.Lock()
        self.sent = 0  # how many operations actually left the process

    def _client(self, service: str) -> Any:
        with self._lock:
            if service not in self._clients:
                env = self._env
                self._clients[service] = boto3.client(
                    service,
                    endpoint_url=env.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
                    region_name=env.get("AWS_DEFAULT_REGION", "us-east-1"),
                    aws_access_key_id=env.get("AWS_ACCESS_KEY_ID", "test"),
                    aws_secret_access_key=env.get("AWS_SECRET_ACCESS_KEY", "test"),
                    config=Config(retries={"max_attempts": 1}, connect_timeout=3, read_timeout=30),
                )
            return self._clients[service]

    def send(self, service: str, operation: str, params: dict) -> dict:
        """Call one operation; the response, or {"error": code, "message": ...}."""
        self.sent += 1
        method = getattr(self._client(service), to_snake(operation))
        try:
            response = method(**params)
        except ClientError as exc:
            err = exc.response.get("Error", {})
            return {"error": err.get("Code", "ClientError"), "message": err.get("Message", str(exc))}
        except (BotoCoreError, TypeError, ValueError) as exc:
            return {"error": type(exc).__name__, "message": str(exc)[:500]}
        response.pop("ResponseMetadata", None)
        return plain(response)

    def validate(self, service: str, operation: str, params: dict) -> str | None:
        """What botocore would say about these parameters, without sending anything."""
        shape = self._models.model(service).operation_model(operation).input_shape
        if shape is None:
            return None
        try:
            validate_parameters(params, shape)
        except ParamValidationError as exc:
            return str(exc)[:400]
        return None
