"""The one place where a generic call reaches a cloud.

Every generic tool, and the code sandbox, goes through Gateway. The read/write decision is
made here, from the classification, not by whichever tool was registered: a read-only gateway
cannot be talked into a write by the code it runs.
"""
import asyncio
import os
import threading
from typing import Any

import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, ParamValidationError
from botocore.validate import validate_parameters

from floci_generic import catalog, restroute
from floci_generic.classify import Verdict, classify_rest, to_snake
from floci_generic.errors import Blocked
from floci_generic.payload import cap, plain

__all__ = ["Blocked", "Gateway", "make_pair"]

_TRUTHY = ("1", "true", "yes", "on")


def _validate(service: str, operation: str, params: dict) -> str | None:
    """What botocore would say about these parameters, without sending anything."""
    shape = catalog.aws_model(service).operation_model(operation).input_shape
    if shape is None:
        return None
    try:
        validate_parameters(params, shape)
    except ParamValidationError as exc:
        return str(exc)[:400]
    return None


class Gateway:
    """Classifies and sends calls. `allow_write` False makes it a reader; `dry_run_writes` records
    writes instead of sending them (the eval); `log` keeps every attempt, blocked ones included."""

    def __init__(self, allow_write: bool = False, dry_run_writes: bool = False, allow_sensitive: bool | None = None):
        self.allow_write = allow_write
        self.dry_run_writes = dry_run_writes
        if allow_sensitive is None:
            allow_sensitive = os.environ.get("FLOCI_ALLOW_SECRET_VALUES", "").lower() in _TRUTHY
        self.allow_sensitive = allow_sensitive
        self.log: list[dict] = []
        self._clients: dict[str, Any] = {}
        self._lock = threading.Lock()

    # ----------------------------------------------------------------- policy
    def _admit(self, entry: dict, verdict: Verdict, label: str) -> dict | None:
        """Apply the read/write and secret rules to one call.

        Raises Blocked when it is refused, returns the dry-run answer when a write is only being
        recorded, and returns None when the call should go ahead.
        """
        if not verdict.read and not self.allow_write:
            self.log.append({**entry, "blocked": "write"})
            reason = f" ({verdict.reason})" if verdict.reason else ""
            raise Blocked(f"{label} changes state{reason}; this is a read-only call. Use the write tool.")
        if verdict.read and verdict.sensitive and not self.allow_sensitive:
            self.log.append({**entry, "blocked": "sensitive"})
            raise Blocked(f"{label} returns secret values. Set FLOCI_ALLOW_SECRET_VALUES=1 to allow it.")
        if not verdict.read and self.dry_run_writes:
            return self._dry_run(entry, label)
        self.log.append(entry)
        return None

    def _dry_run(self, entry: dict, label: str) -> dict:
        params = entry.get("params")
        problem = _validate(entry["service"], entry["operation"], params) if entry["cloud"] == "aws" else None
        if problem:
            self.log.append({**entry, "dry_run": True, "invalid": True})
            return {"error": "ParamValidationError", "message": problem}
        self.log.append({**entry, "dry_run": True})
        return {"dry_run": True, "would_call": label}

    # -------------------------------------------------------------------- AWS
    def _client(self, service: str):
        with self._lock:
            if service not in self._clients:
                from floci_backend.config import config
                self._clients[service] = boto3.client(
                    service,
                    endpoint_url=config.aws_endpoint_url,
                    region_name=config.aws_region,
                    aws_access_key_id=config.aws_access_key_id,
                    aws_secret_access_key=config.aws_secret_access_key,
                    config=Config(retries={"max_attempts": 1}, connect_timeout=3, read_timeout=30),
                )
            return self._clients[service]

    def aws_call(self, service: str, operation: str, params: dict) -> dict:
        """One AWS operation through boto3. Cloud errors come back as {"error": code, "message": ...}."""
        if not catalog.has_aws_service(service):
            raise Blocked(f"Unknown AWS service {service!r}. Use list_services or search_operations.")
        resolved = catalog.resolve_aws_operation(service, operation)
        if resolved is None:
            raise Blocked(f"{service} has no operation {operation!r}. Use search_operations(service={service!r}).")
        verdict = catalog.aws_verdict(service, resolved)
        entry = {"cloud": "aws", "service": service, "operation": resolved, "kind": verdict.kind, "params": params}
        answer = self._admit(entry, verdict, f"{service}.{resolved}")
        if answer is not None:
            return answer
        return self._send_aws(service, resolved, params)

    def _send_aws(self, service: str, operation: str, params: dict) -> dict:
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

    # ------------------------------------------------------------------- REST
    def _rest_route(self, cloud: str, service: str, operation: str, params: dict) -> dict:
        op = catalog.find_rest_op(cloud, service, operation)
        if op is None:
            raise Blocked(f"{cloud} has no catalogued operation {service}.{operation}. "
                          f"Use search_operations(cloud={cloud!r}) or pass request={{method, path}}.")

        def namespace() -> str:
            return str(self._rest(cloud, {"method": "GET", "path": "/n/"})["body"]).strip('"')

        return restroute.build_request(cloud, service, op, params, namespace)

    def _rest(self, cloud: str, request: dict) -> dict:
        method = str(request.get("method", "GET")).upper()
        path = str(request.get("path", ""))
        if not path.startswith("/") or "://" in path or ".." in path.split("?")[0].split("/"):
            raise Blocked("request.path must be a path on the runtime, such as /storage/v1/b?project=x.")
        verdict = classify_rest(cloud, method, path)
        entry = {"cloud": cloud, "method": method, "path": path, "kind": verdict.kind}
        answer = self._admit(entry, Verdict(verdict.kind, verdict.destructive, verdict.sensitive, ""), f"{method} {path}")
        if answer is not None:
            return answer
        return self._send_rest(cloud, method, path, request)

    def _send_rest(self, cloud: str, method: str, path: str, request: dict) -> dict:
        from floci_tools.clouds import AZURE_API_VERSION, endpoint

        headers = {str(k): str(v) for k, v in (request.get("headers") or {}).items()}
        if cloud == "azure":
            headers.setdefault("x-ms-version", AZURE_API_VERSION)
            headers.setdefault("authorization", "Bearer floci-mcp")
        try:
            with httpx.Client(base_url=endpoint(cloud), timeout=15) as client:
                response = client.request(method, path, params=request.get("query"), json=request.get("json"),
                                          content=request.get("body"), headers=headers)
        except httpx.HTTPError as exc:
            return {"error": "Unreachable", "message": f"Cannot reach the {cloud} runtime: {exc}"}
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text
        return {"status": response.status_code, "body": body}

    # ---------------------------------------------------------------- recipes
    async def _recipes(self, operation: str, params: dict) -> dict:
        from floci_generic import recipes

        name = recipes.resolve(operation)
        verdict = recipes.verdict(name) if name else None
        if verdict is None:
            return {"error": f"Unknown recipe operation {operation!r}. Use search_operations(cloud='recipes')."}
        entry = {"cloud": "recipes", "service": "marketplace", "operation": name, "kind": verdict.kind, "params": params}
        answer = self._admit(entry, verdict, f"recipes.{name}")
        if answer is not None:
            return answer
        return cap(await recipes.call(name, params))

    # ------------------------------------------------------------------ entry
    async def acall(self, cloud: str, service: str = "", operation: str = "", params: dict | None = None,
                    request: dict | None = None) -> dict:
        """call() for async callers. Recipes run on the caller's event loop, everything else in a thread."""
        if cloud == "recipes":
            return await self._recipes(operation, params or {})
        return await asyncio.to_thread(self.call, cloud, service, operation, params, request)

    def call(self, cloud: str, service: str = "", operation: str = "", params: dict | None = None,
             request: dict | None = None) -> dict:
        """One call. Raises Blocked when it is refused; cloud errors come back as {"error": ...}."""
        if cloud not in catalog.CLOUDS:
            raise Blocked(f"Unknown cloud {cloud!r}. Use one of {', '.join(catalog.CLOUDS)}.")
        params = params or {}
        if cloud == "recipes":
            raise Blocked("Recipes run on the server's event loop: use acall (the tools do).")
        if cloud == "aws":
            if request:
                raise Blocked("AWS calls use service, operation and params.")
            return cap(self.aws_call(service, operation, params))
        route = request or self._rest_route(cloud, service, operation, params)
        return cap(self._rest(cloud, route))


def make_pair() -> "tuple[Gateway, Gateway]":
    """The reading and the writing gateway a toolset registers. The eval replaces this to record dry runs."""
    return Gateway(allow_write=False), Gateway(allow_write=True)
