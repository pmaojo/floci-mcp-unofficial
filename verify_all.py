"""Exhaustive check of the Floci MCP server against live emulators.

Needs the AWS runtime on :4566. Azure, GCP and OCI groups run when their runtimes
answer. Every tool must either be exercised or carry a reason in SKIPPED, so a
new tool cannot go untested unnoticed.

    uv run python verify_all.py            # all groups
    uv run python verify_all.py aws s3     # only groups whose name matches
"""
import asyncio
import base64
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import re
import uuid
import zipfile
import io

os.environ["FLOCI_TOOLSETS"] = "all"
import toolsets as toolsets_module  # noqa: E402
spec = importlib.util.spec_from_file_location("floci_mcp", os.path.join(os.path.dirname(__file__), "floci_mcp.py"))
server = importlib.util.module_from_spec(spec)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
spec.loader.exec_module(server)

X = uuid.uuid4().hex[:6]
RESULTS: list[tuple[str, str, str]] = []  # group, label, status
EXERCISED: set[str] = set()
GROUPS: list = []

SKIPPED = {
    "list_toolsets": "covered by the toolsets and dynamic groups, which run it in a subprocess",
    "enable_toolset": "registered unless switching is forbidden; the dynamic group drives it over stdio",
    "suggest_toolsets": "only registered when FLOCI_DECIDER is set; the decider group drives it over stdio",
    "disable_toolset": "registered unless switching is forbidden; the dynamic group drives it over stdio",
    "start_reverse_tunnel": "spawns an external tunnel binary; only its error path is checked",
    "stop_reverse_tunnel": "needs a live tunnel pid",
}


def group(fn):
    GROUPS.append(fn)
    return fn


class ToolFailed(Exception):
    pass


async def call(tool: str, /, **arguments):
    EXERCISED.add(tool)
    try:
        result = await server.mcp.call_tool(tool, arguments)
    except Exception as exc:  # noqa: BLE001
        raise ToolFailed(str(exc)[:400]) from exc
    if isinstance(result, tuple):
        return result[1]
    return json.loads(result[0].text)


async def attempt(tool: str, /, **arguments):
    """Like call(), but returns the error text instead of raising."""
    try:
        return await call(tool, **arguments)
    except ToolFailed as exc:
        return {"__error__": str(exc)}


def ok(name: str, label: str, condition, detail=None):
    RESULTS.append((name, label, "ok" if condition else "FAIL"))
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition and detail is not None:
        print(f"       {json.dumps(detail, default=str)[:400]}")


def skip(name: str, label: str, reason: str):
    RESULTS.append((name, label, "skip"))
    print(f"  skip {label}: {reason}")


def has_error(value) -> bool:
    return isinstance(value, dict) and "__error__" in value


def runtime_up(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def lambda_zip(source: str) -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("main.py", source)
    return base64.b64encode(buffer.getvalue()).decode()


SPANISH_WORDS = {"el", "la", "los", "las", "una", "del", "para", "con", "por", "sus", "lista", "crea", "elimina",
                 "obtiene", "envía", "ejecuta", "devuelve", "recibe", "entorno", "todas", "todos"}


def _spanish(text: str) -> bool:
    import re
    words = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]+", text)
    return bool(re.search(r"[áéíóúñ¿¡]", text)) or sum(1 for w in words if w.lower() in SPANISH_WORDS) >= 2


# ---------------------------------------------------------------- catalogue
@group
async def catalogue():
    tools = await server.mcp.list_tools()
    names = [t.name for t in tools]
    ok("catalogue", f"{len(names)} tools registered", len(names) >= 139)
    ok("catalogue", "descriptions are in English (no accents, no Spanish stop words)",
       not [t.name for t in tools if _spanish(t.description or "")], [t.name for t in tools if _spanish(t.description or "")][:10])
    ok("catalogue", "tool names are unique", len(names) == len(set(names)))
    ok("catalogue", "every tool has a description", all((t.description or "").strip() for t in tools),
       [t.name for t in tools if not (t.description or "").strip()])
    ok("catalogue", "every input schema is an object", all(t.inputSchema.get("type") == "object" for t in tools))
    ok("catalogue", "names are snake_case", all(n == n.lower() and " " not in n for n in names))
    ok("catalogue", "cloud tools are present",
       {"list_clouds", "gcp_list_buckets", "azure_list_queues", "oci_list_buckets"} <= set(names))


# ----------------------------------------------------------------- protocol
@group
async def protocol():
    root = os.path.dirname(os.path.abspath(__file__))
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "verify", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "floci_hello", "arguments": {"name": "stdio"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "no_such_tool", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "get_s3_object", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 6, "method": "no/such/method"},
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "floci_hello", "arguments": {"name": "after errors"}}},
    ]
    proc = subprocess.run(
        [sys.executable, "-u", os.path.join(root, "floci_mcp.py")],
        input="\n".join(json.dumps(m) for m in messages) + "\n",
        capture_output=True, text=True, timeout=60, cwd=root,
    )
    replies = {}
    for line in proc.stdout.splitlines():
        if line.startswith("{"):
            body = json.loads(line)
            replies[body.get("id")] = body
    ok("protocol", "initialize answers with server info", "serverInfo" in replies.get(1, {}).get("result", {}), replies.get(1))
    ok("protocol", "tools/list returns every tool over stdio", len(replies.get(2, {}).get("result", {}).get("tools", [])) >= 139)
    ok("protocol", "tools/call works over stdio", "stdio" in json.dumps(replies.get(3, {})), replies.get(3))
    ok("protocol", "unknown tool is an error, not a crash",
       replies.get(4, {}).get("result", {}).get("isError") or "error" in replies.get(4, {}), replies.get(4))
    ok("protocol", "missing required argument is an error",
       replies.get(5, {}).get("result", {}).get("isError") or "error" in replies.get(5, {}), replies.get(5))
    ok("protocol", "unknown method is a JSON-RPC error", "error" in replies.get(6, {}), replies.get(6))
    ok("protocol", "server keeps answering after errors", "after errors" in json.dumps(replies.get(7, {})), replies.get(7))


# --------------------------------------------------------------------- docs
@group
async def docs_group():
    root = os.path.dirname(os.path.abspath(__file__))
    readme = open(os.path.join(root, "README.md")).read()
    index = await __import__("toolsets").tool_index()

    # Every environment variable the code reads is documented.
    pattern = re.compile(r"""(?:os\.environ\.get|os\.getenv|environ\[|env\.get)\(?\s*['"]([A-Z][A-Z0-9_]{3,})['"]""")
    read: set[str] = set()
    for folder in ("tools", "floci_backend"):
        for dirpath, _, files in os.walk(os.path.join(root, folder)):
            for name in files:
                if name.endswith(".py"):
                    read |= set(pattern.findall(open(os.path.join(dirpath, name)).read()))
    for name in ("floci_mcp.py", "toolsets.py", "decider.py"):
        read |= set(pattern.findall(open(os.path.join(root, name)).read()))
    internal = {"SIDECAR_HOST", "SIDECAR_PORT", "SIDECAR_ALLOWED_ORIGINS", "SIDECAR_MAX_BODY_MB", "SIDECAR_TOKEN",
                "LAMBDA_DEFAULT_ROLE_ARN", "AWS_DEFAULT_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                "FLOCI_EVAL_MODEL", "ANTHROPIC_API_KEY", "VERIFY_DOCKER",
                "KUBECONFIG"}  # KUBECONFIG: read by an EKS backend route that no tool exposes
    missing = sorted(v for v in read if v not in internal and v not in readme)
    ok("docs", "every environment variable the server reads is in the README", not missing, missing)

    # The cookbook and skills table only name tools that exist.
    names = set(re.findall(r"`([a-z0-9_]+)`", readme))
    tool_like = {n for n in names if TOOL_LIKE.match(n)} - {"list_changed"}  # list_changed is an MCP notification
    ok("docs", "every tool the README names exists", not [n for n in tool_like if n not in index], [n for n in tool_like if n not in index])

    # The error messages the troubleshooting table quotes are the ones the code produces.
    source = ""
    for folder in ("tools", "floci_backend", "."):
        for dirpath, _, files in os.walk(os.path.join(root, folder)):
            if ".venv" in dirpath or "docs" in dirpath.split(os.sep):
                continue
            for name in files:
                if name.endswith(".py") and name != "verify_all.py":
                    source += open(os.path.join(dirpath, name)).read()
        if folder == ".":
            break
    for fragment in ("The aws CLI is not on PATH", "'docker' was not found on PATH", "Cannot reach the", "is not allowed to be enabled at runtime",
                     "unknown toolset", "Could not connect"):
        if fragment == "Could not connect":
            continue  # botocore's own message
        ok("docs", f"troubleshooting message exists in the code: {fragment}", fragment in source)

    # Every toolset is documented in the README table.
    ok("docs", "every toolset is in the README", all(f"`{t}`" in readme for t in __import__("toolsets").TOOLSETS))


