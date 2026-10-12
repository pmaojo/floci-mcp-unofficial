"""Read/write classification of cloud operations.

The generic tools can reach every operation of every service, so "is this a read"
has to be answered by rules that can be tested, not by a name list that someone
must keep up to date. The default is write: an operation is a read only when its
verb says so and nothing in its name or protocol contradicts it.

AWS     classified by operation name, cross-checked against the botocore model
        (REST protocols declare an HTTP method; a read verb on PUT/DELETE/PATCH is a write).
Others  classified by HTTP method (Azure, GCP and OCI are REST), with a short
        list of POST-based reads.
"""
import re
from dataclasses import dataclass

READ_VERBS = {
    "list", "describe", "get", "head", "search", "lookup", "query", "scan", "check", "estimate",
    "preview", "view", "retrieve", "validate",
    # Stateless computations over what is already there.
    "count", "is", "select", "filter", "compare", "calculate", "forecast", "geocode", "decode",
}
# BatchGetItem is a read, BatchWriteItem is not: the word after "batch" decides.
BATCH_READ_VERBS = {"get", "describe", "list"}

# GetOrCreate*, DescribeAndStop*: a joiner right after the verb followed by a mutating word.
JOINERS = {"or", "and"}
MUTATING_WORDS = {
    "create", "delete", "put", "update", "start", "stop", "invoke", "send", "publish", "execute",
    "run", "enable", "disable", "attach", "detach", "associate", "disassociate", "cancel",
    "terminate", "reset", "rotate", "restore", "import", "register", "deregister", "tag", "untag",
    "write", "set", "add", "remove", "modify", "replace", "apply", "authorize", "revoke", "grant",
    "accept", "reject", "approve", "deny", "upload", "copy", "move", "purge", "redrive", "restart",
    "reboot", "deploy", "rollback", "subscribe", "unsubscribe", "confirm", "initiate", "complete",
    "abort", "lock", "unlock",
}

DESTRUCTIVE_VERBS = {
    "delete", "remove", "terminate", "purge", "destroy", "deregister", "detach", "disassociate",
    "revoke", "cancel", "stop", "drop", "truncate", "untag", "unsubscribe", "deactivate", "abort",
    "discard", "clear", "erase", "reset", "disable", "redrive",
}

# Operations whose verb looks like a read and whose effect is not (reviewed by hand).
READ_VERB_BUT_WRITES = {
    ("cognito-identity", "GetId"): "creates the identity when it does not exist",
    ("cognito-identity", "GetOpenIdToken"): "issues a token for the identity",
    ("cognito-identity", "GetCredentialsForIdentity"): "issues credentials",
    ("sts", "GetFederationToken"): "issues credentials",
    ("sts", "GetSessionToken"): "issues credentials",
}

# Operations that do not start with a read verb and are reads all the same.
READ_BY_NAME = {
    ("dynamodb", "Query"), ("dynamodb", "Scan"),
    ("s3", "SelectObjectContent"),
    ("kms", "GenerateRandom"), ("sts", "DecodeAuthorizationMessage"),
    ("iam", "SimulatePrincipalPolicy"), ("iam", "SimulateCustomPolicy"),
}

# Reads that return secret material. Still reads, but the verdict flags them.
SENSITIVE = {
    ("secretsmanager", "GetSecretValue"), ("secretsmanager", "BatchGetSecretValue"),
    ("ssm", "GetParameter"), ("ssm", "GetParameters"), ("ssm", "GetParametersByPath"),
}

_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+")

# POST calls that only read, per cloud. Matched against the path without its query string.
REST_POST_READS = {
    "gcp": re.compile(r":(list|get|batchGet|runQuery|search|lookup|testIamPermissions|aggregate|listCollectionIds|access)$"),
    "azure": re.compile(r"/(providers/Microsoft\.ResourceGraph/resources|checkNameAvailability)$"),
    "oci": re.compile(r"/search/resources$"),
}
REST_READ_METHODS = {"GET", "HEAD", "OPTIONS"}
# Reads that return secret material, per cloud (matched against the path without its query string).
REST_SENSITIVE = re.compile(
    r"(:access$|/listKeys$|/listConnectionStrings$|/listSecrets$|/secretbundles/|-keyvault/secrets/[^/]+(/[^/]+)?$|/secrets/[^/]+/versions/[^/]+:access$)"
)
# Many REST services list and describe with POST (a body carries the filter), so for AWS a read
# verb is only contradicted by a method that replaces or removes: PUT, DELETE, PATCH.
AWS_READ_HTTP_METHODS = REST_READ_METHODS | {"POST"}


@dataclass(frozen=True)
class Verdict:
    kind: str  # "read" or "write"
    destructive: bool
    sensitive: bool
    reason: str

    @property
    def read(self) -> bool:
        return self.kind == "read"


def split_name(operation: str) -> list[str]:
    """GetObjectLockConfiguration -> ['get', 'object', 'lock', 'configuration']"""
    return [t.lower() for t in _CAMEL.findall(operation)]


def classify_aws(service: str, operation: str, http_method: str | None = None) -> Verdict:
    tokens = split_name(operation)
    verb = tokens[0] if tokens else ""
    key = (service, operation)
    destructive = verb in DESTRUCTIVE_VERBS or (verb == "batch" and len(tokens) > 1 and tokens[1] in DESTRUCTIVE_VERBS)

    if key in READ_VERB_BUT_WRITES:
        return Verdict("write", destructive, False, READ_VERB_BUT_WRITES[key])
    if key in READ_BY_NAME:
        return Verdict("read", False, key in SENSITIVE, "reviewed read")

    effective = tokens[1] if verb == "batch" and len(tokens) > 1 else verb
    allowed = BATCH_READ_VERBS if verb == "batch" else READ_VERBS
    if effective not in allowed:
        return Verdict("write", destructive, False, f"verb {effective!r} is not a read verb")

    if len(tokens) > 2 and tokens[1] in JOINERS and any(t in MUTATING_WORDS for t in tokens[2:]):
        return Verdict("write", destructive, False, "name combines a read verb with a mutating word")

    if http_method and http_method.upper() not in AWS_READ_HTTP_METHODS:
        return Verdict("write", destructive, False, f"read-looking name but the model says HTTP {http_method.upper()}")
    return Verdict("read", False, key in SENSITIVE, "read verb")


def classify_rest(cloud: str, method: str, path: str) -> Verdict:
    method = method.upper()
    bare = path.split("?", 1)[0].rstrip("/")
    sensitive = bool(REST_SENSITIVE.search(bare))
    if method in REST_READ_METHODS:
        return Verdict("read", False, sensitive, f"HTTP {method}")
    pattern = REST_POST_READS.get(cloud)
    if method == "POST" and pattern and pattern.search(bare):
        return Verdict("read", False, sensitive, "POST that only reads")
    if method == "POST" and sensitive:
        return Verdict("write", False, False, "POST that returns secrets: treated as a write")
    return Verdict("write", method == "DELETE", False, f"HTTP {method} changes state")


def to_snake(operation: str) -> str:
    """boto3 method name of an operation: ListObjectsV2 -> list_objects_v2."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", operation)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
