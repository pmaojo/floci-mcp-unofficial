"""What can be called: AWS from the botocore service models, the other clouds from a route table.

AWS has a machine-readable model for every service, so the catalog is complete by
construction and follows boto3 releases. Azure, GCP and OCI have no such model
offline, so their catalog lists the routes known to work against Floci and
`request` reaches any other path of the runtime.
"""
import functools
import html
import json
import math
import os
import re
from collections import Counter

import botocore.session

from floci_generic import recipes as recipes_module
from floci_generic.classify import Verdict, classify_aws, classify_rest, split_name

CLOUDS = ("aws", "azure", "gcp", "oci", "recipes")
REST_PROTOCOLS = {"rest-json", "rest-xml"}

# Services Floci lists for each non-AWS cloud (its README). Route shapes follow the provider's
# real REST contract; only the ones in REST_ROUTES have been checked against the runtime.
REST_SERVICES = {
    "azure": [
        "blob", "queue", "keyvault", "table", "functions", "appconfiguration", "cosmosdb", "eventhubs",
        "servicebus", "sql", "postgresql", "mysql", "mariadb", "aks", "containerapps", "apim",
        "virtualnetwork", "vm", "redis", "acr", "aci", "eventgrid", "monitor", "email",
        "managedidentity", "policy", "signalr",
    ],
    "gcp": [
        "storage", "pubsub", "secretmanager", "firestore", "datastore", "managedkafka", "eventarc",
        "kms", "iam", "sts", "firebaseauth", "gke", "compute", "cloudrun", "cloudfunctions",
        "cloudtasks", "scheduler", "cloudsql", "bigquery", "logging", "monitoring",
    ],
    "oci": [
        "objectstorage", "identity", "queue", "streaming", "vault", "secrets", "functions", "oke",
    ],
}

# (service, operation, method, path template, summary). {name} in the path comes from params;
# anything else in params goes to the query string (GET) or the JSON body.
REST_ROUTES = {
    "gcp": [
        ("storage", "ListBuckets", "GET", "/storage/v1/b?project={project}", "Lists Cloud Storage buckets"),
        ("storage", "CreateBucket", "POST", "/storage/v1/b?project={project}", "Creates a bucket; body {name}"),
        ("storage", "ListObjects", "GET", "/storage/v1/b/{bucket}/o", "Lists objects; optional prefix"),
        ("pubsub", "ListTopics", "GET", "/v1/projects/{project}/topics", "Lists Pub/Sub topics"),
        ("pubsub", "CreateTopic", "PUT", "/v1/projects/{project}/topics/{topic}", "Creates a topic"),
        ("secretmanager", "ListSecrets", "GET", "/v1/projects/{project}/secrets", "Lists secret names"),
    ],
    "azure": [
        ("blob", "ListContainers", "GET", "/{account}?comp=list", "Lists blob containers"),
        ("blob", "CreateContainer", "PUT", "/{account}/{container}?restype=container", "Creates a container"),
        ("blob", "DeleteContainer", "DELETE", "/{account}/{container}?restype=container", "Deletes a container and its blobs"),
        ("blob", "ListBlobs", "GET", "/{account}/{container}?restype=container&comp=list", "Lists blobs; optional prefix"),
        ("queue", "ListQueues", "GET", "/{account}-queue?comp=list", "Lists queues"),
        ("queue", "CreateQueue", "PUT", "/{account}-queue/{queue}", "Creates a queue"),
        ("queue", "DeleteQueue", "DELETE", "/{account}-queue/{queue}", "Deletes a queue and its messages"),
        ("table", "ListTables", "GET", "/{account}-table/Tables", "Lists tables"),
        ("keyvault", "ListSecrets", "GET", "/{account}-keyvault/secrets?api-version=7.4", "Lists secret ids"),
    ],
    "oci": [
        ("objectstorage", "GetNamespace", "GET", "/n/", "Returns the Object Storage namespace"),
        ("objectstorage", "ListBuckets", "GET", "/n/{namespace}/b?compartmentId={compartmentId}", "Lists buckets"),
        ("objectstorage", "CreateBucket", "POST", "/n/{namespace}/b", "Creates a bucket; body {name, compartmentId}"),
        ("objectstorage", "ListObjects", "GET", "/n/{namespace}/b/{bucket}/o", "Lists objects; optional prefix"),
        ("objectstorage", "DeleteBucket", "DELETE", "/n/{namespace}/b/{bucket}", "Deletes an empty bucket"),
    ],
}

