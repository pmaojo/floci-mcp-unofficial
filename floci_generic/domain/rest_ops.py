"""The route catalog of Azure, GCP and OCI as plain data: build it, look things up in it, describe it."""
import re

from floci_generic.domain.classify import classify_rest
from floci_generic.domain.clouds import DEFAULTED_PARAMS, HAND_ROUTES

_ARM = "/subscriptions/{subscription}"
_ARM_RG = _ARM + "/resourceGroups/{resourceGroup}"
_ARM_RG_LOWER = _ARM + "/resourcegroups/{resourceGroup}"
_PATH_PARAM = {"in": "path", "required": True, "type": "string"}
_OPTIONAL_PATH_PARAM = {"in": "path", "required": False, "type": "string"}
_BODY = {"in": "body", "required": True, "type": "object"}


def hand_ops(cloud: str) -> dict[str, list[dict]]:
    """The routes written by hand (Azure data plane, GCP basics, OCI Object Storage)."""
    out: dict[str, list[dict]] = {}
    for svc, name, method, path, summary in HAND_ROUTES.get(cloud, []):
        params = {p: dict(_PATH_PARAM) for p in re.findall(r"{(\w+)}", path)}
        if method in ("POST", "PUT") and "Create" in name and cloud == "oci":
            params["body"] = {"in": "body", "required": False, "type": "object"}
        out.setdefault(svc, []).append({"name": name, "id": f"{svc}.{name}", "method": method, "path": path,
                                        "params": params, "summary": summary, "verified": True})
    return out


def _arm_base_ops() -> list[dict]:
    sub = {"subscription": dict(_OPTIONAL_PATH_PARAM)}
    rg = {**sub, "resourceGroup": dict(_PATH_PARAM)}
    version = "?api-version=2021-04-01"
    return [
        {"name": "ListSubscriptions", "method": "GET", "path": "/subscriptions?api-version=2020-01-01",
         "params": {}, "summary": "Lists subscriptions", "verified": True},
        {"name": "ListResourceGroups", "method": "GET", "path": _ARM + "/resourcegroups" + version,
         "params": sub, "summary": "Lists resource groups", "verified": True},
        {"name": "CreateResourceGroup", "method": "PUT", "path": _ARM_RG_LOWER + version,
         "params": {**rg, "body": dict(_BODY)}, "summary": "Creates a resource group; body {location}"},
        {"name": "DeleteResourceGroup", "method": "DELETE", "path": _ARM_RG_LOWER + version,
         "params": rg, "summary": "Deletes a resource group and everything in it"},
    ]


def _arm_type_ops(entry: dict) -> list[dict]:
    type_, version = entry["type"], entry["api_version"]
    noun = type_.split("/")[-1]
    plural = noun[:1].upper() + noun[1:]
    singular = plural[:-1] if plural.endswith("s") and not plural.endswith("ss") else plural
    sub = {"subscription": dict(_OPTIONAL_PATH_PARAM)}
    rg = {**sub, "resourceGroup": dict(_PATH_PARAM)}
    item = {"name": dict(_PATH_PARAM)}
    one = f"{_ARM_RG}/providers/{type_}/{{name}}?api-version={version}"
    return [
        {"name": f"List{plural}", "method": "GET", "path": f"{_ARM}/providers/{type_}?api-version={version}",
         "params": sub, "summary": f"Lists {type_}", "verified": True},
        {"name": f"Get{singular}", "method": "GET", "path": one, "params": {**rg, **item},
         "summary": f"Returns one {type_}", "verified": True},
        {"name": f"Put{singular}", "method": "PUT", "path": one, "params": {**rg, **item, "body": dict(_BODY)},
         "summary": f"Creates or updates a {type_}"},
        {"name": f"Delete{singular}", "method": "DELETE", "path": one, "params": {**rg, **item},
         "summary": f"Deletes a {type_}"},
    ]


def arm_ops(data: dict) -> dict[str, list[dict]]:
    """Azure's ARM operations: the generic ones, and four per resource type that answered on Floci."""
    ops: dict[str, list[dict]] = {"arm": _arm_base_ops()}
    for entry in data.get("arm_types", []):
        ops.setdefault(entry["service"], []).extend(_arm_type_ops(entry))
    return ops


def build(cloud: str, data: dict | None) -> dict[str, list[dict]]:
    """service -> operations: hand-written routes plus whatever was generated for the cloud."""
    ops = hand_ops(cloud)
    if data:
        generated = arm_ops(data) if cloud == "azure" else data
        for svc, items in generated.items():
            known = {o["name"].lower() for o in ops.get(svc, [])}
            ops.setdefault(svc, []).extend(o for o in items if o["name"].lower() not in known)
    for items in ops.values():
        for op in items:
            op.setdefault("id", op["name"])
    return ops


def find(ops: dict[str, list[dict]], service: str, operation: str) -> dict | None:
    """An operation by its friendly name or its provider id, case-insensitively."""
    wanted = operation.lower()
    for op in ops.get(service, []):
        if op["name"].lower() == wanted or op.get("id", "").lower() == wanted:
            return op
    return None


def describe(cloud: str, service: str, op: dict) -> dict:
    """What an agent needs to know before calling a REST operation."""
    verdict = classify_rest(cloud, op["method"], op["path"])
    params = {}
    for name, spec in op["params"].items():
        defaulted = name in DEFAULTED_PARAMS
        info = {"in": spec.get("in", "path"), "required": spec.get("required", False) and not defaulted,
                "type": spec.get("type", "string")}
        if defaulted:
            info["note"] = "default from FLOCI_* when omitted"
        params[name] = info
    out = {
        "cloud": cloud, "service": service, "operation": op["name"], "method": op["method"], "path": op["path"],
        "kind": verdict.kind, "destructive": verdict.destructive, "sensitive": verdict.sensitive,
        "summary": op.get("summary", ""), "params": params,
        "call_with": "call_read" if verdict.read else "call_write",
    }
    if "verified" in op:
        out["verified_on_floci"] = op["verified"]
    return out
