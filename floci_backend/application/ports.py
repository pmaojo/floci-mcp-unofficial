"""The backend hexagon's ports: what the application services need from the outside world.

Services depend on these shapes only. boto3, the aws CLI and the disk live in floci_backend/infrastructure,
and floci_backend/server.py is the one place where the real adapters are wired in.
"""
from typing import Any, Dict, List, Optional, Protocol


class QueueTransport(Protocol):
    """The SQS operations the dead-letter-queue service needs. Failures propagate as the SDK raises them."""

    def list_queue_urls(self) -> List[str]: ...

    def queue_attributes(self, queue_url: str, names: List[str]) -> Dict[str, str]: ...

    def queue_url(self, queue_name: str) -> Optional[str]: ...

    def receive(
        self,
        queue_url: str,
        *,
        max_messages: int,
        visibility_timeout: int,
        wait_seconds: int,
        all_attributes: bool = False,
    ) -> List[Dict[str, Any]]:
        """Receive up to max_messages with all their message attributes (and system attributes when asked)."""
        ...

    def send(self, queue_url: str, body: str, message_attributes: Dict[str, Any]) -> None: ...

    def delete(self, queue_url: str, receipt_handle: str) -> None: ...


class ResourceTagging(Protocol):
    """Tags across every resource type (the Resource Groups Tagging API). Failures propagate as the SDK raises them."""

    def resources(
        self, tag_filters: Optional[List[Dict[str, Any]]] = None, resource_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Every resource-tag mapping matching the filters, all pages."""
        ...

    def tag_keys(self) -> List[str]: ...

    def tag_values(self, key: str) -> List[str]: ...

    def tag(self, resource_arns: List[str], tags: Dict[str, str]) -> Dict[str, Any]:
        """ARN -> failure for the resources that could not be tagged."""
        ...

    def untag(self, resource_arns: List[str], tag_keys: List[str]) -> Dict[str, Any]:
        """ARN -> failure for the resources that could not be untagged."""
        ...


class CommandError(Exception):
    """A command that ran and failed, or could not run. Adapters raise a subclass of it."""

    def __init__(self, message: str, stdout: str, stderr: str, exit_code: int):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code


class CliRunner(Protocol):
    """Runs one `aws` CLI command against Floci and returns its parsed JSON output ({} when it prints nothing).

    Raises CommandError (or a subclass) when the command fails."""

    async def run_json(self, args: List[str]) -> Any: ...