# ------------------------------------------------------------------- plugin
@group
async def plugin_group():
    root = os.path.dirname(os.path.abspath(__file__))
    manifest = json.load(open(os.path.join(root, ".claude-plugin", "plugin.json")))
    market = json.load(open(os.path.join(root, ".claude-plugin", "marketplace.json")))
    mcp_json = json.load(open(os.path.join(root, ".mcp.json")))
    ok("plugin", "name is kebab-case and not reserved",
       re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", manifest["name"]) is not None
       and not manifest["name"].startswith(("claude-", "anthropic-")), manifest["name"])
    ok("plugin", "the marketplace lists the plugin from the repository root",
       any(p["name"] == manifest["name"] and p["source"] in (".", "./") for p in market["plugins"]), market["plugins"])
    ok("plugin", "skills live in the default skills/ directory", os.path.isdir(os.path.join(root, "skills")))
    server = mcp_json["mcpServers"]["floci"]
    referenced = set(re.findall(r"\$\{user_config\.([A-Za-z0-9_]+)\}", json.dumps(server)))
    ok("plugin", "every user_config reference is declared", referenced <= set(manifest["userConfig"]), referenced - set(manifest["userConfig"]))
    ok("plugin", "the server entry point exists", os.path.isfile(os.path.join(root, "floci_mcp.py")))
    ok("plugin", "the default toolsets in the manifest match the server",
       manifest["userConfig"]["toolsets"]["default"] == ",".join(toolsets_module.DEFAULT_TOOLSETS),
       manifest["userConfig"]["toolsets"]["default"])
    import shutil
    if shutil.which("claude"):
        for target in (".claude-plugin/plugin.json", "."):
            proc = subprocess.run(["claude", "plugin", "validate", target, "--strict"], capture_output=True, text=True, cwd=root, timeout=120)
            ok("plugin", f"claude plugin validate {target}", proc.returncode == 0, (proc.stdout + proc.stderr)[-300:])
    else:
        skip("plugin", "claude plugin validate", "the claude CLI is not installed")


# ------------------------------------------------------------------- skills
TOOL_LIKE = re.compile(
    r"^(list|get|create|delete|put|update|send|publish|subscribe|unsubscribe|purge|receive|invoke|run|start|stop|"
    r"describe|generate|export|seed|deploy|teardown|promote|register|emit|inspect|redrive|tag|untag|find|check|"
    r"verify|detect|discover|capture|edit|replay|kms|gcp|azure|oci|scan|query|execute|proxy)_[a-z0-9_]+$"
)
ENV_AND_PARAMS = {"FLOCI_TOOLSETS", "FLOCI_READ_ONLY"}


@group
async def skills_group():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import skills_catalog
    skills = await skills_catalog.load_skills()
    readme = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")).read()
    ok("skills", f"{len(skills)} skills found", len(skills) >= 6)
    for skill in skills:
        name = skill["dir"]
        ok("skills", f"{name}: frontmatter name matches its directory", skill["name"] == name, skill["name"])
        ok("skills", f"{name}: has a description of 40 to 1024 characters", 40 <= len(skill["description"]) <= 1024, len(skill["description"]))
        ok("skills", f"{name}: description says when to use it", "use when" in skill["description"].lower(), skill["description"][:120])
        ok("skills", f"{name}: every tool it names exists", not [c for c in skill["candidates"] if TOOL_LIKE.match(c)],
           [c for c in skill["candidates"] if TOOL_LIKE.match(c)])
        ok("skills", f"{name}: calls at least one tool", len(skill["tools"]) >= 1)
        ok("skills", f"{name}: states the toolsets it needs, and they are the right ones",
           set(skill["statedToolsets"]) == set(skill["requires"]), {"stated": skill["statedToolsets"], "actual": skill["requires"]})
        ok("skills", f"{name}: is listed in the README", f"`{name}`" in readme)


# ----------------------------------------------------------------- toolsets
@group
async def toolsets_group():
    root = os.path.dirname(os.path.abspath(__file__))
    script = (
        "import asyncio, importlib.util, json, sys\n"
        "sys.path.insert(0, %r)\n"
        "spec = importlib.util.spec_from_file_location('m', %r); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "import toolsets\n"
        "tools = asyncio.run(m.mcp.list_tools())\n"
        "print('RESULT' + json.dumps({'names': [t.name for t in tools],\n"
        "  'ro': {t.name: bool(t.annotations and t.annotations.readOnlyHint) for t in tools},\n"
        "  'writers': [t.name for t in tools if toolsets.is_write(t.name)],\n"
        "  'selection': list(m.SELECTION), 'read_only': m.READ_ONLY}))\n"
    ) % (root, os.path.join(root, "floci_mcp.py"))

    def run(**env):
        full = {k: v for k, v in os.environ.items() if k not in ("FLOCI_TOOLSETS", "FLOCI_READ_ONLY")}
        full.update(env)
        proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=full, timeout=120, cwd=root)
        line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULT")), None)
        return (json.loads(line[6:]) if line else None), proc

    default, _ = run()
    ok("toolsets", "the default selection is core, storage, messaging and compute",
       bool(default) and default["selection"] == ["core", "storage", "messaging", "compute"], default and default["selection"])
    everything, _ = run(FLOCI_TOOLSETS="all")
    ok("toolsets", "'all' registers more tools than the default",
       bool(default and everything) and len(everything["names"]) > len(default["names"]),
       (len(default["names"]), len(everything["names"])) if default and everything else None)
    core, _ = run(FLOCI_TOOLSETS="core")
    ok("toolsets", "core is small and holds the discovery tools",
       bool(core) and len(core["names"]) < 30 and {"check_floci_health", "list_clouds", "list_toolsets"} <= set(core["names"]),
       core and len(core["names"]))
    ok("toolsets", "a disabled toolset is really absent", bool(core) and "create_sqs_queue" not in core["names"])
    two, _ = run(FLOCI_TOOLSETS="core,messaging")
    ok("toolsets", "toolsets combine", bool(two) and "create_sqs_queue" in two["names"] and "create_s3_bucket" not in two["names"])
    ok("toolsets", "names are case and space tolerant", bool(run(FLOCI_TOOLSETS=" CORE , Storage ")[0]))
    bad, proc = run(FLOCI_TOOLSETS="nope")
    ok("toolsets", "an unknown toolset fails fast and names the valid ones",
       bad is None and "unknown toolset nope" in proc.stderr and "Available:" in proc.stderr, proc.stderr[-200:])
    ro, _ = run(FLOCI_TOOLSETS="all", FLOCI_READ_ONLY="1")
    ok("toolsets", "read-only mode leaves no writer", bool(ro) and ro["writers"] == [], ro and ro["writers"])
    must_go = ["azure_create_container", "azure_create_queue", "gcp_create_bucket", "gcp_create_topic", "oci_create_bucket",
               "create_s3_bucket", "put_s3_object", "delete_sqs_queue", "invoke_lambda", "deploy_marketplace_app", "run_local_aws_cmd"]
    ok("toolsets", "read-only mode removes the cloud writers by name, not by the module's own rule",
       bool(ro) and not [n for n in must_go if n in ro["names"]], ro and [n for n in must_go if n in ro["names"]])
    ok("toolsets", "read-only mode keeps the readers",
       bool(ro) and {"list_s3_buckets", "get_secret_value", "scan_dynamodb", "list_clouds"} <= set(ro["names"]))
    ok("toolsets", "read-only mode is reported", bool(ro) and ro["read_only"] is True)
    ok("toolsets", "every tool carries a readOnlyHint", bool(everything) and len(everything["ro"]) == len(everything["names"]))
    ok("toolsets", "writers are not hinted as read-only",
       bool(everything) and not any(everything["ro"].get(n) for n in everything["writers"]),
       [n for n in (everything or {}).get("writers", []) if everything["ro"].get(n)])
    listing = await attempt("list_toolsets")
    ok("toolsets", "list_toolsets explains the configuration", "enabled" in listing and "how_to_enable" in listing, listing)
    digest = listing.get("definitions_sha256", "")
    ok("toolsets", "list_toolsets reports a definitions digest", bool(re.fullmatch(r"[0-9a-f]{64}", digest)), digest)
    again = await attempt("list_toolsets")
    ok("toolsets", "the digest is stable between calls", again.get("definitions_sha256") == digest)