REST_HINTS = {
    "azure": "Data plane: /{account}[-queue|-keyvault]/... with comp=, restype= query parameters. Responses are XML for Blob and Queue.",
    "gcp": "Google REST: /storage/v1/b/..., /v1/projects/{project}/topics|secrets|... Custom methods use ':verb' suffixes.",
    "oci": "OCI REST: /n/{namespace}/b/... for Object Storage; other services use /20xxxxxx/... with compartmentId.",
}


@functools.lru_cache(maxsize=1)
def _session():
    return botocore.session.get_session()


def aws_services() -> list[str]:
    return sorted(_session().get_available_services())


@functools.lru_cache(maxsize=None)
def aws_model(service: str):
    return _session().get_service_model(service)


def has_aws_service(service: str) -> bool:
    return service in set(aws_services())


def aws_operation_names(service: str) -> list[str]:
    return list(aws_model(service).operation_names)


def aws_verdict(service: str, operation: str) -> Verdict:
    """The verdict for one operation, cross-checked with the model's HTTP method on REST protocols."""
    model = aws_model(service)
    method = None
    if model.protocol in REST_PROTOCOLS:
        method = model.operation_model(operation).http.get("method")
    return classify_aws(service, operation, method)


def resolve_aws_operation(service: str, operation: str) -> str | None:
    """Accepts ListBuckets, list_buckets or listbuckets and returns the model's name."""
    names = aws_operation_names(service)
    if operation in names:
        return operation
    flat = re.sub(r"[^a-z0-9]", "", operation.lower())
    for name in names:
        if re.sub(r"[^a-z0-9]", "", name.lower()) == flat:
            return name
    return None


def _plain(text: str, limit: int = 240) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _signature(shape, depth: int = 2) -> str:
    """A compact type. Shapes can be recursive (DynamoDB's AttributeValue), so depth is a hard stop."""
    kind = shape.type_name
    if depth <= 0:
        return "object" if kind == "structure" else kind
    if kind == "structure":
        required = set(shape.required_members)
        inner = ", ".join(f"{n}{'*' if n in required else ''}: {_signature(m, depth - 1)}" for n, m in shape.members.items())
        return "{" + inner + "}"
    if kind == "list":
        return f"[{_signature(shape.member, depth - 1)}]"
    if kind == "map":
        return f"map<{_signature(shape.key, 0)}, {_signature(shape.value, depth - 1)}>"
    enum = getattr(shape, "enum", None)
    if enum:
        return "enum(" + "|".join(enum[:8]) + ("|…" if len(enum) > 8 else "") + ")"
    return kind


_NOTICE = re.compile(r"^(end of support|note:|important:|this (api|operation|action) (is|has been) (deprecated|replaced))", re.I)


_ACTION = re.compile(r"^[A-Z][a-z]+s\b")  # "Adds", "Retrieves", "Invokes": how most operations open


def _summary(documentation: str, limit: int = 200) -> str:
    """First useful sentence of an operation's documentation, skipping notices.

    Notices are whole paragraphs in the HTML, so the paragraph is the unit that is skipped.
    """
    paragraphs = re.findall(r"<p>(.*?)</p>", documentation or "", re.S) or [documentation or ""]
    texts = [t for t in (_plain(p, 600) for p in paragraphs) if t]
    notices = re.compile(_NOTICE.pattern + r"|^(this change|starting|as of|beginning)", re.I)
    pick = (next((t for t in texts if _ACTION.match(t) and not notices.match(t)), None)
            or next((t for t in texts if not notices.match(t)), None)
            or (texts[0] if texts else ""))
    sentence = re.split(r"(?<=[a-z0-9)])\.\s+(?=[A-Z])", pick)[0]
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rstrip() + "…"


def _short_type(sig: str, limit: int = 70) -> str:
    return sig if len(sig) <= limit else sig[: limit - 1] + "…"


