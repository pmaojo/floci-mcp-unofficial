"""The hexagon's ports: what the application needs from the outside world.

The domain and the application depend on these shapes only. boto3, httpx, the disk, Docker and
subprocesses live in adapters that implement them, and bootstrap.py is the one place they meet.
"""
from typing import Any, Protocol


class ServiceModels(Protocol):
    """The AWS service models (shaped like botocore's) the catalog is built from."""

    def services(self) -> list[str]: ...

    def model(self, service: str) -> Any: ...


class RestData(Protocol):
    """The generated route catalogs of Azure, GCP and OCI."""

    def load(self, cloud: str) -> dict | None: ...


class AwsTransport(Protocol):
    """Sends one AWS operation. Every outcome is a dict: the response, or {"error": code, "message": ...}
    (EndpointConnectionError when the runtime cannot be reached)."""

    def send(self, service: str, operation: str, params: dict) -> dict: ...

    def validate(self, service: str, operation: str, params: dict) -> str | None:
        """What the SDK would say about these parameters, without sending anything."""
        ...


class RestTransport(Protocol):
    """Sends one HTTP request to a REST cloud's runtime and returns {"status", "body"} or {"error"}."""

    def send(self, cloud: str, method: str, path: str, request: dict) -> dict: ...


class RecipeRuntime(Protocol):
    """Where recipes are listed, installed and removed, and what is known about the host."""

    async def recipes(self) -> list[dict]: ...

    async def installations(self) -> dict: ...

    async def logs(self, recipe_id: str) -> list[str]: ...

    async def install(self, recipe_id: str, variables: dict) -> None: ...

    async def uninstall(self, recipe_id: str) -> None: ...

    def port_busy(self, port: int) -> bool: ...

    def answering_aws(self, services: list[str]) -> set[str]:
        """Which of these AWS services answer on the running Floci."""
        ...