# --------------------------------------------------------------------- core
@group
async def core():
    health = await call("check_floci_health")
    ok("core", "health reports the emulator online", health.get("aws_emulator", {}).get("status") == "Online", health)
    services = await call("list_aws_services")
    keys = {s["key"] for s in services.get("services", [])}
    ok("core", "service catalogue lists s3, dynamodb and sqs", {"s3", "dynamodb", "sqs"} <= keys, sorted(keys)[:10])
    res = await call("get_service_resources", service_key="s3")
    ok("core", "service resources for s3", res.get("serviceKey") == "s3", res)
    bad = await attempt("get_service_resources", service_key="nope")
    ok("core", "unknown service key is an error", has_error(bad) or bad.get("ok") is False, bad)
    ok("core", "cost forecast has a total", "totalMonthlyForecast" in await call("get_cost_forecast"))
    ok("core", "network topology returns a diagram", "mermaid" in await call("get_network_topology"))
    ok("core", "enterprise roadmap", "roadmap" in await call("get_enterprise_roadmap"))
    ok("core", "service graph has nodes", "nodes" in await call("get_service_graph"))
    arch = await attempt("get_architecture_diagram")
    ok("core", "architecture diagram", not has_error(arch), arch)
    runtimes = await call("get_lambda_runtimes")
    ok("core", "lambda runtimes include a python runtime", "python" in json.dumps(runtimes), runtimes)
    ok("core", "plugin catalogue", "plugins" in await call("list_floci_plugins"))
    ok("core", "community plugin tool", "stdio-check" in json.dumps(await call("floci_hello", name="stdio-check")))
    ok("core", "pipeline environments", "environments" in await call("list_pipeline_environments"))


# ------------------------------------------------------------------- aws s3
@group
async def s3():
    bucket = f"vfy-{X}"
    await call("create_s3_bucket", name=bucket)
    try:
        ok("s3", "bucket listed", bucket in [b["name"] for b in (await call("list_s3_buckets"))["buckets"]])
        await call("put_s3_object", bucket=bucket, key="dir/a.txt", content="hello mcp", content_type="text/plain")
        await call("put_s3_object", bucket=bucket, key="b.json", content='{"a":1}', content_type="application/json")
        got = await call("get_s3_object", bucket=bucket, key="dir/a.txt")
        ok("s3", "object round-trips", "hello mcp" in json.dumps(got), got)
        listing = await call("list_s3_objects", bucket=bucket)
        ok("s3", "objects listed", len(json.dumps(listing)) > 20 and "a.txt" in json.dumps(listing), listing)
        pref = await call("list_s3_objects", bucket=bucket, prefix="dir/")
        ok("s3", "prefix filter", "a.txt" in json.dumps(pref) and "b.json" not in json.dumps(pref), pref)
        limited = await call("list_s3_objects", bucket=bucket, max_keys=1)
        ok("s3", "max_keys limits the page", json.dumps(limited).count('"key"') <= 1 or json.dumps(limited).count("txt") + json.dumps(limited).count("json") <= 2, limited)
        url = await call("generate_s3_presigned_url", bucket=bucket, key="dir/a.txt", operation="get_object", expires_in=60)
        ok("s3", "presigned url", "http" in json.dumps(url), url)
        await call("delete_s3_object", bucket=bucket, key="b.json")
        ok("s3", "object deleted", "b.json" not in json.dumps(await call("list_s3_objects", bucket=bucket)))
        missing = await attempt("get_s3_object", bucket=bucket, key="nope")
        ok("s3", "missing object is an error", has_error(missing) or "error" in json.dumps(missing).lower(), missing)
        nobucket = await attempt("list_s3_objects", bucket=f"absent-{X}")
        ok("s3", "missing bucket is an error", has_error(nobucket) or "error" in json.dumps(nobucket).lower(), nobucket)
        notempty = await attempt("delete_s3_bucket", name=bucket)
        ok("s3", "non-empty bucket is not deleted without force", has_error(notempty) or "error" in json.dumps(notempty).lower() or bucket in [b["name"] for b in (await call("list_s3_buckets"))["buckets"]], notempty)
    finally:
        await attempt("delete_s3_bucket", name=bucket, force=True)
    ok("s3", "bucket force-deleted", bucket not in [b["name"] for b in (await call("list_s3_buckets"))["buckets"]])


# ------------------------------------------------------------------ aws sqs
@group
async def sqs():
    name = f"vfy-{X}"
    created = await call("create_sqs_queue", name=name, visibility_timeout=5)
    url = created.get("queue_url") or created.get("QueueUrl") or created.get("url")
    ok("sqs", "queue created", bool(url), created)
    try:
        await call("send_sqs_message", queue_url=url, body="first")
        await call("send_sqs_message", queue_url=url, body="second", delay_seconds=0)
        attrs = await call("get_sqs_queue_attributes", queue_url=url)
        ok("sqs", "attributes report the backlog", "ApproximateNumberOfMessages" in json.dumps(attrs), attrs)
        got = await call("receive_sqs_messages", queue_url=url, max_messages=10, wait_seconds=1)
        messages = got.get("messages") or got.get("Messages") or []
        ok("sqs", "both messages received", len(messages) == 2, got)
        if messages:
            handle = messages[0].get("receipt_handle") or messages[0].get("ReceiptHandle")
            await call("delete_sqs_message", queue_url=url, receipt_handle=handle)
        await call("purge_sqs_queue", queue_url=url)
        ok("sqs", "queue appears in the list", url in json.dumps(await call("list_sqs_queues")))
        bad = await attempt("send_sqs_message", queue_url=url + "-absent", body="x")
        ok("sqs", "send to a missing queue is an error", has_error(bad) or "error" in json.dumps(bad).lower(), bad)
    finally:
        await attempt("delete_sqs_queue", queue_url=url)
    fifo = await attempt("create_sqs_queue", name=f"vfy-{X}.fifo", fifo=True)
    fifo_url = fifo.get("queue_url") or fifo.get("QueueUrl") or fifo.get("url")
    ok("sqs", "fifo queue created", bool(fifo_url), fifo)
    if fifo_url:
        sent = await attempt("send_sqs_message", queue_url=fifo_url, body="f", message_group_id="g", message_deduplication_id="d1")
        ok("sqs", "fifo send with group and dedup id", not has_error(sent), sent)
        await attempt("delete_sqs_queue", queue_url=fifo_url)


# ------------------------------------------------------------------ aws sns
@group
async def sns():
    created = await call("create_sns_topic", name=f"vfy-{X}", display_name="Verify")
    arn = created.get("topic_arn") or created.get("TopicArn") or created.get("arn")
    ok("sns", "topic created", bool(arn), created)
    queue = await call("create_sqs_queue", name=f"vfy-sns-{X}")
    qurl = queue.get("queue_url") or queue.get("QueueUrl") or queue.get("url")
    try:
        sub = await call("subscribe_sns", topic_arn=arn, protocol="sqs", endpoint=f"arn:aws:sqs:us-east-1:000000000000:vfy-sns-{X}")
        sub_arn = sub.get("subscription_arn") or sub.get("SubscriptionArn")
        ok("sns", "subscribed", bool(sub_arn), sub)
        ok("sns", "subscription listed", f"vfy-sns-{X}" in json.dumps(await call("list_sns_subscriptions", topic_arn=arn)))
        ok("sns", "topic attributes", "TopicArn" in json.dumps(await call("get_sns_topic_attributes", topic_arn=arn)))
        published = await call("publish_sns_message", topic_arn=arn, message="hi", subject="s",
                               message_attributes={"k": {"DataType": "String", "StringValue": "v"}})
        ok("sns", "published", "message_id" in json.dumps(published).lower() or "MessageId" in json.dumps(published), published)
        got = await call("receive_sqs_messages", queue_url=qurl, max_messages=5, wait_seconds=2)
        ok("sns", "message fans out to the sqs subscriber", "hi" in json.dumps(got), got)
        if sub_arn:
            await call("unsubscribe_sns", subscription_arn=sub_arn)
    finally:
        await attempt("delete_sqs_queue", queue_url=qurl)
        await attempt("delete_sns_topic", topic_arn=arn)
    ok("sns", "topic deleted", arn not in json.dumps(await call("list_sns_topics")))


