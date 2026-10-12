"""From a catalogued REST operation and the caller's parameters to one HTTP request.

Path parameters fill the template ({name} is quoted, {+name} is a reserved expansion and is
not), declared query parameters go to the query string, a `body` parameter or the leftovers
become the JSON body, and the cloud's usual defaults (project, account, compartment...) fill
what the caller left out.
"""
import os
import re
from typing import Any, Callable
from urllib.parse import quote

from floci_generic.errors import Blocked

_PLACEHOLDER = re.compile(r"{\+?(\w+)}")
DEFAULT_TENANCY = "ocid1.tenancy.oc1..flocilocaltenancy0000000000000000000000000000000000000000"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def defaults() -> dict[str, str]:
    """Values for the parameters every cloud's routes share, from FLOCI_* or Floci's own defaults."""
    project = _env("FLOCI_GCP_PROJECT", "floci-local")
    return {
        "project": project, "projectId": project, "projectsId": project, "projectNumber": project,
        "parent": f"projects/{project}", "location": "us-central1", "locationsId": "us-central1",
        "region": "us-central1", "zone": "us-central1-a",
        "account": _env("FLOCI_AZURE_ACCOUNT_NAME", "devstoreaccount1"),
        "subscription": _env("FLOCI_AZURE_SUBSCRIPTION", "00000000-0000-0000-0000-000000000000"),
        "compartmentId": _env("FLOCI_OCI_TENANCY_ID", DEFAULT_TENANCY),
    }


def _fill_path(path: str, names: list[str], values: dict[str, Any]) -> str:
    for name in names:
        value = str(values[name])
        path = path.replace("{+" + name + "}", value).replace("{" + name + "}", quote(value, safe=""))
    return path


def _split_params(params: dict, declared: dict, used: list[str]) -> tuple[dict, dict]:
    """Declared query parameters, and everything else that is not a path parameter or the body."""
    query: dict = {}
    leftovers: dict = {}
    for key, value in params.items():
        if key in used or key == "body":
            continue
        target = query if declared.get(key, {}).get("in") == "query" else leftovers
        target[key] = value
    return query, leftovers


def _required_query_defaults(declared: dict, path: str, query: dict, fallback: dict) -> None:
    for key, spec in declared.items():
        needed = spec.get("in") == "query" and spec.get("required")
        if needed and key not in query and key in fallback and f"{key}=" not in path:
            query[key] = fallback[key]


def _body(cloud: str, method: str, params: dict, leftovers: dict, query: dict, fallback: dict) -> Any:
    body = params.get("body")
    if body is None and leftovers:
        if method == "GET":
            query.update(leftovers)
        else:
            body = leftovers
    # OCI creates always carry the compartment; every route here takes it.
    if cloud == "oci" and method == "POST" and isinstance(body, dict) and "compartmentId" not in body:
        body = {**body, "compartmentId": fallback["compartmentId"]}
    return body


def build_request(cloud: str, service: str, op: dict, params: dict,
                  namespace: Callable[[], str]) -> dict:
    """The {method, path, query?, json?} request for a catalogued operation."""
    fallback = defaults()
    values = {**fallback, **{k: v for k, v in params.items() if k != "body"}}
    used = _PLACEHOLDER.findall(op["path"])
    if "namespace" in used and "namespace" not in params:
        values["namespace"] = namespace()
    missing = [p for p in used if p not in values]
    if missing:
        raise Blocked(f"Missing parameter(s) {missing} for {service}.{op['name']}. Use describe_operation to see them.")

    path = _fill_path(op["path"], used, values)
    declared = op["params"]
    query, leftovers = _split_params(params, declared, used)
    _required_query_defaults(declared, path, query, fallback)
    body = _body(cloud, op["method"], params, leftovers, query, fallback)

    request: dict = {"method": op["method"], "path": path}
    if query:
        request["query"] = query
    if body is not None:
        request["json"] = body
    return request
