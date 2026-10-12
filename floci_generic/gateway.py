"""The one place where a generic call reaches a cloud.

Every generic tool, and the code sandbox, goes through Gateway.call. The read/write
decision is made here, from the classification, not by whichever tool was registered:
a read-only gateway cannot be talked into a write by the code it runs.
"""
import base64
import json
import os
import re
import threading
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from floci_generic import catalog
from floci_generic.classify import classify_rest, split_name, to_snake

OUTPUT_LIMIT = 20_000
BODY_READ_LIMIT = 64 * 1024


class Blocked(Exception):
    """The call was refused before it left the process."""


def _plain(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, (bytes, bytearray)):
        try:
            return bytes(obj).decode("utf-8")
        except UnicodeDecodeError:
            return base64.b64encode(bytes(obj)).decode()
    if hasattr(obj, "read") and hasattr(obj, "close"):  # StreamingBody
        data = obj.read(BODY_READ_LIMIT + 1)
        return _plain(data[:BODY_READ_LIMIT]) + ("…[truncated]" if len(data) > BODY_READ_LIMIT else "")
    return obj


def cap(value: Any, limit: int = OUTPUT_LIMIT) -> Any:
    text = json.dumps(value, default=str)
    if len(text) <= limit:
        return value
    return {"truncated": True, "total_chars": len(text), "preview": text[:limit]}


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


class Gateway:
    def __init__(self, allow_write: bool = False, dry_run_writes: bool = False, allow_sensitive: bool | None = None):
        self.allow_write = allow_write
        # dry_run_writes records the write and answers {"dry_run": true} instead of sending it (used by the eval).
        self.dry_run_writes = dry_run_writes
        self.allow_sensitive = (
            allow_sensitive if allow_sensitive is not None
            else _env("FLOCI_ALLOW_SECRET_VALUES", "").lower() in ("1", "true", "yes", "on")
        )
        self.log: list[dict] = []
        self._clients: dict[str, Any] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ AWS
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

    def _aws(self, service: str, operation: str, params: dict) -> dict:
        if not catalog.has_aws_service(service):
            raise Blocked(f"Unknown AWS service {service!r}. Use list_services or search_operations.")
        resolved = catalog.resolve_aws_operation(service, operation)
        if resolved is None:
            raise Blocked(f"{service} has no operation {operation!r}. Use search_operations(service={service!r}).")
        verdict = catalog.aws_verdict(service, resolved)
        entry = {"cloud": "aws", "service": service, "operation": resolved, "kind": verdict.kind, "params": params}
        if not verdict.read and not self.allow_write:
            raise Blocked(f"{service}.{resolved} changes state ({verdict.reason}); this is a read-only call. Use the write tool.")
        if verdict.read and verdict.sensitive and not self.allow_sensitive:
            raise Blocked(f"{service}.{resolved} returns secret values. Set FLOCI_ALLOW_SECRET_VALUES=1 to allow it.")
        if not verdict.read and self.dry_run_writes:
            self.log.append({**entry, "dry_run": True})
            return {"dry_run": True, "would_call": f"{service}.{resolved}"}
        self.log.append(entry)
        method = getattr(self._client(service), to_snake(resolved))
        try:
            response = method(**params)
        except ClientError as exc:
            err = exc.response.get("Error", {})
            return {"error": err.get("Code", "ClientError"), "message": err.get("Message", str(exc))}
        except (BotoCoreError, TypeError, ValueError) as exc:
            return {"error": type(exc).__name__, "message": str(exc)[:500]}
        response.pop("ResponseMetadata", None)
        return _plain(response)

    # ------------------------------------------------------------------ REST
    def _defaults(self) -> dict[str, str]:
        project = _env("FLOCI_GCP_PROJECT", "floci-local")
        return {
            "project": project, "projectId": project, "projectsId": project, "projectNumber": project,
            "parent": f"projects/{project}", "location": "us-central1", "locationsId": "us-central1",
            "region": "us-central1", "zone": "us-central1-a",
            "account": _env("FLOCI_AZURE_ACCOUNT_NAME", "devstoreaccount1"),
            "subscription": _env("FLOCI_AZURE_SUBSCRIPTION", "00000000-0000-0000-0000-000000000000"),
            "compartmentId": _env("FLOCI_OCI_TENANCY_ID",
                                  "ocid1.tenancy.oc1..flocilocaltenancy0000000000000000000000000000000000000000"),
        }

    def _rest_route(self, cloud: str, service: str, operation: str, params: dict) -> dict:
        from urllib.parse import quote

        op = catalog.find_rest_op(cloud, service, operation)
        if op is None:
            raise Blocked(f"{cloud} has no catalogued operation {service}.{operation}. "
                          f"Use search_operations(cloud={cloud!r}) or pass request={{method, path}}.")
        values = {**self._defaults(), **{k: v for k, v in params.items() if k != "body"}}
        path = op["path"]
        used = re.findall(r"{\+?(\w+)}", path)
        if "namespace" in used and "namespace" not in params:
            values["namespace"] = str(self._rest(cloud, {"method": "GET", "path": "/n/"})["body"]).strip('"')
        missing = [p for p in used if p not in values]
        if missing:
            raise Blocked(f"Missing parameter(s) {missing} for {service}.{op['name']}. "
                          f"Use describe_operation to see them.")
        for name in used:
            value = str(values[name])
            path = path.replace("{+" + name + "}", value).replace("{" + name + "}", quote(value, safe=""))
        declared = op["params"]
        query: dict = {}
        leftovers: dict = {}
        for key, value in params.items():
            if key in used or key == "body":
                continue
            (query if declared.get(key, {}).get("in") == "query" else leftovers)[key] = value
        defaults = self._defaults()
        for key, spec in declared.items():
            if spec.get("in") == "query" and spec.get("required") and key not in query and key in defaults and f"{key}=" not in path:
                query[key] = defaults[key]
        request: dict = {"method": op["method"], "path": path}
        body = params.get("body")
        if body is None and leftovers:
            if op["method"] == "GET":
                query.update(leftovers)
            else:
                body = leftovers
        if cloud == "oci" and op["method"] == "POST" and isinstance(body, dict) and "compartmentId" not in body:
            body = {**body, "compartmentId": defaults["compartmentId"]}
        if query:
            request["query"] = query
        if body is not None:
            request["json"] = body
        return request

    def _rest(self, cloud: str, request: dict) -> dict:
        method = str(request.get("method", "GET")).upper()
        path = str(request.get("path", ""))
        if not path.startswith("/") or "://" in path or ".." in path.split("?")[0].split("/"):
            raise Blocked("request.path must be a path on the runtime, such as /storage/v1/b?project=x.")
        verdict = classify_rest(cloud, method, path)
        entry = {"cloud": cloud, "method": method, "path": path, "kind": verdict.kind}
        if not verdict.read and not self.allow_write:
            raise Blocked(f"{method} {path} changes state; this is a read-only call. Use the write tool.")
        if verdict.read and verdict.sensitive and not self.allow_sensitive:
            raise Blocked(f"{method} {path} returns secret values. Set FLOCI_ALLOW_SECRET_VALUES=1 to allow it.")
        if not verdict.read and self.dry_run_writes:
            self.log.append({**entry, "dry_run": True})
            return {"dry_run": True, "would_call": f"{method} {path}"}
        self.log.append(entry)
        from tools.clouds import AZURE_API_VERSION, endpoint
        headers = {str(k): str(v) for k, v in (request.get("headers") or {}).items()}
        if cloud == "azure":
            headers.setdefault("x-ms-version", AZURE_API_VERSION)
            headers.setdefault("authorization", "Bearer floci-mcp")
        try:
            with httpx.Client(base_url=endpoint(cloud), timeout=15) as client:
                response = client.request(
                    method, path, params=request.get("query"), json=request.get("json"),
                    content=request.get("body"), headers=headers,
                )
        except httpx.HTTPError as exc:
            return {"error": "Unreachable", "message": f"Cannot reach the {cloud} runtime: {exc}"}
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text
        return {"status": response.status_code, "body": body}

    # ------------------------------------------------------------------ entry
    async def _recipes(self, operation: str, params: dict) -> dict:
        from floci_generic import recipes

        name = recipes.resolve(operation)
        verdict = recipes.verdict(name) if name else None
        if verdict is None:
            return {"error": f"Unknown recipe operation {operation!r}. Use search_operations(cloud='recipes')."}
        entry = {"cloud": "recipes", "service": "marketplace", "operation": name, "kind": verdict.kind, "params": params}
        if not verdict.read and not self.allow_write:
            raise Blocked(f"recipes.{name} changes state; this is a read-only call. Use the write tool.")
        if not verdict.read and self.dry_run_writes:
            self.log.append({**entry, "dry_run": True})
            return {"dry_run": True, "would_call": f"recipes.{name}"}
        self.log.append(entry)
        return cap(await recipes.call(name, params))

    async def acall(self, cloud: str, service: str = "", operation: str = "", params: dict | None = None,
                    request: dict | None = None) -> dict:
        """call() for async callers. Recipes run on the caller's event loop, everything else in a thread."""
        import asyncio

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
            return cap(self._aws(service, operation, params))
        if request:
            return cap(self._rest(cloud, request))
        return cap(self._rest(cloud, self._rest_route(cloud, service, operation, params)))