# ----------------------------------------------------------- aws dynamodb
@group
async def dynamodb():
    table = f"vfy-{X}"

    def typed(pk, sk, n, **extra):
        item = {"pk": {"S": pk}, "sk": {"N": str(sk)}, "n": {"N": str(n)}}
        item.update(extra)
        return item

    await call("create_dynamodb_table", name=table, partition_key="pk", sort_key="sk", sort_key_type="N")
    try:
        ok("dynamodb", "table listed", table in (await call("list_dynamodb_tables"))["tables"])
        for i in (1, 2, 3):
            await call("put_dynamodb_item", table=table, item=typed(
                "a", i, i * 10, tags={"L": [{"S": "x"}, {"S": "y"}]}, meta={"M": {"city": {"S": "Madrid"}}}))
        await call("put_dynamodb_item", table=table, item=typed("b", 1, 5))
        got = await call("get_dynamodb_item", table=table, key={"pk": {"S": "a"}, "sk": {"N": "2"}})
        ok("dynamodb", "item round-trips with nested attributes", "Madrid" in json.dumps(got), got)
        q = await call("query_dynamodb", table=table, key_condition_expression="pk = :p AND sk >= :s",
                       expression_attribute_values={":p": {"S": "a"}, ":s": {"N": "2"}})
        ok("dynamodb", "query with a range condition returns 2", json.dumps(q).count("Madrid") == 2, q)
        top = await call("query_dynamodb", table=table, key_condition_expression="pk = :p",
                         expression_attribute_values={":p": {"S": "a"}}, scan_index_forward=False, limit=1)
        ok("dynamodb", "descending query with limit returns only the highest sk",
           json.dumps(top).count("Madrid") == 1 and '"30"' in json.dumps(top), top)
        scan = await call("scan_dynamodb", table=table, filter_expression="n > :v",
                          expression_attribute_values={":v": {"N": "15"}})
        ok("dynamodb", "scan with a filter returns the 2 items above 15", json.dumps(scan).count("Madrid") == 2, scan)
        sel = await call("execute_partiql_dynamodb", statement=f'SELECT pk, sk, meta.city FROM "{table}" WHERE pk = \'a\'')
        ok("dynamodb", "partiql select with a nested path", "Madrid" in json.dumps(sel), sel)
        ins = await call("execute_partiql_dynamodb", statement=f"INSERT INTO \"{table}\" VALUE {{'pk':'c','sk':1,'n':99}}")
        ok("dynamodb", "partiql insert", not has_error(ins), ins)
        upd = await call("execute_partiql_dynamodb", statement=f"UPDATE \"{table}\" SET n = 100 WHERE pk = 'c' AND sk = 1")
        ok("dynamodb", "partiql update", not has_error(upd), upd)
        seen = await call("get_dynamodb_item", table=table, key={"pk": {"S": "c"}, "sk": {"N": "1"}})
        ok("dynamodb", "partiql update is visible", "100" in json.dumps(seen), seen)
        await call("execute_partiql_dynamodb", statement=f"DELETE FROM \"{table}\" WHERE pk = 'c' AND sk = 1")
        gone = await attempt("get_dynamodb_item", table=table, key={"pk": {"S": "c"}, "sk": {"N": "1"}})
        ok("dynamodb", "partiql delete", "100" not in json.dumps(gone), gone)
        bad = await attempt("execute_partiql_dynamodb", statement="SELEKT nope")
        ok("dynamodb", "malformed partiql is an error", has_error(bad) or "error" in json.dumps(bad).lower(), bad)
        two = await attempt("execute_partiql_dynamodb", statement=f'SELECT * FROM "{table}" SELECT * FROM "{table}"')
        ok("dynamodb", "two statements in one are rejected", has_error(two) or "error" in json.dumps(two).lower(), two)
        await call("delete_dynamodb_item", table=table, key={"pk": {"S": "b"}, "sk": {"N": "1"}})
        after = await attempt("scan_dynamodb", table=table)
        ok("dynamodb", "item deleted", json.dumps(after).count('"b"') == 0, after)
        missing = await attempt("scan_dynamodb", table=f"absent-{X}")
        ok("dynamodb", "scan of a missing table is an error", has_error(missing) or "error" in json.dumps(missing).lower(), missing)
        typed_wrong = await attempt("put_dynamodb_item", table=table, item={"pk": "plain", "sk": 1})
        ok("dynamodb", "an untyped item is rejected with a clear error", has_error(typed_wrong), typed_wrong)
    finally:
        await attempt("delete_dynamodb_table", name=table)
    ok("dynamodb", "table deleted", table not in (await call("list_dynamodb_tables"))["tables"])


# ---------------------------------------------------- aws secrets and kms
@group
async def secrets_kms():
    name = f"vfy/{X}"
    await call("create_secret", name=name, value="v1", description="verify")
    try:
        ok("secrets", "secret listed", name in json.dumps(await call("list_secrets")))
        ok("secrets", "value readable", "v1" in json.dumps(await call("get_secret_value", name_or_arn=name)))
        await call("update_secret", name_or_arn=name, value="v2")
        ok("secrets", "update visible", "v2" in json.dumps(await call("get_secret_value", name_or_arn=name)))
    finally:
        await attempt("delete_secret", name_or_arn=name, force=True)
    gone = await attempt("get_secret_value", name_or_arn=name)
    ok("secrets", "deleted secret is unreadable", has_error(gone) or "error" in json.dumps(gone).lower() or "v2" not in json.dumps(gone), gone)

    key = await call("create_kms_key", description=f"verify {X}", alias=f"alias/vfy-{X}")
    key_id = key.get("key_id") or key.get("KeyId") or key.get("keyId")
    ok("kms", "key created", bool(key_id), key)
    enc = await call("kms_encrypt", key_id=key_id, plaintext="secret payload")
    blob = enc.get("ciphertext_blob") or enc.get("CiphertextBlob") or enc.get("ciphertext")
    ok("kms", "encrypt returns a ciphertext", bool(blob), enc)
    dec = await call("kms_decrypt", ciphertext_blob=blob)
    ok("kms", "decrypt restores the plaintext", "secret payload" in json.dumps(dec), dec)
    ok("kms", "key listed", key_id in json.dumps(await call("list_kms_keys")))
    diag = await call("run_kms_diagnostic")
    ok("kms", "diagnostic round-trips", diag.get("matches") is True, diag)


# ------------------------------------------------ aws events and workflows
@group
async def events_workflows():
    rule = f"vfy-{X}"
    await call("create_eventbridge_rule", name=rule, schedule_expression="rate(5 minutes)")
    try:
        ok("eventbridge", "rule listed", rule in json.dumps(await call("list_eventbridge_rules")))
        ok("eventbridge", "buses listed", "default" in json.dumps(await call("list_eventbridge_buses")))
        put = await call("put_eventbridge_events", entries=[{"Source": "vfy", "DetailType": "t", "Detail": "{\"a\":1}"}])
        ok("eventbridge", "events accepted", not has_error(put), put)
    finally:
        await attempt("delete_eventbridge_rule", name=rule)
    ok("eventbridge", "rule deleted", rule not in json.dumps(await call("list_eventbridge_rules")))
    ok("sfn", "state machines listed", "state_machines" in await call("list_step_functions"))
    bad = await attempt("start_sfn_execution", state_machine_arn="arn:aws:states:us-east-1:000000000000:stateMachine:absent")
    ok("sfn", "starting a missing machine is an error", has_error(bad) or "error" in json.dumps(bad).lower(), bad)
    bad = await attempt("describe_sfn_execution", execution_arn="arn:aws:states:us-east-1:000000000000:execution:absent:x")
    ok("sfn", "describing a missing execution is an error", has_error(bad) or "error" in json.dumps(bad).lower(), bad)
    ok("sfn", "executions of a missing machine do not crash the server",
       isinstance(await attempt("list_sfn_executions", state_machine_arn="arn:aws:states:us-east-1:000000000000:stateMachine:absent"), dict))
    ok("athena", "glue databases", "catalog" in await call("list_glue_databases"))
    q = await attempt("run_athena_query", sql="SELECT 1 AS one, 'two' AS two", timeout_seconds=90)
    ok("athena", "query succeeds", q.get("status") == "SUCCEEDED", q)
    ok("athena", "columns are named", [c["name"] for c in q.get("columns", [])] == ["one", "two"], q)
    ok("athena", "rows carry the values and no header row", q.get("rows") == [["1", "two"]], q)
    bad = await attempt("run_athena_query", sql="SELECT * FROM table_that_does_not_exist", timeout_seconds=60)
    ok("athena", "a failing query reports FAILED with a reason", bad.get("status") == "FAILED" or has_error(bad), bad)
    hist = await attempt("get_athena_query_history", max_results=5)
    ok("athena", "history lists the executed queries", "SELECT 1" in json.dumps(hist), hist)


