"""The one place where a generic call reaches a cloud.

Every generic tool, and the code sandbox, goes through a Gateway. The read/write decision is made
here, from the classification and the policy, not by whichever tool was registered: a read-only
gateway cannot be talked into a write by the code it runs. The cloud itself is reached through the
transport ports, so this module holds no SDK.
"""
import asyncio
from typing import Any, Mapping

from floci_generic.app import catalog
from floci_generic.app.admission import Admission
from floci_generic.app.recipes import RecipeService
from floci_generic.domain import recipes as recipes_domain
from floci_generic.domain import restroute
from floci_generic.domain.classify import Verdict, classify_rest
from floci_generic.domain.errors import Blocked
from floci_generic.domain.payload import cap
from floci_generic.domain.policy import Policy
from floci_generic.ports import AwsTransport, RestTransport

__all__ = ["Blocked", "Gateway"]


class Gateway:
    """Classifies and sends calls. `log` keeps every attempt, blocked and dry-run ones included."""

    def __init__(self, aws: AwsTransport, rest: RestTransport, admission: Admission,
                 recipes: RecipeService | None = None, env: Mapping[str, str] | None = None):
        self.aws = aws
        self.rest = rest
        self.recipes = recipes
        self.env = env or {}
        self._admission = admission

    @property
    def policy(self) -> Policy:
        """The rules this gateway applies."""
        return self._admission.policy

    @property
    def log(self) -> list[dict]:
        """Every attempt so far: sent, blocked and dry-run ones."""
        return self._admission.log

    @property
    def allow_write(self) -> bool:
        """Whether this gateway may send calls that change state."""
        return self._admission.policy.allow_write

    # -------------------------------------------------------------------- AWS
    def aws_call(self, service: str, operation: str, params: dict) -> dict:
        """One AWS operation. Cloud errors come back as {"error": code, "message": ...}."""
        if not catalog.has_aws_service(service):
            raise Blocked(f"Unknown AWS service {service!r}. Use list_services or search_operations.")
        resolved = catalog.resolve_aws_operation(service, operation)
        if resolved is None:
            raise Blocked(f"{service} has no operation {operation!r}. Use search_operations(service={service!r}).")
        verdict = catalog.aws_verdict(service, resolved)
        entry = {"cloud": "aws", "service": service, "operation": resolved, "kind": verdict.kind, "params": params}
        answer = self._admission.admit(entry, verdict, f"{service}.{resolved}")
        return answer if answer is not None else self.aws.send(service, resolved, params)

    # ------------------------------------------------------------------- REST
    def _rest_route(self, cloud: str, service: str, operation: str, params: dict) -> dict:
        op = catalog.find_rest_op(cloud, service, operation)
        if op is None:
            raise Blocked(f"{cloud} has no catalogued operation {service}.{operation}. "
                          f"Use search_operations(cloud={cloud!r}) or pass request={{method, path}}.")

        def namespace() -> str:
            return str(self._rest(cloud, {"method": "GET", "path": "/n/"})["body"]).strip('"')

        return restroute.build_request(cloud, service, op, params, namespace, self.env)

    def _rest(self, cloud: str, request: dict) -> dict:
        method = str(request.get("method", "GET")).upper()
        path = str(request.get("path", ""))
        if not restroute.is_runtime_path(path):
            raise Blocked("request.path must be a path on the runtime, such as /storage/v1/b?project=x.")
        verdict = classify_rest(cloud, method, path)
        entry = {"cloud": cloud, "method": method, "path": path, "kind": verdict.kind}
        answer = self._admission.admit(entry, Verdict(verdict.kind, verdict.destructive, verdict.sensitive, ""), f"{method} {path}")
        return answer if answer is not None else self.rest.send(cloud, method, path, request)

    # ---------------------------------------------------------------- recipes
    async def _recipes(self, operation: str, params: dict) -> dict:
        name = recipes_domain.resolve(operation)
        verdict = recipes_domain.verdict(name) if name else None
        if verdict is None:
            return {"error": f"Unknown recipe operation {operation!r}. Use search_operations(cloud='recipes')."}
        if self.recipes is None:
            return {"error": "Recipes are not available in this gateway."}
        entry = {"cloud": "recipes", "service": "marketplace", "operation": name, "kind": verdict.kind, "params": params}
        answer = self._admission.admit(entry, verdict, f"recipes.{name}")
        return answer if answer is not None else cap(await self.recipes.call(name, params))

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
