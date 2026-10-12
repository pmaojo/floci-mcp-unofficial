"""The Docker recipe catalog as one more cloud of the gateway: cloud="recipes".

Recipes are Docker Compose stacks (keycloak, ollama, metabase...), not cloud APIs, so
they have no service model. They are exposed here, behind the same gateway, because
that costs no tool definitions: an agent finds them with search_operations and runs
them with call_read / call_write / code_*. Docker is only touched by the server
process, never by the code sandbox.
"""
import asyncio
import re
import socket
from typing import Any

from floci_generic.classify import Verdict

# operation -> (kind, destructive, summary, parameters)
OPERATIONS: dict[str, tuple[str, bool, str, dict[str, str]]] = {
    "ListRecipes": ("read", False,
                    "Lists the recipes: id, name, what each is, the AWS service it stands in for, and whether "
                    "Floci emulates that service natively (prefer the native one).",
                    {"query": "optional word to filter by"}),
    "GetRecipe": ("read", False,
                  "One recipe in full: its variables with defaults, access URL and AWS counterpart.",
                  {"recipe_id": "required"}),
    "GetStatus": ("read", False,
                  "State of installed recipes: IDLE, INSTALLING, RUNNING, UNINSTALLING or FAILED, with the access URL.",
                  {"recipe_id": "optional; all installed when omitted"}),
    "GetLogs": ("read", False, "Last lines of a recipe's Docker Compose output.", {"recipe_id": "required", "lines": "default 40"}),
    "DeployRecipe": ("write", False,
                     "Starts a recipe on local Docker and waits for RUNNING or FAILED. A default port that is already "
                     "taken is moved to a free one and reported; a port you set that is taken is refused.",
                     {"recipe_id": "required", "vars": "object of the recipe's variables", "wait_seconds": "default 90"}),
    "TeardownRecipe": ("write", True, "Stops the recipe and removes its containers AND volumes (its data).",
                       {"recipe_id": "required", "wait_seconds": "default 60"}),
}

# Recipe -> botocore service(s) Floci may emulate in its place. Whether Floci answers is checked
# live (see native_for); this table only says what to ask.
AWS_EQUIVALENT = {
    "postgres": ["rds"], "mysql": ["rds"], "pgadmin": ["rds"], "mongodb": ["docdb"], "redis": ["elasticache"],
    "kafka": ["kafka"], "redpanda": ["kafka"], "rabbitmq": ["mq"], "minio": ["s3"], "s3-admin": ["s3"],
    "dynamodb-admin": ["dynamodb"], "elasticsearch": ["opensearch"], "meilisearch": ["opensearch"],
    "weaviate": ["opensearch"], "qdrant": ["opensearch"], "mailpit": ["ses"], "vault": ["secretsmanager", "kms"],
    "airflow": ["mwaa"], "iotcore": ["iot"], "keycloak": ["cognito-idp"], "nats": ["sns", "sqs"],
    "transfer": ["transfer"], "portainer": ["ecs", "eks"], "loki": ["logs"], "jaeger": ["xray"],
    "ollama": ["bedrock"], "observability": ["amp", "grafana"],
}

_native_cache: dict[str, str] | None = None


def verdict(operation: str) -> Verdict | None:
    entry = OPERATIONS.get(operation)
    if entry is None:
        return None
    kind, destructive, _, _ = entry
    return Verdict(kind, destructive, False, "recipe operation")


def resolve(operation: str) -> str | None:
    flat = re.sub(r"[^a-z0-9]", "", operation.lower())
    return next((n for n in OPERATIONS if n.lower() == flat), None)


def describe(operation: str) -> dict | None:
    name = resolve(operation)
    if name is None:
        return None
    kind, destructive, summary, params = OPERATIONS[name]
    return {
        "cloud": "recipes", "service": "marketplace", "operation": name, "kind": kind, "destructive": destructive,
        "summary": summary, "params": params, "call_with": "call_read" if kind == "read" else "call_write",
    }