def describe_aws(service: str, operation: str, detail: str = "brief") -> dict:
    """detail="brief": required parameters with their docs, optional ones by name and type only.
    detail="full": every parameter with its documentation (large for operations such as s3.PutObject)."""
    model = aws_model(service)
    op = model.operation_model(operation)
    verdict = aws_verdict(service, operation)
    required: dict = {}
    optional: dict = {}
    if op.input_shape:
        needed = set(op.input_shape.required_members)
        for name, member in op.input_shape.members.items():
            if name in needed:
                required[name] = {"type": _signature(member), "doc": _plain(member.documentation, 140)}
            elif detail == "full":
                optional[name] = {"type": _signature(member), "doc": _plain(member.documentation, 140)}
            else:
                optional[name] = _short_type(_signature(member))
    outputs = list(op.output_shape.members) if op.output_shape else []
    out = {
        "cloud": "aws", "service": service, "operation": operation,
        "kind": verdict.kind, "destructive": verdict.destructive, "sensitive": verdict.sensitive,
        "summary": _summary(op.documentation),
        "required": required, "optional": optional,
        "returns": outputs[:25] + (["…"] if len(outputs) > 25 else []),
        "call_with": "call_read" if verdict.read else "call_write",
    }
    if detail != "full" and optional:
        out["more"] = "Optional parameters are listed by name and type; describe_operation with detail='full' adds their docs."
    return out



# --------------------------------------------------------------- REST catalog
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
AZURE_SUBSCRIPTION_DEFAULT = "00000000-0000-0000-0000-000000000000"
ARM = "/subscriptions/{subscription}"
ARM_RG = ARM + "/resourceGroups/{resourceGroup}"


def _hand(cloud: str) -> dict[str, list[dict]]:
    """The routes written by hand (Azure data plane, OCI Object Storage), in the catalog's shape."""
    out: dict[str, list[dict]] = {}
    for svc, name, method, path, summary in REST_ROUTES.get(cloud, []):
        params = {p: {"in": "path", "required": True, "type": "string"} for p in re.findall(r"{(\w+)}", path)}
        if method in ("POST", "PUT") and "Create" in name and cloud == "oci":
            params["body"] = {"in": "body", "required": False, "type": "object"}
        out.setdefault(svc, []).append({"name": name, "id": f"{svc}.{name}", "method": method, "path": path,
                                        "params": params, "summary": summary, "verified": True})
    return out


def _load(cloud: str):
    try:
        with open(os.path.join(DATA_DIR, f"{cloud}.json")) as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None


def _arm_ops(data: dict) -> dict[str, list[dict]]:
    sub = {"subscription": {"in": "path", "required": False, "type": "string"}}
    rg = {**sub, "resourceGroup": {"in": "path", "required": True, "type": "string"}}
    body = {"body": {"in": "body", "required": True, "type": "object"}}
    ops: dict[str, list[dict]] = {"arm": [
        {"name": "ListSubscriptions", "method": "GET", "path": "/subscriptions?api-version=2020-01-01", "params": {}, "summary": "Lists subscriptions", "verified": True},
        {"name": "ListResourceGroups", "method": "GET", "path": ARM + "/resourcegroups?api-version=2021-04-01", "params": sub, "summary": "Lists resource groups", "verified": True},
        {"name": "CreateResourceGroup", "method": "PUT", "path": ARM_RG.replace("resourceGroups", "resourcegroups") + "?api-version=2021-04-01", "params": {**rg, **body}, "summary": "Creates a resource group; body {location}"},
        {"name": "DeleteResourceGroup", "method": "DELETE", "path": ARM_RG.replace("resourceGroups", "resourcegroups") + "?api-version=2021-04-01", "params": rg, "summary": "Deletes a resource group and everything in it"},
    ]}
    for entry in data.get("arm_types", []):
        type_, version = entry["type"], entry["api_version"]
        noun = type_.split("/")[-1]
        plural = noun[:1].upper() + noun[1:]
        singular = plural[:-1] if plural.endswith("s") and not plural.endswith("ss") else plural
        item = {"name": {"in": "path", "required": True, "type": "string"}}
        ops.setdefault(entry["service"], []).extend([
            {"name": f"List{plural}", "method": "GET", "path": f"{ARM}/providers/{type_}?api-version={version}", "params": sub, "summary": f"Lists {type_}", "verified": True},
            {"name": f"Get{singular}", "method": "GET", "path": f"{ARM_RG}/providers/{type_}/{{name}}?api-version={version}", "params": {**rg, **item}, "summary": f"Returns one {type_}", "verified": True},
            {"name": f"Put{singular}", "method": "PUT", "path": f"{ARM_RG}/providers/{type_}/{{name}}?api-version={version}", "params": {**rg, **item, **body}, "summary": f"Creates or updates a {type_}"},
            {"name": f"Delete{singular}", "method": "DELETE", "path": f"{ARM_RG}/providers/{type_}/{{name}}?api-version={version}", "params": {**rg, **item}, "summary": f"Deletes a {type_}"},
        ])
    return ops