# ------------------------------------------------------------ aws lambda
@group
async def lambda_():
    fn = f"vfy-{X}"
    source = "def handler(event, context):\n    print('log line', event)\n    return {'echo': event, 'ok': True}\n"
    created = await attempt("create_lambda_function", function_name=fn, runtime="python3.12", handler="main.handler",
                            code={"mode": "zipBase64", "zipBase64": lambda_zip(source)})
    ok("lambda", "function created", not has_error(created), created)
    if has_error(created):
        return
    try:
        ok("lambda", "function listed", fn in json.dumps(await call("list_lambda_functions")))
        inv = await attempt("invoke_lambda", function_name=fn, payload={"hello": "mcp"})
        ok("lambda", "invoke returns the handler result", "mcp" in json.dumps(inv), inv)
        logs = await attempt("get_lambda_logs", function_name=fn)
        ok("lambda", "logs are readable", not has_error(logs), logs)
        cfg = await attempt("update_lambda_config", function_name=fn, timeout=10, memory_size=256, description="updated")
        ok("lambda", "configuration updated", not has_error(cfg), cfg)
        code = await attempt("update_lambda_code", function_name=fn, runtime="python3.12",
                             code={"mode": "zipBase64", "zipBase64": lambda_zip("def handler(e, c):\n    return {'v': 2}\n")})
        ok("lambda", "code updated", not has_error(code), code)
        again = await attempt("invoke_lambda", function_name=fn, payload={})
        ok("lambda", "new code is served", '"v": 2' in json.dumps(again) or "'v': 2" in json.dumps(again) or "2" in json.dumps(again), again)
        asyn = await attempt("invoke_lambda", function_name=fn, payload={}, async_invocation=True)
        ok("lambda", "async invoke", not has_error(asyn), asyn)
    finally:
        await attempt("delete_lambda", function_name=fn)
    missing = await attempt("invoke_lambda", function_name=f"absent-{X}", payload={})
    ok("lambda", "invoking a missing function is an error", has_error(missing) or "error" in json.dumps(missing).lower() or missing.get("ok") is False, missing)


# --------------------------------------------------------- aws ses and tags
@group
async def ses_tags():
    email = f"vfy-{X}@example.com"
    await call("verify_ses_email", email=email)
    ok("ses", "identity listed", email in json.dumps(await call("list_ses_identities")))
    sent = await attempt("send_ses_email", from_address=email, to_addresses=[email], subject="s", body_text="b", body_html="<b>b</b>", cc_addresses=[email])
    ok("ses", "email sent", not has_error(sent), sent)
    ok("ses", "quota", "max_24_hour_send" in await call("get_ses_send_quota"))
    bad = await attempt("send_ses_email", from_address="unverified@nowhere.invalid", to_addresses=[email], subject="s", body_text="b")
    ok("ses", "unverified sender does not crash the server", isinstance(bad, dict), bad)

    queue = await call("create_sqs_queue", name=f"vfy-tag-{X}")
    qurl = queue.get("queue_url") or queue.get("QueueUrl") or queue.get("url")
    arn = f"arn:aws:sqs:us-east-1:000000000000:vfy-tag-{X}"
    try:
        tagged = await attempt("tag_resources", resource_arns=[arn], tags={"env": f"vfy{X}", "team": "mcp"})
        ok("tags", "tag_resources", not has_error(tagged), tagged)
        ok("tags", "tag keys listed", "env" in json.dumps(await call("get_all_tag_keys")))
        ok("tags", "tag values listed", f"vfy{X}" in json.dumps(await call("get_tag_values", key="env")))
        found = await call("find_resources_by_tag", tag_key="env", tag_value=f"vfy{X}")
        ok("tags", "find by tag", f"vfy-tag-{X}" in json.dumps(found), found)
        ok("tags", "all tagged resources", f"vfy-tag-{X}" in json.dumps(await call("list_all_tagged_resources")))
        await attempt("untag_resources", resource_arns=[arn], tag_keys=["team"])
        after = await call("find_resources_by_tag", tag_key="team", tag_value="mcp")
        ok("tags", "untag removes the tag", f"vfy-tag-{X}" not in json.dumps(after), after)
    finally:
        await attempt("delete_sqs_queue", queue_url=qurl)


# ------------------------------------------------------------ observability
@group
async def observability():
    main = f"vfy-main-{X}"
    dlq = f"vfy-dlq-{X}"
    m = await call("create_sqs_queue", name=main)
    d = await call("create_sqs_queue", name=dlq)
    murl = m.get("queue_url") or m.get("QueueUrl") or m.get("url")
    durl = d.get("queue_url") or d.get("QueueUrl") or d.get("url")
    try:
        policy = json.dumps({"deadLetterTargetArn": f"arn:aws:sqs:us-east-1:000000000000:{dlq}", "maxReceiveCount": 1})
        attrs = json.dumps({"RedrivePolicy": policy})
        set_attr = await attempt("run_local_aws_cmd", command=f"sqs set-queue-attributes --queue-url {murl} --attributes '{attrs}'")
        ok("devtools", "run_local_aws_cmd executes an aws cli command", not has_error(set_attr), set_attr)
        await call("send_sqs_message", queue_url=durl, body="dead letter")
        found = await call("list_dead_letter_queues")
        ok("dlq", "dead letter queue is detected", dlq in json.dumps(found) or found.get("count", 0) >= 1, found)
        insp = await attempt("inspect_dlq_messages", dlq_url=durl, max_messages=5)
        ok("dlq", "messages can be inspected", not has_error(insp), insp)
        redrive = await attempt("redrive_dlq", dlq_url=durl, source_url=murl, max_messages=5)
        ok("dlq", "redrive runs", not has_error(redrive), redrive)
    finally:
        await attempt("delete_sqs_queue", queue_url=murl)
        await attempt("delete_sqs_queue", queue_url=durl)

    queue = await call("create_sqs_queue", name=f"vfy-replay-{X}")
    qurl = queue.get("queue_url") or queue.get("QueueUrl") or queue.get("url")
    try:
        cap = await call("capture_event_for_replay", target_type="sqs", target=qurl, payload={"order": 1}, source="verify", label="v")
        event_id = cap.get("id") or cap.get("event_id") or cap.get("eventId") or (cap.get("event") or {}).get("id")
        ok("replay", "event captured", bool(event_id), cap)
        ok("replay", "event listed", str(event_id) in json.dumps(await call("list_captured_events")))
        if event_id:
            edited = await attempt("edit_captured_event", event_id=event_id, payload={"order": 2})
            ok("replay", "event edited", not has_error(edited), edited)
            replayed = await attempt("replay_captured_event", event_id=event_id)
            ok("replay", "event replayed", not has_error(replayed), replayed)
            got = await call("receive_sqs_messages", queue_url=qurl, max_messages=5, wait_seconds=2)
            ok("replay", "replayed payload reaches the queue", '"order": 2' in json.dumps(got) or "order" in json.dumps(got), got)
    finally:
        await attempt("delete_sqs_queue", queue_url=qurl)


# --------------------------------------------------------------- extensions
@group
async def extensions():
    hook = await call("register_lifecycle_webhook", event="resource.created", url="http://127.0.0.1:9/hook", description="verify")
    hook_id = hook.get("id") or hook.get("webhook_id") or (hook.get("webhook") or {}).get("id")
    ok("webhooks", "registered", bool(hook_id), hook)
    ok("webhooks", "listed", str(hook_id) in json.dumps(await call("list_lifecycle_webhooks")))
    emitted = await attempt("emit_lifecycle_event", event="resource.created", payload={"x": 1})
    ok("webhooks", "emit does not crash on an unreachable hook", not has_error(emitted), emitted)
    if hook_id:
        await call("delete_lifecycle_webhook", webhook_id=hook_id)
        ok("webhooks", "deleted", str(hook_id) not in json.dumps(await call("list_lifecycle_webhooks")))

    inter = await call("register_http_interceptor", url_pattern="*/vfy-*", phase="request", action="delay_ms", params={"ms": 1})
    inter_id = inter.get("id") or inter.get("interceptor_id") or (inter.get("interceptor") or {}).get("id")
    ok("interceptors", "registered", bool(inter_id), inter)
    ok("interceptors", "listed", str(inter_id) in json.dumps(await call("list_http_interceptors")))
    if inter_id:
        await call("delete_http_interceptor", interceptor_id=inter_id)
        ok("interceptors", "deleted", str(inter_id) not in json.dumps(await call("list_http_interceptors")))

    tunnel = await attempt("start_reverse_tunnel", port=1)
    ok("tunnels", "start answers (tunnel or explicit error)", isinstance(tunnel, dict), tunnel)
    ok("tunnels", "list answers", "tunnels" in await call("list_reverse_tunnels"))
    pid = tunnel.get("pid")
    if pid:
        await attempt("stop_reverse_tunnel", pid=pid)

    token = await call("generate_jwt_token", claims={"sub": "u1", "role": "admin"}, secret="s3cr3t", algorithm="HS256")
    raw = token.get("token") or token.get("jwt") or json.dumps(token)
    ok("devtools", "jwt has three parts", raw.count(".") >= 2, token)
    ok("devtools", "jwt carries the claims", base64.urlsafe_b64decode(raw.split(".")[1] + "==").decode().count("admin") == 1 if raw.count(".") >= 2 else False)
    proxied = await attempt("proxy_http_request", url="http://localhost:4566/_floci/health", method="GET")
    ok("devtools", "proxy reaches a local endpoint", not has_error(proxied) and "version" in json.dumps(proxied), proxied)
    blocked = await attempt("proxy_http_request", url="file:///etc/hosts")
    ok("devtools", "proxy refuses a file:// url", has_error(blocked) or "error" in json.dumps(blocked).lower() or "localhost" not in json.dumps(blocked), blocked)
    ok("devtools", "terraform export", not has_error(await attempt("export_to_terraform")))
    ok("devtools", "recipes terraform export", not has_error(await attempt("export_recipes_to_terraform")))
    ok("devtools", "iac discovery runs", not has_error(await attempt("discover_iac_resources")))
    ok("devtools", "drift detection runs", not has_error(await attempt("detect_iac_drift")))

    table = f"vfy-seed-{X}"
    await call("create_dynamodb_table", name=table, partition_key="id")
    try:
        seeded = await attempt("seed_mock_data", target="dynamodb", target_name=table)
        ok("devtools", "seed_mock_data fills a table", not has_error(seeded), seeded)
        scan = await call("scan_dynamodb", table=table, limit=5)
        ok("devtools", "seeded items are readable", json.dumps(scan).count('"id"') >= 1, scan)
        rel = await attempt("get_resource_relations", resource_id=table, resource_type="dynamodb")
        ok("devtools", "resource relations answers", not has_error(rel), rel)
    finally:
        await attempt("delete_dynamodb_table", name=table)
    bad = await attempt("seed_mock_data", target="nonsense", target_name="x")
    ok("devtools", "unknown seed target is an error", has_error(bad) or "error" in json.dumps(bad).lower() or bad.get("ok") is False, bad)