# ------------------------------------------------------------------ ports
def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def free_port(start: int, taken: set[int]) -> int:
    for port in range(start, min(start + 200, 65535)):
        if port not in taken and not port_busy(port):
            return port
    raise RuntimeError(f"No free port found from {start}")


def _is_port(variable: dict) -> bool:
    key = variable["key"].upper()
    return (key.endswith("PORT") or "_PORT_" in key) and str(variable.get("default", "")).isdigit()


def render_url(recipe: dict, variables: dict) -> str | None:
    url = recipe.get("accessUrl")
    if not url:
        return None
    return re.sub(r"{{(\w+)}}", lambda m: str(variables.get(m.group(1), m.group(0))), url)


# ---------------------------------------------------------------- backend
async def _backend(method: str, path: str, json_data: dict | None = None) -> Any:
    from tools._client import backend
    return await backend(method, path, json_data=json_data)


async def _recipes() -> list[dict]:
    return (await _backend("GET", "/api/marketplace/recipes")).get("recipes", [])


async def _installations() -> dict:
    return (await _backend("GET", "/api/marketplace/installations")).get("installations", {})


def native_for(recipes: list[dict]) -> dict[str, str]:
    """recipe id -> 'rds' etc. for the recipes whose AWS equivalent Floci answers right now. Cached."""
    global _native_cache
    if _native_cache is None:
        from floci_generic import catalog
        from floci_generic.gateway import probe_aws

        wanted = sorted({s for r in recipes for s in AWS_EQUIVALENT.get(r["id"], []) if catalog.has_aws_service(s)})
        answering = {s for s, v in probe_aws(wanted).items() if v == "answers"} if wanted else set()
        _native_cache = {
            r["id"]: "+".join(AWS_EQUIVALENT[r["id"]])
            for r in recipes
            if r["id"] in AWS_EQUIVALENT and all(s in answering for s in AWS_EQUIVALENT[r["id"]])
        }
    return _native_cache


def _summary(recipe: dict, native: dict[str, str]) -> dict:
    out = {"id": recipe["id"], "name": recipe.get("name"), "about": (recipe.get("description") or "")[:140],
           "aws": (recipe.get("aws") or {}).get("service")}
    if recipe["id"] in native:
        out["floci_native"] = native[recipe["id"]]
    return out


# ------------------------------------------------------------------ calls
async def call(operation: str, params: dict) -> dict:
    name = resolve(operation)
    if name is None:
        return {"error": f"Unknown recipe operation {operation!r}. Use one of {', '.join(OPERATIONS)}."}
    try:
        return await _HANDLERS[name](params or {})
    except Exception as exc:  # noqa: BLE001  BackendError, docker problems...
        return {"error": f"{type(exc).__name__}: {exc}"[:600]}


async def _list(params: dict) -> dict:
    recipes = await _recipes()
    native = await asyncio.to_thread(native_for, recipes)
    query = str(params.get("query", "")).lower().strip()
    rows = [_summary(r, native) for r in recipes
            if not query or query in f"{r['id']} {r.get('name', '')} {r.get('description', '')} {(r.get('aws') or {}).get('service', '')}".lower()]
    return {"count": len(rows), "recipes": sorted(rows, key=lambda r: r["id"]),
            "hint": "floci_native means Floci emulates the AWS service this recipe stands in for; prefer it unless you need the real engine."}


async def _find(recipe_id: str) -> dict | None:
    return next((r for r in await _recipes() if r.get("id") == recipe_id), None)


async def _get(params: dict) -> dict:
    recipe = await _find(str(params.get("recipe_id", "")))
    if recipe is None:
        return {"error": f"Unknown recipe {params.get('recipe_id')!r}. Use ListRecipes."}
    native = await asyncio.to_thread(native_for, await _recipes())
    return {**_summary(recipe, native), "version": recipe.get("version"), "accessUrl": recipe.get("accessUrl"),
            "variables": [{k: v[k] for k in ("key", "default", "type", "description") if k in v} for v in recipe.get("variables", [])],
            "aws_parity": (recipe.get("aws") or {}).get("parity")}


