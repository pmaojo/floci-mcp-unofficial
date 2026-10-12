"""Catalog use cases: what can be called, how to call it, and finding it from a sentence.

The service models and the route data arrive through ports (see bootstrap.configure); nothing here
imports an SDK. The functions keep the names the tools and tests have always used.
"""
import functools

from floci_generic.domain import describe as describe_domain
from floci_generic.domain import recipes as recipes_domain
from floci_generic.domain import rest_ops as rest_domain
from floci_generic.domain import search as search_domain
from floci_generic.domain.classify import Verdict, classify_rest
from floci_generic.domain.clouds import (  # noqa: F401  re-exported for the tools
    CLOUDS, DEFAULTED_PARAMS, REST_HINTS, REST_PROTOCOLS, REST_SERVICES,
)
from floci_generic.ports import RestData, ServiceModels


class _Wiring:
    """The adapters this catalog reads from. Set once by configure()."""

    models: ServiceModels | None = None
    data: RestData | None = None


def configure(models: ServiceModels, data: RestData) -> None:
    """Install the service-model and route-data adapters and forget anything derived from the old ones."""
    _Wiring.models, _Wiring.data = models, data
    for cached in (aws_services, aws_model, rest_ops, _index):
        cached.cache_clear()


def _need_models() -> ServiceModels:
    if _Wiring.models is None:
        raise RuntimeError("floci_generic is not configured: import floci_generic.bootstrap first.")
    return _Wiring.models


# ----------------------------------------------------------------------------- AWS
@functools.lru_cache(maxsize=1)
def aws_services() -> list[str]:
    """Every AWS service the models know, sorted."""
    return sorted(_need_models().services())


@functools.lru_cache(maxsize=None)
def aws_model(service: str):
    """The service model of one AWS service."""
    return _need_models().model(service)


def has_aws_service(service: str) -> bool:
    """Whether the models know this service."""
    return service in set(aws_services())


def aws_operation_names(service: str) -> list[str]:
    """The operation names of a service, in the model's spelling."""
    return list(aws_model(service).operation_names)


def aws_verdict(service: str, operation: str) -> Verdict:
    """Classify one operation as read or write."""
    return describe_domain.verdict_for(aws_model(service), service, operation)


def resolve_aws_operation(service: str, operation: str) -> str | None:
    """Accepts ListBuckets, list_buckets or listbuckets and returns the model's name."""
    names = aws_operation_names(service)
    if operation in names:
        return operation
    flat = "".join(c for c in operation.lower() if c.isalnum())
    return next((n for n in names if "".join(c for c in n.lower() if c.isalnum()) == flat), None)


def describe_aws(service: str, operation: str, detail: str = "brief") -> dict:
    """Describe an AWS operation: required parameters, optional ones, what it returns, read or write."""
    return describe_domain.describe_aws(aws_model(service), service, operation, detail)


# ---------------------------------------------------------------------------- REST
@functools.lru_cache(maxsize=None)
def rest_ops(cloud: str) -> dict[str, list[dict]]:
    """service -> operations for azure, gcp and oci."""
    if _Wiring.data is None:
        raise RuntimeError("floci_generic is not configured: import floci_generic.bootstrap first.")
    return rest_domain.build(cloud, _Wiring.data.load(cloud))


def find_rest_op(cloud: str, service: str, operation: str) -> dict | None:
    """A REST operation by friendly name or provider id."""
    return rest_domain.find(rest_ops(cloud), service, operation)


def describe_rest(cloud: str, service: str, operation: str) -> dict | None:
    """Describe a REST operation, or None when it is not catalogued."""
    op = find_rest_op(cloud, service, operation)
    return rest_domain.describe(cloud, service, op) if op else None


def list_services(cloud: str) -> list[dict]:
    """The services of a cloud, with how many operations are catalogued and verified for each."""
    if cloud == "recipes":
        return [{"name": "marketplace", "described_operations": len(recipes_domain.OPERATIONS)}]
    if cloud == "aws":
        return [{"name": s} for s in aws_services()]
    ops = rest_ops(cloud)
    names = list(ops) + [n for n in REST_SERVICES[cloud] if n not in ops]
    return [{"name": n, "operations": len(ops.get(n, [])),
             "verified": sum(1 for o in ops.get(n, []) if o.get("verified"))} for n in names]


# --------------------------------------------------------------------------- search
def _aws_entries(service: str | None) -> list[dict]:
    entries = []
    for svc in ([service] if service else aws_services()):
        if not has_aws_service(svc):
            continue
        model = aws_model(svc)
        for op in aws_operation_names(svc):
            entries.append(search_domain.aws_entry(svc, op, describe_domain.first_sentence(model, op)))
    return entries


def _entries(cloud: str, service: str | None) -> list[dict]:
    if cloud == "aws":
        return _aws_entries(service)
    if cloud == "recipes":
        return [search_domain.recipe_entry(name, kind, summary)
                for name, (kind, _, summary, _) in recipes_domain.OPERATIONS.items()]
    entries = []
    for svc, items in rest_ops(cloud).items():
        if service and svc != service:
            continue
        entries.extend(search_domain.rest_entry(cloud, svc, op) for op in items)
    return entries


@functools.lru_cache(maxsize=16)
def _index(cloud: str, service: str | None) -> search_domain.Index:
    return search_domain.build_index(_entries(cloud, service))


def _present(cloud: str, entry: dict) -> dict:
    """One search hit as the tools return it."""
    hit = {"service": entry["service"], "operation": entry["operation"]}
    if cloud == "aws":
        return {**hit, "kind": aws_verdict(entry["service"], entry["operation"]).kind}
    if cloud == "recipes":
        return {**hit, "kind": entry["kind"], "summary": entry["summary"][:100]}
    return {**hit, "kind": classify_rest(cloud, entry["method"], "").kind, "summary": entry["summary"]}


def search(query: str, cloud: str = "aws", service: str | None = None, limit: int = 8) -> list[dict]:
    """Operations that match a sentence, best first, each with whether it reads or writes."""
    ranked = search_domain.rank(_index(cloud, service), query, limit)
    return [_present(cloud, entry) for entry in ranked]