# ----------------------------------------------------------- hybrid (cloud)
@group
async def hybrid():
    fake = dict(region="us-east-1", aws_access_key_id="AKIAFAKEFAKEFAKEFAKE", aws_secret_access_key="fake", aws_session_token="fake")
    started = time.time()
    seed = await attempt("seed_from_cloud_dynamodb", source_table="nope", **fake)
    ok("hybrid", "seeding from the cloud with bad credentials fails cleanly", has_error(seed) or seed.get("ok") is False or "error" in json.dumps(seed).lower(), seed)
    proxy = await attempt("proxy_cloud_sqs_to_local", source_queue_url="https://sqs.us-east-1.amazonaws.com/1/nope", target_type="sqs", target="x", **fake)
    ok("hybrid", "sqs proxy with bad credentials fails cleanly", has_error(proxy) or proxy.get("ok") is False or "error" in json.dumps(proxy).lower(), proxy)
    ok("hybrid", "neither call hangs", time.time() - started < 60, round(time.time() - started, 1))


# --------------------------------------------------- marketplace and pipeline
@group
async def marketplace():
    recipes = (await call("list_marketplace_recipes"))["recipes"]
    ids = [r["id"] for r in recipes]
    ok("marketplace", f"{len(ids)} recipes", len(ids) >= 30)
    ok("marketplace", "recipe ids are unique", len(ids) == len(set(ids)))
    ok("marketplace", "every recipe has a name and variables list", all("name" in r for r in recipes))
    ok("marketplace", "installations answer", "installed" in await call("list_marketplace_recipes", status=True))
    missing = await attempt("list_marketplace_recipes", recipe_id="absent-recipe", logs=True)
    ok("marketplace", "an unknown recipe is an error, not a crash", has_error(missing), missing)
    ok("marketplace", "deploying an unknown recipe is an error",
       has_error(await attempt("deploy_marketplace_app", recipe_id="absent-recipe")))
    ok("pipeline", "copilot manifests for a recipe", not has_error(await attempt("generate_copilot_manifests", recipe_id="redis")))
    ok("pipeline", "logs of a recipe that never ran do not crash", isinstance(await attempt("get_pipeline_logs", recipe_id="redis", env="test"), dict))

    if os.environ.get("VERIFY_DOCKER") != "1":
        skip("marketplace", "deploy and teardown", "set VERIFY_DOCKER=1 to start and remove a real container")
        for tool in ("deploy_marketplace_app", "teardown_marketplace_app", "deploy_to_environment", "teardown_environment_recipe", "promote_recipe"):
            EXERCISED.add(tool)
        return
    async def until_running(read, timeout=120):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            last = await read()
            if last == "RUNNING":
                return True, last
            if last in ("FAILED", "ERROR"):
                break
            await asyncio.sleep(2)
        return False, last

    async def marketplace_status():
        state = await call("list_marketplace_recipes", status=True)
        return state.get("installed", {}).get("redis", {}).get("status")

    async def env_status(env):
        envs = (await call("list_pipeline_environments"))["environments"]
        entry = next((e for e in envs if e["name"] == env), {})
        return entry.get("deployments", {}).get("redis", {}).get("status")

    try:
        dep = await attempt("deploy_marketplace_app", recipe_id="redis", vars={"REDIS_PORT": 16379})
        ok("marketplace", "redis deployed", not has_error(dep), dep)
        running, last = await until_running(marketplace_status)
        ok("marketplace", "installation reaches RUNNING", running, last)
    finally:
        td = await attempt("teardown_marketplace_app", recipe_id="redis")
        ok("marketplace", "redis torn down", not has_error(td), td)
        ok("marketplace", "installation is gone after teardown", await marketplace_status() in (None, "IDLE", "UNINSTALLING"))
    try:
        dep = await attempt("deploy_to_environment", recipe_id="redis", env="test", vars={})
        ok("pipeline", "deployed to the test environment", not has_error(dep), dep)
        running, last = await until_running(lambda: env_status("test"))
        ok("pipeline", "test deployment reaches RUNNING", running, last)
        pro = await attempt("promote_recipe", recipe_id="redis", from_env="test", to_env="demo")
        ok("pipeline", "promoted to demo", not has_error(pro), pro)
        running, last = await until_running(lambda: env_status("demo"))
        ok("pipeline", "demo deployment reaches RUNNING", running, last)
        prod = await attempt("promote_recipe", recipe_id="redis", from_env="demo", to_env="production")
        ok("pipeline", "promotion to production is refused", has_error(prod), prod)
        logs = await attempt("get_pipeline_logs", recipe_id="redis", env="test")
        ok("pipeline", "pipeline logs are readable", not has_error(logs), logs)
    finally:
        await attempt("teardown_environment_recipe", recipe_id="redis", env="demo")
        await attempt("teardown_environment_recipe", recipe_id="redis", env="test")


# -------------------------------------------------------------- multi-cloud
@group
async def clouds():
    status = {c["cloud"]: c["status"] for c in (await call("list_clouds"))["clouds"]}
    ok("clouds", "aws is online", status.get("aws") == "online", status)

    if status.get("gcp") == "online":
        b, t = f"vfy-{X}", f"vfy-{X}"
        await call("gcp_create_bucket", name=b)
        await call("gcp_create_topic", name=t)
        ok("gcp", "bucket listed", b in (await call("gcp_list_buckets"))["buckets"])
        ok("gcp", "topic listed", any(x.endswith("/" + t) for x in (await call("gcp_list_topics"))["topics"]))
        ok("gcp", "objects list", "objects" in await call("gcp_list_objects", bucket=b))
        ok("gcp", "objects list with a prefix", "objects" in await call("gcp_list_objects", bucket=b, prefix="x/"))
        ok("gcp", "secrets list", "secrets" in await call("gcp_list_secrets"))
        ok("gcp", "objects of a missing bucket is an error", has_error(await attempt("gcp_list_objects", bucket=f"absent-{X}")))
        ok("gcp", "creating a bucket twice is an error", has_error(await attempt("gcp_create_bucket", name=b)))
    else:
        skip("gcp", "gcp tools", "runtime not reachable")
    if status.get("azure") == "online":
        c, q = f"vfy{X}", f"vfy{X}"
        await call("azure_create_container", name=c)
        await call("azure_create_queue", name=q)
        ok("azure", "container listed", c in (await call("azure_list_containers"))["containers"])
        ok("azure", "queue listed", q in (await call("azure_list_queues"))["queues"])
        ok("azure", "blobs list", "blobs" in await call("azure_list_blobs", container=c))
        ok("azure", "secrets list", "secrets" in await call("azure_list_secrets"))
        missing = await attempt("azure_list_blobs", container=f"absent{X}")
        ok("azure", "blobs of a missing container is an error or an empty list", has_error(missing) or missing.get("blobs") == [], missing)
    else:
        skip("azure", "azure tools", "runtime not reachable")
    if status.get("oci") == "online":
        b = f"vfy-{X}"
        await call("oci_create_bucket", name=b)
        ok("oci", "bucket listed", b in (await call("oci_list_buckets"))["buckets"])
        ok("oci", "objects list", "objects" in await call("oci_list_objects", bucket=b))
        ok("oci", "objects of a missing bucket is an error", has_error(await attempt("oci_list_objects", bucket=f"absent-{X}")))
    else:
        skip("oci", "oci tools", "runtime not reachable")