async def _status(params: dict) -> dict:
    installed = await _installations()
    recipes = {r["id"]: r for r in await _recipes()}
    rows = {}
    for rid, inst in installed.items():
        if params.get("recipe_id") and rid != params["recipe_id"]:
            continue
        rows[rid] = {"status": inst.get("status"), "error": inst.get("error"),
                     "access_url": render_url(recipes.get(rid, {}), inst.get("vars", {})) if inst.get("status") == "RUNNING" else None}
    return {"installed": rows}


async def _logs(params: dict) -> dict:
    rid = str(params.get("recipe_id", ""))
    if not rid:
        return {"error": "recipe_id is required."}
    lines = (await _backend("GET", f"/api/marketplace/recipes/{rid}/logs")).get("logs", [])
    return {"recipe_id": rid, "lines": lines[-int(params.get("lines", 40)):]}


async def _wait(recipe_id: str, until: set[str], seconds: float) -> dict | None:
    deadline = asyncio.get_event_loop().time() + seconds
    while True:
        inst = (await _installations()).get(recipe_id)
        status = inst.get("status") if inst else "IDLE"
        if status in until or asyncio.get_event_loop().time() >= deadline:
            return inst or {"status": "IDLE"}
        await asyncio.sleep(1)


async def _deploy(params: dict) -> dict:
    rid = str(params.get("recipe_id", ""))
    recipe = await _find(rid)
    if recipe is None:
        return {"error": f"Unknown recipe {rid!r}. Use ListRecipes."}
    given = dict(params.get("vars") or {})
    known = {v["key"] for v in recipe.get("variables", [])}
    unknown = sorted(set(given) - known)
    if unknown:
        return {"error": f"Unknown variable(s) {unknown} for {rid}. Known: {sorted(known)}."}

    send: dict[str, Any] = {}
    adjusted: dict[str, dict] = {}
    taken: set[int] = set()
    for variable in recipe.get("variables", []):
        key = variable["key"]
        if _is_port(variable):
            wanted = int(given.get(key, variable["default"]))
            if wanted in taken or port_busy(wanted):
                if key in given:
                    return {"error": f"Port {wanted} ({key}) is already in use.",
                            "suggestion": {key: free_port(wanted + 1, taken)}}
                moved = free_port(wanted + 1, taken)
                adjusted[key] = {"default": wanted, "using": moved}
                wanted = moved
            taken.add(wanted)
            send[key] = wanted
        elif key in given:
            send[key] = given[key]

    await _backend("POST", "/api/marketplace/install", {"recipeId": rid, "vars": send})
    final = await _wait(rid, {"RUNNING", "FAILED"}, float(params.get("wait_seconds", 90)))
    values = {**{v["key"]: v.get("default") for v in recipe.get("variables", [])}, **(final.get("vars") or send)}
    out: dict[str, Any] = {"recipe_id": rid, "status": final.get("status"), "access_url": render_url(recipe, values)}
    if adjusted:
        out["ports_adjusted"] = adjusted
    if final.get("status") == "FAILED":
        out["error"] = final.get("error")
        out["log_tail"] = (await _logs({"recipe_id": rid, "lines": 15}))["lines"]
    elif final.get("status") != "RUNNING":
        out["note"] = "Still installing; call GetStatus to follow it."
        out["access_url"] = None
    return out


async def _teardown(params: dict) -> dict:
    rid = str(params.get("recipe_id", ""))
    if await _find(rid) is None:
        return {"error": f"Unknown recipe {rid!r}. Use ListRecipes."}
    await _backend("DELETE", f"/api/marketplace/install/{rid}")
    final = await _wait(rid, {"IDLE", "FAILED"}, float(params.get("wait_seconds", 60)))
    out = {"recipe_id": rid, "status": final.get("status")}
    if final.get("status") == "FAILED":
        out["error"] = final.get("error")
    return out


_HANDLERS = {
    "ListRecipes": _list, "GetRecipe": _get, "GetStatus": _status, "GetLogs": _logs,
    "DeployRecipe": _deploy, "TeardownRecipe": _teardown,
}