def make_pair() -> "tuple[Gateway, Gateway]":
    """The reading and the writing gateway a toolset registers. The eval replaces this to record dry runs."""
    return Gateway(allow_write=False), Gateway(allow_write=True)


def probe_aws(services: "list[str] | None" = None, workers: int = 16, attempts: int = 6) -> dict[str, str]:
    """Which AWS services answer on Floci.

    A service answers when any of a few argument-free reads works. One failing operation says
    nothing about the service: Floci may implement ListTables and not DescribeEndpoints.
    """
    from concurrent.futures import ThreadPoolExecutor

    from botocore.exceptions import EndpointConnectionError

    gateway = Gateway()
    missing = ("NotImplemented", "UnknownOperation", "UnsupportedOperation", "InvalidAction", "UnrecognizedClient")
    order = {"list": 0, "describe": 1, "get": 2}

    def candidates(service: str) -> list[str]:
        model = catalog.aws_model(service)
        found = []
        for name in model.operation_names:
            op = model.operation_model(name)
            verdict = catalog.aws_verdict(service, name)
            if verdict.read and not verdict.sensitive and not (op.input_shape and op.input_shape.required_members):
                found.append(name)
        found.sort(key=lambda n: (order.get(split_name(n)[0], 3), n))
        return found[:attempts]

    def one(service: str) -> tuple[str, str]:
        names = candidates(service)
        if not names:
            return service, "no-argument-free-read"
        outcome = "not-implemented"
        for name in names:
            try:
                result = gateway._aws(service, name, {})
            except EndpointConnectionError:
                return service, "unreachable"
            except Exception as exc:  # noqa: BLE001
                outcome = f"error: {type(exc).__name__}"
                continue
            code = result.get("error", "")
            if not code:
                return service, "answers"
            if not any(m in code for m in missing):
                # The service understood the request and refused it for its own reasons.
                return service, "answers"
        return service, outcome

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(one, services or catalog.aws_services()))