@functools.lru_cache(maxsize=None)
def rest_ops(cloud: str) -> dict[str, list[dict]]:
    """service -> operations for azure, gcp and oci: hand-written routes plus the generated catalog."""
    ops = _hand(cloud)
    data = _load(cloud)
    if data:
        if cloud == "azure":
            for svc, items in _arm_ops(data).items():
                ops.setdefault(svc, []).extend(items)
        else:
            for svc, items in data.items():
                known = {o["name"].lower() for o in ops.get(svc, [])}
                ops.setdefault(svc, []).extend(o for o in items if o["name"].lower() not in known)
    for items in ops.values():
        for op in items:
            op.setdefault("id", op["name"])
    return ops


def find_rest_op(cloud: str, service: str, operation: str) -> dict | None:
    wanted = operation.lower()
    for op in rest_ops(cloud).get(service, []):
        if op["name"].lower() == wanted or op.get("id", "").lower() == wanted:
            return op
    return None

def describe_rest(cloud: str, service: str, operation: str) -> dict | None:
    op = find_rest_op(cloud, service, operation)
    if op is None:
        return None
    verdict = classify_rest(cloud, op["method"], op["path"])
    params = {}
    for name, spec in op["params"].items():
        required = spec.get("required", False) and name not in DEFAULTS
        note = "default from FLOCI_* when omitted" if name in DEFAULTS else ""
        params[name] = {"in": spec.get("in", "path"), "required": required, "type": spec.get("type", "string"), **({"note": note} if note else {})}
    out = {
        "cloud": cloud, "service": service, "operation": op["name"], "method": op["method"], "path": op["path"],
        "kind": verdict.kind, "destructive": verdict.destructive, "sensitive": verdict.sensitive,
        "summary": op.get("summary", ""), "params": params,
        "call_with": "call_read" if verdict.read else "call_write",
    }
    if "verified" in op:
        out["verified_on_floci"] = op["verified"]
    return out


# Placeholders that have a configured default (see floci_generic.invoke).
DEFAULTS = {"project", "projectId", "projectsId", "projectNumber", "parent", "location", "locationsId", "region", "zone",
            "account", "compartmentId", "namespace", "subscription"}


def list_services(cloud: str) -> list[dict]:
    if cloud == "recipes":
        return [{"name": "marketplace", "described_operations": len(recipes_module.OPERATIONS)}]
    if cloud == "aws":
        return [{"name": s} for s in aws_services()]
    ops = rest_ops(cloud)
    names = list(ops) + [n for n in REST_SERVICES[cloud] if n not in ops]
    return [{"name": n, "operations": len(ops.get(n, [])),
             "verified": sum(1 for o in ops.get(n, []) if o.get("verified"))} for n in names]


# --------------------------------------------------------------------------- search
def _stem(token: str) -> str:
    """messages -> message, queues -> queue, policies -> policy. Crude on purpose."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def _tokens(text: str) -> list[str]:
    return [_stem(t) for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


class _BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.avg = sum(len(d) for d in docs) / max(len(docs), 1)
        df: Counter = Counter()
        for doc in docs:
            df.update(set(doc))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in docs]

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for doc, tf in zip(self.docs, self.tf):
            score = 0.0
            for term in query:
                freq = tf.get(term)
                if freq:
                    norm = freq + self.k1 * (1 - self.b + self.b * len(doc) / self.avg)
                    score += self.idf.get(term, 0.0) * freq * (self.k1 + 1) / norm
            out.append(score)
        return out


# Plain-English verbs a user writes, mapped to the verbs APIs use.
_SYNONYMS = {
    "show": ["list", "describe", "get"], "see": ["list", "describe", "get"], "find": ["list", "search", "describe"],
    "which": ["list"], "all": ["list"], "read": ["get", "list", "receive"], "fetch": ["get"], "inspect": ["describe", "get"],
    "make": ["create"], "new": ["create"], "add": ["create", "put"], "remove": ["delete"], "drop": ["delete"],
    "upload": ["put"], "store": ["put", "create"], "write": ["put"], "run": ["start", "invoke", "execute"],
    "call": ["invoke"], "publish": ["publish", "send"], "send": ["send", "publish"], "tag": ["tag"],
    "bucket": ["bucket", "s3"], "queue": ["queue", "sqs"], "topic": ["topic", "sns"],
    "secret": ["secret", "secretsmanager"], "function": ["function", "lambda"], "table": ["table", "dynamodb"],
    "email": ["email", "ses"], "key": ["key", "kms"], "file": ["object"], "text": ["object"],
    "eventbridge": ["events", "rule"], "cloudwatch": ["logs"], "log": ["logs"],
}


def _expand(query: str) -> list[str]:
    out: list[str] = []
    for token in _tokens(query):
        for t in [token, *(_stem(x) for x in _SYNONYMS.get(token, []))]:
            if t not in out:
                out.append(t)
    return out


def _first_sentence(service: str, operation: str) -> str:
    """The opening of the operation's documentation: it carries words the name does not ("tagged", "queue")."""
    text = _plain(aws_model(service).operation_model(operation).documentation, 160)
    return text.split(". ")[0]


