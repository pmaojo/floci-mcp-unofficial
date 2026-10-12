"""The recipe catalog as a cloud: its operations, how they are classified, and how a deploy is planned.

Nothing here touches Docker, the network or the disk. The runtime that does is a port.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from floci_generic.domain.classify import Verdict

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
# live; this table only says what to ask.
AWS_EQUIVALENT = {
    "postgres": ["rds"], "mysql": ["rds"], "pgadmin": ["rds"], "mongodb": ["docdb"], "redis": ["elasticache"],
    "kafka": ["kafka"], "redpanda": ["kafka"], "rabbitmq": ["mq"], "minio": ["s3"], "s3-admin": ["s3"],
    "dynamodb-admin": ["dynamodb"], "elasticsearch": ["opensearch"], "meilisearch": ["opensearch"],
    "weaviate": ["opensearch"], "qdrant": ["opensearch"], "mailpit": ["ses"], "vault": ["secretsmanager", "kms"],
    "airflow": ["mwaa"], "iotcore": ["iot"], "keycloak": ["cognito-idp"], "nats": ["sns", "sqs"],
    "transfer": ["transfer"], "portainer": ["ecs", "eks"], "loki": ["logs"], "jaeger": ["xray"],
    "ollama": ["bedrock"], "observability": ["amp", "grafana"],
}


def verdict(operation: str) -> Verdict | None:
    """The classification of a recipe operation, from the table (not from its verb)."""
    entry = OPERATIONS.get(operation)
    if entry is None:
        return None
    kind, destructive, _, _ = entry
    return Verdict(kind, destructive, False, "recipe operation")


def resolve(operation: str) -> str | None:
    """ListRecipes, list_recipes and listrecipes all name the same operation."""
    flat = re.sub(r"[^a-z0-9]", "", operation.lower())
    return next((n for n in OPERATIONS if n.lower() == flat), None)


def describe(operation: str) -> dict | None:
    """What an agent needs to know before calling a recipe operation."""
    name = resolve(operation)
    if name is None:
        return None
    kind, destructive, summary, params = OPERATIONS[name]
    return {
        "cloud": "recipes", "service": "marketplace", "operation": name, "kind": kind, "destructive": destructive,
        "summary": summary, "params": params, "call_with": "call_read" if kind == "read" else "call_write",
    }


def native_candidates(recipes: list[dict]) -> list[str]:
    """The AWS services worth asking Floci about for these recipes."""
    wanted: set[str] = set()
    for recipe in recipes:
        wanted.update(AWS_EQUIVALENT.get(recipe["id"], []))
    return sorted(wanted)


def native_ids(recipes: list[dict], answering: set[str]) -> dict[str, str]:
    """recipe id -> 'rds' etc., for the recipes whose every AWS equivalent answers."""
    return {
        r["id"]: "+".join(AWS_EQUIVALENT[r["id"]])
        for r in recipes
        if r["id"] in AWS_EQUIVALENT and all(s in answering for s in AWS_EQUIVALENT[r["id"]])
    }


def summarize(recipe: dict, native: dict[str, str]) -> dict:
    """One row of ListRecipes."""
    out = {"id": recipe["id"], "name": recipe.get("name"), "about": (recipe.get("description") or "")[:140],
           "aws": (recipe.get("aws") or {}).get("service")}
    if recipe["id"] in native:
        out["floci_native"] = native[recipe["id"]]
    return out


def matches(recipe: dict, query: str) -> bool:
    """Whether a free-text filter matches a recipe (an empty filter matches all)."""
    haystack = f"{recipe['id']} {recipe.get('name', '')} {recipe.get('description', '')} {(recipe.get('aws') or {}).get('service', '')}"
    return not query or query.lower() in haystack.lower()


def render_url(recipe: dict, variables: dict) -> str | None:
    """The recipe's access URL with its variables filled in."""
    url = recipe.get("accessUrl")
    if not url:
        return None
    return re.sub(r"{{(\w+)}}", lambda m: str(variables.get(m.group(1), m.group(0))), url)


def is_port(variable: dict) -> bool:
    """Whether a recipe variable is a TCP port on the host."""
    key = variable["key"].upper()
    return (key.endswith("PORT") or "_PORT_" in key) and str(variable.get("default", "")).isdigit()


def next_free_port(start: int, taken: set[int], is_busy: Callable[[int], bool]) -> int:
    """The first port from `start` that is neither taken in this plan nor busy on the host."""
    for port in range(start, min(start + 200, 65535)):
        if port not in taken and not is_busy(port):
            return port
    raise RuntimeError(f"No free port found from {start}")


@dataclass
class DeployPlan:
    """The variables to send, the ports that were moved, or why the deploy cannot start."""

    send: dict[str, Any] = field(default_factory=dict)
    adjusted: dict[str, dict] = field(default_factory=dict)
    error: dict | None = None


def _plan_port(variable: dict, given: dict, taken: set[int], is_busy: Callable[[int], bool], plan: DeployPlan) -> None:
    key = variable["key"]
    wanted = int(given.get(key, variable["default"]))
    if wanted in taken or is_busy(wanted):
        if key in given:
            plan.error = {"error": f"Port {wanted} ({key}) is already in use.",
                          "suggestion": {key: next_free_port(wanted + 1, taken, is_busy)}}
            return
        moved = next_free_port(wanted + 1, taken, is_busy)
        plan.adjusted[key] = {"default": wanted, "using": moved}
        wanted = moved
    taken.add(wanted)
    plan.send[key] = wanted


def plan_deploy(recipe: dict, given: dict, is_busy: Callable[[int], bool]) -> DeployPlan:
    """Decide the variables of a deploy: validate names, move taken default ports, refuse taken chosen ones."""
    plan = DeployPlan()
    known = {v["key"] for v in recipe.get("variables", [])}
    unknown = sorted(set(given) - known)
    if unknown:
        plan.error = {"error": f"Unknown variable(s) {unknown} for {recipe['id']}. Known: {sorted(known)}."}
        return plan
    taken: set[int] = set()
    for variable in recipe.get("variables", []):
        if is_port(variable):
            _plan_port(variable, given, taken, is_busy, plan)
            if plan.error:
                return plan
        elif variable["key"] in given:
            plan.send[variable["key"]] = given[variable["key"]]
    return plan
