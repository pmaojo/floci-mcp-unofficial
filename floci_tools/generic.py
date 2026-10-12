"""Generic tools: the whole of every Floci runtime behind five calls.

Discover with list_services, search_operations and describe_operation, then act
with call_read or call_write. AWS is driven by the boto3 service models, so every
operation of every service is reachable; Azure, GCP and OCI take a route from the
catalog or a raw `request` for anything else; `recipes` is the Docker recipe
catalog. Reads and writes are separate tools, so FLOCI_READ_ONLY removes the
writer instead of guessing from a name.
"""
import asyncio

from floci_generic import catalog, recipes
from floci_generic import gateway as gw
from floci_generic.errors import Blocked
from floci_generic.probe import probe_aws

_probe_cache: dict[str, str] = {}


def register(mcp):
    reader, writer = gw.make_pair()

    @mcp.tool()
    async def list_services(cloud: str = "aws", probe: bool = False) -> dict:
        """
        Lists the services of a cloud: aws, azure, gcp, oci or recipes (local Docker stacks).

        For aws, probe=true also asks the running Floci which services answer (a few seconds, cached).
        Azure, GCP and OCI list what Floci supports; any other route is reachable with request={method, path}.
        """
        if cloud not in catalog.CLOUDS:
            return {"error": f"Unknown cloud {cloud!r}. Use one of {', '.join(catalog.CLOUDS)}."}
        if cloud == "aws":
            if probe and not _probe_cache:
                _probe_cache.update(await asyncio.to_thread(probe_aws))
            if _probe_cache:
                answering = sorted(s for s, v in _probe_cache.items() if v == "answers")
                return {"cloud": cloud, "answering": answering, "count": len(answering),
                        "note": "Services not listed did not answer a probe; the model still knows every AWS service."}
            return {"cloud": cloud, "services": catalog.aws_services()}
        if cloud == "recipes":
            return {"cloud": cloud, "services": catalog.list_services(cloud),
                    "hint": "Operations: " + ", ".join(recipes.OPERATIONS) + ". Start with ListRecipes."}
        return {"cloud": cloud, "services": catalog.list_services(cloud), "hint": catalog.REST_HINTS[cloud]}

    @mcp.tool()
    async def search_operations(query: str, cloud: str = "aws", service: str = "", limit: int = 8) -> dict:
        """
        Finds operations by what they do, e.g. "list buckets", "send message to queue", "start a local redis".

        Narrow with service (s3, sqs, dynamodb, ...) when you know it. Each hit says whether the operation
        reads or writes; pass it to describe_operation for its parameters, then call_read or call_write.
        """
        if cloud not in catalog.CLOUDS:
            return {"error": f"Unknown cloud {cloud!r}."}
        hits = await asyncio.to_thread(catalog.search, query, cloud, service or None, max(1, min(limit, 25)))
        return {"cloud": cloud, "hits": hits}

    @mcp.tool()
    async def describe_operation(cloud: str, service: str, operation: str, detail: str = "brief") -> dict:
        """
        Returns what an operation does, its required parameters with their docs, its optional parameters
        by name and type, what it returns, and whether it reads or writes. Read this before calling an
        operation you have not used. detail="full" adds the docs of every optional parameter (long).
        """
        if cloud == "aws":
            if not catalog.has_aws_service(service):
                return {"error": f"Unknown AWS service {service!r}. Use list_services or search_operations."}
            name = catalog.resolve_aws_operation(service, operation)
            if name is None:
                return {"error": f"{service} has no operation {operation!r}. Try search_operations(service={service!r})."}
            return await asyncio.to_thread(catalog.describe_aws, service, name, detail)
        if cloud == "recipes":
            return recipes.describe(operation) or {"error": f"Unknown recipe operation {operation!r}. Use one of {', '.join(recipes.OPERATIONS)}."}
        if cloud in catalog.CLOUDS:
            info = catalog.describe_rest(cloud, service, operation)
            if info:
                return info
            return {"error": f"No catalogued operation {service}.{operation} on {cloud}.",
                    "hint": catalog.REST_HINTS[cloud], "use": "call_read/call_write with request={method, path, query, json}"}
        return {"error": f"Unknown cloud {cloud!r}."}

    @mcp.tool()
    async def call_read(cloud: str, service: str = "", operation: str = "", params: dict | None = None,
                        request: dict | None = None) -> dict:
        """
        Calls an operation that only reads. Refuses anything that would change state.

        aws: service, operation (ListBuckets or list_buckets) and params (names from describe_operation).
        azure, gcp, oci: a catalogued service and operation with params, or request={method, path, query, json}.
        recipes: operation ListRecipes, GetRecipe, GetStatus or GetLogs.
        """
        try:
            return await reader.acall(cloud, service, operation, params, request)
        except Blocked as exc:
            return {"blocked": str(exc)}

    @mcp.tool()
    async def call_write(cloud: str, service: str = "", operation: str = "", params: dict | None = None,
                         request: dict | None = None) -> dict:
        """
        Calls an operation that creates, changes, sends or deletes. Same arguments as call_read.

        Check with describe_operation first (destructive is flagged) and ask the user before anything
        destructive, such as a delete, a purge or TeardownRecipe (which removes data).
        """
        try:
            return await writer.acall(cloud, service, operation, params, request)
        except Blocked as exc:
            return {"blocked": str(exc)}