def _entries(cloud: str, service: str | None) -> list[dict]:
    entries = []
    if cloud == "aws":
        services = [service] if service else aws_services()
        for svc in services:
            if not has_aws_service(svc):
                continue
            for op in aws_operation_names(svc):
                entries.append({"cloud": "aws", "service": svc, "operation": op, "name_tokens": [_stem(t) for t in split_name(op)],
                                "text": f"{svc} {svc} " + " ".join(split_name(op) * 2) + " " + _first_sentence(svc, op)})
    elif cloud == "recipes":
        for name, (kind, _, summary, _) in recipes_module.OPERATIONS.items():
            entries.append({"cloud": cloud, "service": "marketplace", "operation": name, "summary": summary, "kind": kind,
                            "name_tokens": [_stem(t) for t in split_name(name)],
                            "text": f"recipe recipes marketplace docker local stack {' '.join(split_name(name))} {summary}"})
    else:
        for svc, items in rest_ops(cloud).items():
            if service and svc != service:
                continue
            for op in items:
                words = split_name(op["name"]) if "." not in op["name"] else [w for part in op["name"].split(".") for w in split_name(part)]
                entries.append({"cloud": cloud, "service": svc, "operation": op["name"], "summary": op.get("summary", ""),
                                "method": op["method"], "path": op["path"], "name_tokens": [_stem(t) for t in words],
                                "text": f"{svc} {svc} {' '.join(words * 2)} {op.get('summary', '')} {op['path']}"})
    return entries


@functools.lru_cache(maxsize=16)
def _index(cloud: str, service: str | None):
    entries = _entries(cloud, service)
    return entries, _BM25([_tokens(e["text"]) for e in entries])


def search(query: str, cloud: str = "aws", service: str | None = None, limit: int = 8) -> list[dict]:
    entries, index = _index(cloud, service)
    expanded = _expand(query)
    scores = index.scores(expanded)
    wanted = set(expanded)
    flat = "".join(_tokens(query))
    # Prefer the operation whose whole name the query covers: "invoke a function" means Invoke, not
    # PutFunctionEventInvokeConfig.
    for i, entry in enumerate(entries):
        words = entry["name_tokens"]
        scores[i] *= 0.4 + 0.6 * (sum(w in wanted for w in words) / max(len(words), 1))
        # The person named the service ("an athena query", "step functions"): that is the strongest signal.
        svc = entry["service"].replace("-", "")
        if svc in wanted or _stem(svc) in wanted or (len(svc) >= 6 and svc in flat):
            scores[i] *= 2.5
    ranked = sorted(range(len(entries)), key=lambda i: -scores[i])[:limit]
    out = []
    for i in ranked:
        if scores[i] <= 0:
            break
        e = entries[i]
        if cloud == "aws":
            v = aws_verdict(e["service"], e["operation"])
            out.append({"service": e["service"], "operation": e["operation"], "kind": v.kind})
        elif cloud == "recipes":
            out.append({"service": e["service"], "operation": e["operation"], "kind": e["kind"], "summary": e["summary"][:100]})
        else:
            v = classify_rest(cloud, e["method"], "")
            out.append({"service": e["service"], "operation": e["operation"], "kind": v.kind, "summary": e["summary"]})
    return out
