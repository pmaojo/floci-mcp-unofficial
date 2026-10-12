"""The generic core: classification against every botocore model, the gateway guard and the code sandbox.

No network and no Floci needed, except the tests named test_live_*, which return early
when a runtime is not reachable. Run with pytest or `uv run python tests/test_generic.py`.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

import toolsets  # noqa: E402
from floci_generic import catalog, recipes, sandbox  # noqa: E402
from floci_generic.classify import AWS_READ_HTTP_METHODS, JOINERS, MUTATING_WORDS, classify_aws, classify_rest, split_name  # noqa: E402
from floci_generic.gateway import Blocked, Gateway  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def every_operation():
    for service in catalog.aws_services():
        model = catalog.aws_model(service)
        for name in model.operation_names:
            method = model.operation_model(name).http.get("method") if model.protocol in catalog.REST_PROTOCOLS else None
            yield service, name, method


# ------------------------------------------------------------ classification
def test_every_aws_operation_has_a_verdict():
    kinds = {"read": 0, "write": 0}
    for service, name, method in every_operation():
        verdict = classify_aws(service, name, method)
        assert verdict.kind in kinds, (service, name)
        kinds[verdict.kind] += 1
    assert kinds["read"] + kinds["write"] > 15_000
    # Default deny: writes outnumber reads. If this flips, the verb list has grown too generous.
    assert kinds["write"] > kinds["read"]


GOLDEN_READS = [
    ("s3", "ListBuckets"), ("s3", "GetObject"), ("s3", "HeadObject"), ("dynamodb", "Query"), ("dynamodb", "Scan"),
    ("dynamodb", "GetItem"), ("dynamodb", "BatchGetItem"), ("sqs", "ListQueues"), ("sqs", "GetQueueUrl"),
    ("lambda", "ListFunctions"), ("lambda", "GetFunction"), ("iam", "ListRoles"), ("ec2", "DescribeInstances"),
    ("accessanalyzer", "ListFindings"),          # REST service that lists with POST
    ("cloudformation", "DescribeStackSet"),      # 'set' is a noun here
    ("backup", "ListRestoreJobs"),               # 'restore' is a noun here
    ("logs", "FilterLogEvents"), ("athena", "GetQueryResults"), ("secretsmanager", "GetSecretValue"),
]
GOLDEN_WRITES = [
    ("s3", "PutObject"), ("s3", "DeleteBucket"), ("s3", "CreateBucket"), ("sqs", "SendMessage"),
    ("sqs", "ReceiveMessage"),                   # hides the message from other consumers
    ("sqs", "PurgeQueue"), ("lambda", "Invoke"), ("dynamodb", "ExecuteStatement"),  # PartiQL can be DML
    ("dynamodb", "BatchWriteItem"), ("dynamodb", "BatchExecuteStatement"), ("athena", "StartQueryExecution"),
    ("cognito-identity", "GetId"),               # read verb, creates the identity
    ("sts", "GetSessionToken"), ("ec2", "RunInstances"), ("iam", "CreateUser"), ("sns", "Publish"),
    ("secretsmanager", "PutSecretValue"), ("cloudformation", "DetectStackDrift"),
]


def test_golden_reads():
    for service, name in GOLDEN_READS:
        method = None
        model = catalog.aws_model(service)
        if model.protocol in catalog.REST_PROTOCOLS:
            method = model.operation_model(name).http.get("method")
        assert classify_aws(service, name, method).read, (service, name)


def test_golden_writes():
    for service, name in GOLDEN_WRITES:
        assert not catalog.aws_verdict(service, name).read, (service, name)


def test_destructive_flag():
    for service, name in [("s3", "DeleteObject"), ("ec2", "TerminateInstances"), ("sqs", "PurgeQueue"), ("s3", "DeleteBucket")]:
        assert catalog.aws_verdict(service, name).destructive, (service, name)
    for service, name in [("s3", "PutObject"), ("sqs", "SendMessage"), ("iam", "CreateUser")]:
        assert not catalog.aws_verdict(service, name).destructive, (service, name)


def test_secret_values_are_flagged_sensitive():
    assert catalog.aws_verdict("secretsmanager", "GetSecretValue").sensitive
    assert catalog.aws_verdict("ssm", "GetParameter").sensitive
    assert not catalog.aws_verdict("secretsmanager", "ListSecrets").sensitive


def test_no_read_combines_a_read_verb_with_a_mutating_word():
    """GetOrCreate*, DescribeAndStop*: the verb says read, the rest says write."""
    bad = []
    for service, name, method in every_operation():
        if classify_aws(service, name, method).read:
            tokens = split_name(name)
            if len(tokens) > 2 and tokens[1] in JOINERS and any(t in MUTATING_WORDS for t in tokens[2:]):
                bad.append((service, name))
    assert not bad, bad


def test_reads_never_ride_a_replacing_or_removing_http_method():
    bad = []
    for service, name, method in every_operation():
        if classify_aws(service, name, method).read and method and method.upper() not in AWS_READ_HTTP_METHODS:
            bad.append((service, name, method))
    assert not bad, bad


def test_read_verbs_on_put_or_delete_are_demoted():
    """tnb.Validate*Content is declared PUT in the model: the cross-check keeps it out of reads."""
    assert not classify_aws("tnb", "ValidateSolFunctionPackageContent", "PUT").read
    assert classify_aws("tnb", "ValidateSolFunctionPackageContent", None).read


def test_unknown_names_default_to_write():
    for name in ("Frobnicate", "FrobnicateThing", "", "listbuckets_lowercase", "XListBuckets"):
        assert not classify_aws("s3", name).read, name


def test_rest_classification_by_method():
    assert classify_rest("gcp", "GET", "/storage/v1/b?project=x").read
    assert classify_rest("azure", "HEAD", "/acct/c/blob").read
    assert not classify_rest("oci", "POST", "/n/ns/b").read
    assert classify_rest("oci", "DELETE", "/n/ns/b/x").destructive
    assert not classify_rest("gcp", "PUT", "/v1/projects/p/topics/t").read
    assert not classify_rest("gcp", "PATCH", "/v1/projects/p/topics/t").read
    # POST that only reads is allowed for a short list, per cloud.
    assert classify_rest("gcp", "POST", "/v1/projects/p/databases/(default)/documents:runQuery").read
    assert not classify_rest("azure", "POST", "/subscriptions/s/providers/Microsoft.Storage/storageAccounts/a/listKeys").read


# ----------------------------------------------------------------- gateway
def test_gateway_refuses_a_write_before_a_client_exists():
    gateway = Gateway(allow_write=False)
    try:
        gateway.call("aws", "s3", "PutObject", {"Bucket": "b", "Key": "k", "Body": "x"})
    except Blocked as exc:
        assert "read-only" in str(exc)
    else:
        raise AssertionError("write was not blocked")
    assert gateway._clients == {}, "a boto3 client was built for a refused call"
    assert gateway.log == []


def test_gateway_refuses_unknown_service_operation_and_cloud():
    gateway = Gateway(allow_write=True)
    for args in [("aws", "nope", "ListThings"), ("aws", "s3", "ListNothing"), ("mars", "x", "y")]:
        try:
            gateway.call(*args)
        except Blocked:
            continue
        raise AssertionError(args)


def test_gateway_refuses_secret_values_unless_allowed():
    gateway = Gateway(allow_write=False, allow_sensitive=False)
    try:
        gateway.call("aws", "secretsmanager", "GetSecretValue", {"SecretId": "x"})
    except Blocked as exc:
        assert "secret" in str(exc)
    else:
        raise AssertionError("secret value was returned")


def test_gateway_rest_refuses_writes_foreign_hosts_and_traversal():
    gateway = Gateway(allow_write=False)
    for request in [
        {"method": "DELETE", "path": "/storage/v1/b/x"},
        {"method": "PUT", "path": "/v1/projects/p/topics/t"},
        {"method": "GET", "path": "http://169.254.169.254/latest"},
        {"method": "GET", "path": "/../etc/passwd"},
        {"method": "GET", "path": "no-slash"},
    ]:
        try:
            gateway.call("gcp", request=request)
        except Blocked:
            continue
        raise AssertionError(request)


def test_gateway_dry_run_records_a_write_and_sends_nothing():
    gateway = Gateway(allow_write=True, dry_run_writes=True)
    out = gateway.call("aws", "s3", "CreateBucket", {"Bucket": "demo"})
    assert out["dry_run"] is True
    assert gateway._clients == {}
    assert gateway.log[0]["operation"] == "CreateBucket" and gateway.log[0]["kind"] == "write"


def test_gateway_resolves_operation_spelling():
    assert catalog.resolve_aws_operation("s3", "list_buckets") == "ListBuckets"
    assert catalog.resolve_aws_operation("s3", "listbuckets") == "ListBuckets"
    assert catalog.resolve_aws_operation("s3", "ListNothing") is None


# ----------------------------------------------------------------- search
def test_search_finds_the_operation_a_person_means():
    top = lambda q, **kw: [(h["service"], h["operation"]) for h in catalog.search(q, **kw)]  # noqa: E731
    assert ("s3", "ListBuckets") in top("list my buckets", service="s3", limit=3)
    assert ("sqs", "SendMessage") in top("send a message to a queue", limit=5)
    assert ("lambda", "Invoke") in top("invoke a lambda function", limit=5)
    assert ("pubsub", "ListTopics") in top("list pub/sub topics", cloud="gcp", limit=3)
    assert ("queue", "CreateQueue") in top("create an azure storage queue", cloud="azure", limit=3)
    assert ("objectstorage", "ListBuckets") in top("list object storage buckets", cloud="oci", limit=3)


def test_every_cloud_has_services_and_catalogued_routes():
    for cloud in ("aws", "azure", "gcp", "oci"):
        assert catalog.list_services(cloud), cloud
    for cloud in ("azure", "gcp", "oci"):
        for service, operation, method, path, _ in catalog.REST_ROUTES[cloud]:
            info = catalog.describe_rest(cloud, service, operation)
            assert info and info["method"] == method
            assert info["kind"] == classify_rest(cloud, method, path).kind


# ----------------------------------------------------------------- sandbox
class Fake(Gateway):
    def __init__(self, responses, **kw):
        super().__init__(**kw)
        self.responses = responses
        self.seen = []

    def call(self, cloud, service="", operation="", params=None, request=None):
        self.seen.append((cloud, service, operation, params))
        return self.responses[(cloud, service, operation)]


def test_sandbox_runs_code_and_returns_result_and_stdout():
    gateway = Fake({("aws", "s3", "ListBuckets"): {"Buckets": [{"Name": "a"}, {"Name": "b"}]}})
    out = run(sandbox.run('r = aws("s3", "ListBuckets")\nprint(len(r["Buckets"]))\nresult = [b["Name"] for b in r["Buckets"]]', gateway))
    assert out["ok"] and out["result"] == ["a", "b"] and out["stdout"].strip() == "2" and out["calls"] == 1


def test_sandbox_passes_keyword_params_through():
    gateway = Fake({("aws", "sqs", "GetQueueUrl"): {"QueueUrl": "u"}})
    run(sandbox.run('aws("sqs", "GetQueueUrl", QueueName="orders")', gateway))
    assert gateway.seen == [("aws", "sqs", "GetQueueUrl", {"QueueName": "orders"})]


def test_sandbox_refuses_imports_and_escapes_before_running():
    for code in ["import os", "import boto3", "from subprocess import run", "open('/etc/passwd')",
                 "().__class__.__bases__", "__import__('os')", "getattr(aws, 'x')", "exec('1')"]:
        out = run(sandbox.run(code, Fake({})))
        assert not out["ok"] and "refused" in out["error"], code


def test_sandbox_read_gateway_cannot_write_whatever_the_code_says():
    code = 'try:\n    aws("s3", "DeleteBucket", Bucket="x")\nexcept CloudError as e:\n    result = "blocked: " + str(e)'
    out = run(sandbox.run(code, Gateway(allow_write=False)))
    assert out["ok"] and out["result"].startswith("blocked:") and out["blocked"]


def test_sandbox_times_out_and_kills_the_child():
    out = run(sandbox.run("while True:\n    pass", Fake({}), timeout=1))
    assert not out["ok"] and "Timed out" in out["error"]


def test_sandbox_caps_the_number_of_calls():
    gateway = Fake({("aws", "s3", "ListBuckets"): {"Buckets": []}})
    out = run(sandbox.run('for _ in range(10):\n    aws("s3", "ListBuckets")', gateway, max_calls=3))
    assert not out["ok"] and "More than 3" in out["error"]


def test_sandbox_child_has_no_third_party_packages():
    import subprocess
    probe = subprocess.run([sys.executable, "-I", "-S", "-c", "import boto3"], capture_output=True, env={})
    assert probe.returncode != 0


# --------------------------------------------------------------- toolsets
def _names(selection, read_only):
    async def go():
        server = FastMCP("t")
        toolsets.register_selected(server, selection)
        toolsets.finalize(server, read_only)
        return sorted(t.name for t in await server.list_tools())
    return run(go())


def test_generic_toolset_is_small_and_read_only_removes_the_writer():
    assert _names(("generic",), False) == ["call_read", "call_write", "describe_operation", "list_services", "search_operations"]
    assert _names(("generic",), True) == ["call_read", "describe_operation", "list_services", "search_operations"]
    assert _names(("code",), False) == ["code_read", "code_write"]
    assert _names(("code",), True) == ["code_read"]


def test_write_tools_are_annotated_destructive():
    async def go():
        server = FastMCP("t")
        toolsets.register_selected(server, ("generic", "code"))
        toolsets.finalize(server, False)
        return {t.name: t.annotations for t in await server.list_tools()}
    notes = run(go())
    assert notes["call_write"].destructiveHint and not notes["call_write"].readOnlyHint
    assert notes["call_read"].readOnlyHint and not notes["call_read"].destructiveHint


# ------------------------------------------------------------ REST catalog
def test_rest_catalog_is_broad_and_consistent():
    gcp, azure, oci = catalog.rest_ops("gcp"), catalog.rest_ops("azure"), catalog.rest_ops("oci")
    assert sum(len(v) for v in gcp.values()) > 1500 and len(gcp) >= 18
    assert len([s for s in azure if s != "arm"]) >= 15 and "arm" in azure
    assert len(oci) >= 8
    for cloud, services in (("gcp", gcp), ("azure", azure), ("oci", oci)):
        for service, ops in services.items():
            names = [o["name"].lower() for o in ops]
            assert len(names) == len(set(names)), (cloud, service, "duplicate names")
            for op in ops:
                assert op["method"] in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}, op
                assert op["path"].startswith("/"), op


def test_rest_get_lists_read_and_deletes_are_destructive():
    for cloud in ("gcp", "azure", "oci"):
        for ops in catalog.rest_ops(cloud).values():
            for op in ops:
                verdict = classify_rest(cloud, op["method"], op["path"])
                if op["method"] == "GET":
                    assert verdict.read, op
                if op["method"] == "DELETE":
                    assert not verdict.read and verdict.destructive, op


def test_rest_secret_routes_are_sensitive():
    assert classify_rest("gcp", "GET", "/v1/projects/p/secrets/s/versions/1:access").sensitive
    assert classify_rest("azure", "GET", "/devstoreaccount1-keyvault/secrets/db").sensitive
    assert not classify_rest("azure", "GET", "/devstoreaccount1-keyvault/secrets").sensitive


class Capture(Gateway):
    def _rest(self, cloud, request):
        self.sent = (cloud, request)
        return {"status": 200, "body": {}}


def test_gateway_builds_requests_from_the_declared_parameters():
    g = Capture(allow_write=True)
    g.call("gcp", "pubsub", "CreateTopic", {"topic": "events"})
    assert g.sent == ("gcp", {"method": "PUT", "path": "/v1/projects/floci-local/topics/events"})
    g.call("gcp", "storage", "ListBuckets", {})
    assert g.sent[1]["path"].startswith("/storage/v1/b") and "floci-local" in str(g.sent[1])
    g.call("azure", "arm", "ListResourceGroups", {})
    assert g.sent[1]["path"] == "/subscriptions/00000000-0000-0000-0000-000000000000/resourcegroups?api-version=2021-04-01"
    g.call("azure", "arm", "CreateResourceGroup", {"resourceGroup": "rg1", "body": {"location": "westeurope"}})
    assert g.sent[1]["method"] == "PUT" and g.sent[1]["json"] == {"location": "westeurope"}
    g.call("oci", "queue", "CreateQueue", {"body": {"displayName": "q", "compartmentId": "c"}})
    assert g.sent[1]["method"] == "POST" and g.sent[1]["json"]["displayName"] == "q"
    g.call("gcp", "pubsub", "GetTopic", {"topic": "projects/floci-local/topics/t"})
    assert g.sent[1]["path"] == "/v1/projects/floci-local/topics/t"  # {+topic}: reserved expansion, not quoted


def test_gateway_rest_refuses_missing_parameters_and_unknown_operations():
    g = Capture(allow_write=True)
    for args in [("gcp", "pubsub", "CreateTopic", {}), ("gcp", "pubsub", "NoSuchOp", {}), ("azure", "arm", "DeleteResourceGroup", {})]:
        try:
            g.call(*args)
        except Blocked:
            continue
        raise AssertionError(args)


def test_gateway_rest_blocks_secret_reads_by_default():
    try:
        Gateway(allow_write=False, allow_sensitive=False).call("azure", request={"method": "GET", "path": "/devstoreaccount1-keyvault/secrets/db"})
    except Blocked as exc:
        assert "secret" in str(exc)
    else:
        raise AssertionError("secret read was allowed")


def test_search_reaches_the_generated_catalog():
    top = lambda q, cloud, **kw: [(h["service"], h["operation"]) for h in catalog.search(q, cloud, None, 5, **kw)]  # noqa: E731
    assert any(s == "kms" for s, _ in top("list key rings", "gcp")), top("list key rings", "gcp")
    assert any(s == "compute" for s, _ in top("list compute instances", "gcp"))
    assert any(s == "redis" for s, _ in top("list redis caches", "azure")), top("list redis caches", "azure")
    assert any(s == "queue" for s, _ in top("create an oci queue", "oci"))


# ----------------------------------------------------------------- recipes
RECIPES = [
    {"id": "postgres", "name": "PostgreSQL", "description": "db", "accessUrl": "postgresql://u:{{POSTGRES_PASSWORD}}@localhost:{{POSTGRES_PORT}}/db",
     "aws": {"service": "Amazon RDS for PostgreSQL"},
     "variables": [{"key": "POSTGRES_PORT", "default": 5432, "type": "number"},
                   {"key": "POSTGRES_PASSWORD", "default": "postgres123", "type": "password"}]},
    {"id": "keycloak", "name": "Keycloak", "description": "idp", "accessUrl": "http://localhost:{{KEYCLOAK_PORT}}",
     "variables": [{"key": "KEYCLOAK_PORT", "default": 8080, "type": "number"}]},
]


class FakeBackend:
    """Stands in for the in-process backend: records installs and reports RUNNING."""
    def __init__(self, final="RUNNING"):
        self.calls, self.state, self.final = [], {}, final

    async def __call__(self, method, path, json_data=None):
        self.calls.append((method, path, json_data))
        if path == "/api/marketplace/recipes":
            return {"recipes": RECIPES}
        if path == "/api/marketplace/installations":
            return {"installations": self.state}
        if method == "POST":
            rid = json_data["recipeId"]
            defaults = {v["key"]: v["default"] for r in RECIPES if r["id"] == rid for v in r["variables"]}
            self.state[rid] = {"status": self.final, "vars": {**defaults, **json_data["vars"]},
                               "error": "boom" if self.final == "FAILED" else None}
            return {"ok": True}
        if method == "DELETE":
            self.state.pop(path.rsplit("/", 1)[1], None)
            return {"ok": True}
        if path.endswith("/logs"):
            return {"logs": ["line 1", "line 2"]}
        raise AssertionError(path)


def with_backend(backend, busy=()):
    recipes._backend = backend
    recipes._native_cache = {}
    recipes.port_busy = lambda port: port in busy
    return backend


def test_recipes_operations_are_classified_by_table_not_by_verb():
    assert recipes.verdict("ListRecipes").read and recipes.verdict("GetStatus").read
    assert not recipes.verdict("DeployRecipe").read and not recipes.verdict("DeployRecipe").destructive
    assert not recipes.verdict("TeardownRecipe").read and recipes.verdict("TeardownRecipe").destructive
    assert recipes.verdict("Frobnicate") is None


def test_recipes_every_recipe_on_disk_with_a_floci_equivalent_names_real_services():
    import json
    from glob import glob
    ids = {json.load(open(f))["id"] for f in glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recipes", "*", "recipe.json"))}
    assert len(ids) >= 30
    assert set(recipes.AWS_EQUIVALENT) <= ids, set(recipes.AWS_EQUIVALENT) - ids
    for rid, services in recipes.AWS_EQUIVALENT.items():
        for service in services:
            assert catalog.has_aws_service(service), (rid, service)


def test_recipes_deploy_moves_a_busy_default_port_and_reports_it():
    backend = with_backend(FakeBackend(), busy={5432})
    out = run(recipes.call("DeployRecipe", {"recipe_id": "postgres", "wait_seconds": 2}))
    assert out["status"] == "RUNNING", out
    assert out["ports_adjusted"] == {"POSTGRES_PORT": {"default": 5432, "using": 5433}}
    assert out["access_url"] == "postgresql://u:postgres123@localhost:5433/db"
    posts = [c for c in backend.calls if c[0] == "POST"]
    assert len(posts) == 1 and posts[0][2]["vars"] == {"POSTGRES_PORT": 5433}


def test_recipes_deploy_refuses_a_busy_port_the_user_chose():
    backend = with_backend(FakeBackend(), busy={7000})
    out = run(recipes.call("DeployRecipe", {"recipe_id": "postgres", "vars": {"POSTGRES_PORT": 7000}}))
    assert "already in use" in out["error"] and out["suggestion"] == {"POSTGRES_PORT": 7001}
    assert not any(c[0] == "POST" for c in backend.calls), "docker was asked to start despite the busy port"


def test_recipes_deploy_rejects_unknown_variables_and_recipes():
    with_backend(FakeBackend())
    assert "Unknown variable" in run(recipes.call("DeployRecipe", {"recipe_id": "postgres", "vars": {"NOPE": 1}}))["error"]
    assert "Unknown recipe" in run(recipes.call("DeployRecipe", {"recipe_id": "nope"}))["error"]


def test_recipes_failed_deploy_returns_the_error_and_the_log_tail():
    with_backend(FakeBackend(final="FAILED"))
    out = run(recipes.call("DeployRecipe", {"recipe_id": "keycloak", "wait_seconds": 2}))
    assert out["status"] == "FAILED" and out["error"] == "boom" and out["log_tail"] == ["line 1", "line 2"]


def test_recipes_teardown_waits_for_idle():
    backend = with_backend(FakeBackend())
    run(recipes.call("DeployRecipe", {"recipe_id": "keycloak", "wait_seconds": 2}))
    out = run(recipes.call("TeardownRecipe", {"recipe_id": "keycloak", "wait_seconds": 2}))
    assert out == {"recipe_id": "keycloak", "status": "IDLE"}


def test_recipes_through_the_gateway_follow_the_read_write_rule():
    with_backend(FakeBackend())
    read_only = Gateway(allow_write=False)
    assert run(read_only.acall("recipes", operation="ListRecipes"))["count"] == 2
    for op in ("DeployRecipe", "TeardownRecipe"):
        try:
            run(read_only.acall("recipes", operation=op, params={"recipe_id": "postgres"}))
        except Blocked:
            continue
        raise AssertionError(op)
    dry = Gateway(allow_write=True, dry_run_writes=True)
    assert run(dry.acall("recipes", operation="DeployRecipe", params={"recipe_id": "postgres"}))["dry_run"]


def test_recipes_are_reachable_from_the_read_only_code_sandbox_and_cannot_deploy():
    with_backend(FakeBackend())
    gateway = Gateway(allow_write=False)
    out = run(sandbox.run('result = call("recipes", "marketplace", "ListRecipes")["count"]', gateway))
    assert out["ok"] and out["result"] == 2, out
    out = run(sandbox.run('call("recipes", "marketplace", "DeployRecipe", recipe_id="postgres")', gateway))
    assert not out["ok"] and out["blocked"], out


def test_recipes_are_discoverable_without_any_extra_tool():
    assert catalog.list_services("recipes")
    top = [h["operation"] for h in catalog.search("start a local redis stack with docker", "recipes", None, 3)]
    assert "DeployRecipe" in top, top
    assert recipes.describe("deployrecipe")["kind"] == "write"


def test_marketplace_toolset_is_three_tools_and_pipeline_is_apart():
    assert _names(("marketplace",), False) == ["deploy_marketplace_app", "list_marketplace_recipes", "teardown_marketplace_app"]
    assert _names(("marketplace",), True) == ["list_marketplace_recipes"]
    assert "deploy_to_environment" in _names(("pipeline",), False)
    assert "deploy_to_environment" not in _names(("marketplace",), False)


def test_generic_toolsets_do_not_grow_with_recipes():
    """The point of cloud='recipes': no new tool definitions."""
    assert len(_names(("generic",), False)) == 5 and len(_names(("code",), False)) == 2


# -------------------------------------------------------------------- live
def _up(url: str) -> bool:
    try:
        httpx.get(url, timeout=2)
        return True
    except httpx.HTTPError:
        return False


def test_live_every_cloud_answers_a_read():
    gateway = Gateway(allow_write=False)
    checks = []
    if _up("http://localhost:4566/"):
        out = gateway.call("aws", "s3", "ListBuckets")
        assert "Buckets" in out, out
        checks.append("aws")
    if _up("http://localhost:4577/"):
        out = gateway.call("azure", "blob", "ListContainers")
        assert out.get("status") == 200, out
        checks.append("azure")
    if _up("http://localhost:4588/"):
        out = gateway.call("gcp", "storage", "ListBuckets")
        assert out.get("status") == 200, out
        checks.append("gcp")
    if _up("http://localhost:4599/"):
        out = gateway.call("oci", "objectstorage", "ListBuckets")
        assert out.get("status") == 200, out
        checks.append("oci")
    if _up("http://localhost:4566/"):
        recipes._backend = __import__("tools._client", fromlist=["backend"]).backend
        recipes._native_cache = None
        out = run(Gateway().acall("recipes", operation="ListRecipes"))
        assert out["count"] >= 30, out
        checks.append(f"recipes({out['count']}, native: {sorted(r['id'] for r in out['recipes'] if 'floci_native' in r)})")
    print("   live clouds checked:", checks or "none reachable")


def test_live_every_verified_read_in_the_catalog_still_answers():
    gateway = Gateway(allow_write=False)
    bad = []
    count = 0
    for cloud, port in (("gcp", 4588), ("azure", 4577), ("oci", 4599)):
        if not _up(f"http://localhost:{port}/"):
            continue
        for service, ops in catalog.rest_ops(cloud).items():
            for op in ops:
                if not op.get("verified") or op["method"] != "GET":
                    continue
                required = [p for p, v in op["params"].items() if v.get("required") and v.get("in") == "path"]
                needs = [p for p in required if p not in ("project", "projectId", "projectsId", "projectNumber", "parent",
                                                        "location", "locationsId", "region", "zone", "account", "subscription",
                                                        "compartmentId", "namespace")]
                if needs:
                    continue
                out = gateway.call(cloud, service, op["name"], {})
                count += 1
                if out.get("status", 200) >= 400 or "error" in out:
                    bad.append((cloud, service, op["name"], out.get("status"), str(out)[:80]))
    print(f"   live verified reads run: {count}, failing: {len(bad)}")
    assert not bad, bad[:8]


def test_live_create_and_delete_cycle_on_every_rest_cloud():
    import uuid
    gateway = Gateway(allow_write=True)
    tag = uuid.uuid4().hex[:8]
    done = []
    if _up("http://localhost:4588/"):
        name = f"mcp-t-{tag}"
        assert gateway.call("gcp", "pubsub", "CreateTopic", {"topic": name})["status"] < 300
        assert name in str(gateway.call("gcp", "pubsub", "ListTopics", {})["body"])
        assert gateway.call("gcp", "pubsub", "DeleteTopic", {"topic": f"projects/floci-local/topics/{name}"})["status"] < 300
        assert name not in str(gateway.call("gcp", "pubsub", "ListTopics", {})["body"])
        done.append("gcp")
    if _up("http://localhost:4577/"):
        name = f"mcpt{tag}"
        assert gateway.call("azure", "queue", "CreateQueue", {"queue": name})["status"] < 300
        assert name in str(gateway.call("azure", "queue", "ListQueues", {})["body"])
        assert gateway.call("azure", "queue", "DeleteQueue", {"queue": name})["status"] < 300
        rg = f"rg-{tag}"
        assert gateway.call("azure", "arm", "CreateResourceGroup", {"resourceGroup": rg, "body": {"location": "westeurope"}})["status"] < 300
        assert rg in str(gateway.call("azure", "arm", "ListResourceGroups", {})["body"])
        assert gateway.call("azure", "arm", "DeleteResourceGroup", {"resourceGroup": rg})["status"] < 300
        done.append("azure")
    if _up("http://localhost:4599/"):
        name = f"mcp-t-{tag}"
        assert gateway.call("oci", "objectstorage", "CreateBucket", {"body": {"name": name}})["status"] < 300
        assert name in str(gateway.call("oci", "objectstorage", "ListBuckets", {})["body"])
        assert gateway.call("oci", "objectstorage", "DeleteBucket", {"bucket": name})["status"] < 300
        done.append("oci")
    print("   live write cycles:", done or "none reachable")


if __name__ == "__main__":
    failed = 0
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            fn()
            print(f"ok    {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {type(exc).__name__}: {str(exc)[:400]}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