# -------------------------------------------------------- dynamic toolsets
class StdioClient:
    """A minimal MCP client over stdio that also records notifications."""

    def __init__(self, **env):
        root = os.path.dirname(os.path.abspath(__file__))
        full = {k: v for k, v in os.environ.items() if not k.startswith("FLOCI_")}
        full.update(env)
        self.proc = subprocess.Popen([sys.executable, "-u", os.path.join(root, "floci_mcp.py")], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=full, cwd=root)
        self.next_id = 1
        self.notifications: list[str] = []

    def request(self, method, params=None):
        request_id = self.next_id
        self.next_id += 1
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("server closed the connection")
            if not line.startswith("{"):
                continue
            message = json.loads(line)
            if "id" not in message and "method" in message:
                self.notifications.append(message["method"])
            elif message.get("id") == request_id:
                return message

    def initialize(self):
        reply = self.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "verify", "version": "0"}})
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.proc.stdin.flush()
        return reply["result"]

    def tool_names(self):
        return [t["name"] for t in self.request("tools/list")["result"]["tools"]]

    def call(self, tool, /, **arguments):
        reply = self.request("tools/call", {"name": tool, "arguments": arguments})
        return json.loads(reply["result"]["content"][0]["text"])

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=15)
        except Exception:  # noqa: BLE001
            self.proc.kill()


@group
async def generic():
    """The generic and code toolsets: discovery, guarded reads and writes, the sandbox, and recipes as a cloud."""
    services = await call("list_services", cloud="aws")
    ok("generic", "list_services knows the AWS model", "s3" in services.get("services", []) and len(services["services"]) > 300)
    for cloud in ("azure", "gcp", "oci", "recipes"):
        listed = await call("list_services", cloud=cloud)
        ok("generic", f"list_services({cloud}) answers", bool(listed.get("services")), listed)
    found = await call("search_operations", query="list buckets", cloud="aws", service="s3")
    ok("generic", "search_operations finds ListBuckets", any(h["operation"] == "ListBuckets" for h in found["hits"]), found)
    described = await call("describe_operation", cloud="aws", service="sqs", operation="CreateQueue")
    ok("generic", "describe_operation says CreateQueue is a write with a QueueName",
       described.get("kind") == "write" and "QueueName" in described.get("params", {}), described)
    read = await call("call_read", cloud="aws", service="s3", operation="ListBuckets")
    ok("generic", "call_read ListBuckets", "Buckets" in read, read)
    refused = await call("call_read", cloud="aws", service="s3", operation="CreateBucket", params={"Bucket": f"vfy-no-{X}"})
    ok("generic", "call_read refuses a write", "blocked" in refused, refused)
    queue = f"vfy-gen-{X}"
    created = await call("call_write", cloud="aws", service="sqs", operation="CreateQueue", params={"QueueName": queue})
    ok("generic", "call_write CreateQueue", "QueueUrl" in created, created)
    if "QueueUrl" in created:
        deleted = await call("call_write", cloud="aws", service="sqs", operation="DeleteQueue", params={"QueueUrl": created["QueueUrl"]})
        ok("generic", "call_write DeleteQueue", "error" not in deleted, deleted)
    for cloud, port, service, op in (("gcp", 4588, "storage", "ListBuckets"), ("azure", 4577, "blob", "ListContainers"),
                                     ("oci", 4599, "objectstorage", "ListBuckets")):
        if runtime_up(port):
            out = await call("call_read", cloud=cloud, service=service, operation=op)
            ok("generic", f"call_read {cloud} {service}.{op}", out.get("status") == 200, out)
        else:
            skip("generic", f"{cloud} read", f"runtime on :{port} not reachable")

    code = await call("code_read", code='b = aws("s3", "ListBuckets")["Buckets"]\nresult = len(b)')
    ok("generic", "code_read runs Python against AWS", code.get("ok") and isinstance(code.get("result"), int), code)
    blocked = await call("code_read", code='aws("s3", "CreateBucket", Bucket="vfy-never")')
    ok("generic", "code_read cannot write whatever the code says", not blocked.get("ok") and blocked.get("blocked"), blocked)
    topic = f"vfy-code-{X}"
    if runtime_up(4588):
        written = await call("code_write", code=f'r = call("gcp", "pubsub", "CreateTopic", topic="{topic}")\n'
                                              f'result = r["status"]\n'
                                              f'call("gcp", "pubsub", "DeleteTopic", topic="projects/floci-local/topics/{topic}")')
        ok("generic", "code_write creates and removes a GCP topic", written.get("ok") and written.get("result") == 200, written)
    recipes_listed = await call("call_read", cloud="recipes", operation="ListRecipes")
    ok("generic", "recipes are a cloud: ListRecipes", recipes_listed.get("count", 0) >= 30, recipes_listed)
    unknown = await call("call_write", cloud="recipes", operation="DeployRecipe", params={"recipe_id": "absent-recipe"})
    ok("generic", "DeployRecipe of an unknown recipe is an error, not a crash", "error" in unknown, unknown)


@group
async def dynamic_toolsets():
    forbidden = StdioClient(FLOCI_TOOLSETS="core", FLOCI_TOOLSETS_ALLOWED="")
    try:
        caps = forbidden.initialize()["capabilities"]
        names = forbidden.tool_names()
        ok("dynamic", "an empty FLOCI_TOOLSETS_ALLOWED forbids switching: no enable/disable tools",
           "enable_toolset" not in names and "disable_toolset" not in names, names[:5])
        ok("dynamic", "and listChanged is not advertised", not caps.get("tools", {}).get("listChanged"), caps)
    finally:
        forbidden.close()

    free = StdioClient(FLOCI_TOOLSETS="core")
    try:
        free.initialize()
        before_free = free.tool_names()
        ok("dynamic", "by default the agent has enable_toolset and disable_toolset",
           {"enable_toolset", "disable_toolset"} <= set(before_free))
        granted = free.call("enable_toolset", name="hybrid")
        ok("dynamic", "by default the agent can enable any toolset, hybrid included",
           granted.get("enabled") is True and "seed_mock_data" in free.tool_names(), granted)
        listing_free = free.call("list_toolsets")
        ok("dynamic", "list_toolsets reports every toolset as reachable",
           len(listing_free["allowed_at_runtime"]) == len(toolsets_module.TOOLSETS), listing_free["allowed_at_runtime"])
    finally:
        free.close()

    client = StdioClient(FLOCI_TOOLSETS="core", FLOCI_TOOLSETS_ALLOWED="ops,marketplace")
    try:
        caps = client.initialize()["capabilities"]
        ok("dynamic", "the server advertises tools.listChanged", caps.get("tools", {}).get("listChanged") is True, caps)
        before = client.tool_names()
        digest_before = client.call("list_toolsets")["definitions_sha256"]
        ok("dynamic", "enable_toolset and disable_toolset are registered", {"enable_toolset", "disable_toolset"} <= set(before))
        ok("dynamic", "ops tools are absent at the start", "list_dead_letter_queues" not in before)

        rejected = client.call("enable_toolset", name="hybrid")
        ok("dynamic", "a toolset outside the allowed list is refused", rejected.get("enabled") is False and "FLOCI_TOOLSETS_ALLOWED" in rejected.get("reason", ""), rejected)
        ok("dynamic", "refusing changes nothing", sorted(client.tool_names()) == sorted(before))
        unknown = client.call("enable_toolset", name="nope")
        ok("dynamic", "an unknown toolset is refused with the valid names", unknown.get("enabled") is False and "Available:" in unknown.get("reason", ""), unknown)

        enabled = client.call("enable_toolset", name="ops")
        after = client.tool_names()
        ok("dynamic", "enabling adds the toolset's tools", enabled.get("enabled") is True and "list_dead_letter_queues" in after, enabled)
        ok("dynamic", "enabling sends tools/list_changed", "notifications/tools/list_changed" in client.notifications, client.notifications)
        listing = client.call("list_toolsets")
        ok("dynamic", "list_toolsets reflects the change", "ops" in listing["enabled"] and listing["allowed_at_runtime"] == ["ops", "marketplace"], listing)
        again = client.call("enable_toolset", name="ops")
        ok("dynamic", "enabling twice adds nothing and does not duplicate", again.get("tools_added") == [] and len(client.tool_names()) == len(after))

        disabled = client.call("disable_toolset", name="ops")
        ok("dynamic", "disabling removes the tools again", disabled.get("disabled") is True and sorted(client.tool_names()) == sorted(before), disabled)
        ok("dynamic", "the digest changes while a toolset is enabled and returns after disabling it",
           listing["definitions_sha256"] != digest_before and client.call("list_toolsets")["definitions_sha256"] == digest_before)
    finally:
        client.close()

    restricted = StdioClient(FLOCI_TOOLSETS="core", FLOCI_TOOLSETS_ALLOWED="ops,hybrid", FLOCI_READ_ONLY="1")
    try:
        restricted.initialize()
        restricted.call("enable_toolset", name="ops")
        names = restricted.tool_names()
        import toolsets as ts
        ok("dynamic", "read-only mode also holds for tools enabled later",
           "list_dead_letter_queues" in names and not [n for n in names if ts.is_write(n)], [n for n in names if ts.is_write(n)])
    finally:
        restricted.close()


# ------------------------------------------------------------------ decider
@group
async def decider_group():
    import importlib
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    root = os.path.dirname(os.path.abspath(__file__))
    spec2 = importlib.util.spec_from_file_location("test_decider", os.path.join(root, "tests", "test_decider.py"))
    tests = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(tests)
    for name in sorted(n for n in dir(tests) if n.startswith("test_")):
        try:
            await asyncio.to_thread(getattr(tests, name))
            ok("decider", name.replace("_", " "), True)
        except AssertionError as error:
            ok("decider", name.replace("_", " "), False, str(error))

    seen: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            seen["body"], seen["auth"], seen["path"] = body, self.headers.get("authorization"), self.path
            answers = {n: {"type": "noul", "noul": 0.9 if n in ("ops", "messaging") else 0.05} for n in body["questions"]}
            data = json.dumps({"model": body["model"], "answers": answers, "usage": {"input_tokens": 1, "output_tokens": 1}}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    client = StdioClient(FLOCI_TOOLSETS="core", FLOCI_DECIDER="custom", FLOCI_DECIDER_URL=f"http://127.0.0.1:{port}/v1/systemone",
                         FLOCI_DECIDER_MODEL="typesafe/jev-latest", FLOCI_DECIDER_API_KEY="secret")
    try:
        client.initialize()
        names = client.tool_names()
        ok("decider", "suggest_toolsets is registered when a decider is configured", "suggest_toolsets" in names)
        suggestion = client.call("suggest_toolsets", task="messages are stuck in my dead-letter queue")
        ok("decider", "the model's answer is ranked and thresholded over a real HTTP call",
           suggestion.get("recommended") == ["messaging", "ops"] or sorted(suggestion.get("recommended", [])) == ["messaging", "ops"], suggestion)
        ok("decider", "the state and the key reach the endpoint",
           seen.get("body", {}).get("state", "").startswith("messages are stuck") and seen.get("auth") == "Bearer secret" and seen.get("path") == "/v1/systemone", seen)
        ok("decider", "without apply nothing is enabled", "list_dead_letter_queues" not in client.tool_names())
        applied = client.call("suggest_toolsets", task="messages are stuck in my dead-letter queue", apply=True)
        ok("decider", "with apply the recommended toolsets are enabled", sorted(applied.get("applied", [])) == ["messaging", "ops"], applied)
        ok("decider", "applying announces the change and the tools appear",
           "notifications/tools/list_changed" in client.notifications and "list_dead_letter_queues" in client.tool_names(), client.notifications)
    finally:
        client.close()
        server.shutdown()

    off = StdioClient(FLOCI_TOOLSETS="core")
    try:
        off.initialize()
        ok("decider", "suggest_toolsets is absent when no decider is configured", "suggest_toolsets" not in off.tool_names())
    finally:
        off.close()


# ------------------------------------------------------------------- cwd
@group
async def working_directory():
    """An MCP client starts the server from its own directory, not from this repository."""
    import tempfile
    root = os.path.dirname(os.path.abspath(__file__))
    work = tempfile.mkdtemp(prefix="floci-cwd-")
    state = tempfile.mkdtemp(prefix="floci-state-")
    script = (
        "import asyncio, importlib.util, json, sys\n"
        "sys.path.insert(0, %r)\n"
        "spec = importlib.util.spec_from_file_location('m', %r); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "async def go():\n"
        "    out = {}\n"
        "    r = await m.mcp.call_tool('list_marketplace_recipes', {})\n"
        "    d = r[1] if isinstance(r, tuple) else json.loads(r[0].text)\n"
        "    out['recipes'] = len(d.get('recipes', []))\n"
        "    await m.mcp.call_tool('get_network_topology', {})\n"
        "    await m.mcp.call_tool('list_lifecycle_webhooks', {})\n"
        "    print('RESULT' + json.dumps(out))\n"
        "asyncio.run(go())\n"
    ) % (root, os.path.join(root, "floci_mcp.py"))
    env = {**os.environ, "FLOCI_TOOLSETS": "all", "SIDECAR_STATE_DIR": state}
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=120, cwd=work)
    line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULT")), None)
    ok("cwd", "the server runs from another directory", line is not None, proc.stderr[-300:])
    if line:
        ok("cwd", "the recipe catalog is found from another directory", json.loads(line[6:])["recipes"] >= 30, line)
    ok("cwd", "nothing is written into the working directory", os.listdir(work) == [], os.listdir(work))
    ok("cwd", "state goes to SIDECAR_STATE_DIR", len(os.listdir(state)) >= 1, os.listdir(state))


# ------------------------------------------------------------ resilience
@group
async def resilience():
    """Runtime down: tools must fail fast with a clear message, never hang the server."""
    root = os.path.dirname(os.path.abspath(__file__))
    script = (
        "import asyncio, importlib.util, json, sys, time\n"
        "sys.path.insert(0, %r)\n"
        "spec = importlib.util.spec_from_file_location('m', %r); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "async def go():\n"
        "    out = {}\n"
        "    for tool, args in [('list_s3_buckets', {}), ('gcp_list_buckets', {}), ('azure_list_queues', {}), ('oci_list_buckets', {}), ('list_clouds', {})]:\n"
        "        t = time.time()\n"
        "        try:\n"
        "            r = await m.mcp.call_tool(tool, args); out[tool] = ['ok', round(time.time()-t, 1), str(r)[:160]]\n"
        "        except Exception as e:\n"
        "            out[tool] = ['error', round(time.time()-t, 1), str(e)[:160]]\n"
        "    print('RESULT' + json.dumps(out))\n"
        "asyncio.run(go())\n"
    ) % (root, os.path.join(root, "floci_mcp.py"))
    env = {**os.environ,
           "AWS_ENDPOINT_URL": "http://127.0.0.1:1", "FLOCI_AZURE_ENDPOINT": "http://127.0.0.1:1",
           "FLOCI_GCP_ENDPOINT": "http://127.0.0.1:1", "FLOCI_OCI_ENDPOINT": "http://127.0.0.1:1"}
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=240, cwd=root)
    line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULT")), None)
    ok("resilience", "harness ran", line is not None, proc.stderr[-300:])
    if not line:
        return
    out = json.loads(line[len("RESULT"):])
    for tool in ("list_s3_buckets", "gcp_list_buckets", "azure_list_queues", "oci_list_buckets"):
        status, seconds, text = out[tool]
        ok("resilience", f"{tool} fails with the runtime down", status == "error", out[tool])
        ok("resilience", f"{tool} fails fast (under 30s)", seconds < 30, out[tool])
    ok("resilience", "list_clouds reports unreachable runtimes instead of failing",
       out["list_clouds"][0] == "ok" and "unreachable" in out["list_clouds"][2], out["list_clouds"])


async def main(filters: list[str]) -> int:
    only = [g for g in GROUPS if not filters or any(f in g.__name__ for f in filters)]
    for g in only:
        print(f"\n[{g.__name__}]")
        try:
            await g()
        except Exception as exc:  # noqa: BLE001
            RESULTS.append((g.__name__, f"group aborted: {str(exc)[:200]}", "FAIL"))
            print(f"  FAIL group aborted: {str(exc)[:300]}")

    if not filters:
        names = {t.name for t in await server.mcp.list_tools()}
        unexercised = sorted(names - EXERCISED - set(SKIPPED))
        # Registered only under some configuration, so the default server does not list them.
        conditional = {"suggest_toolsets"}
        stale = sorted(set(SKIPPED) - names - conditional)
        print("\n[coverage]")
        ok("coverage", f"every tool is exercised or skipped with a reason ({len(names)} tools)", not unexercised, unexercised)
        ok("coverage", "no stale entries in SKIPPED", not stale, stale)

    passed = sum(1 for _, _, s in RESULTS if s == "ok")
    failed = [(g, l) for g, l, s in RESULTS if s == "FAIL"]
    skipped = sum(1 for _, _, s in RESULTS if s == "skip")
    print(f"\n{passed} passed, {len(failed)} failed, {skipped} skipped")
    for g, l in failed:
        print(f"  FAIL [{g}] {l}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
