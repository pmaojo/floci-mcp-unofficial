"""Eval for the generic arms: B (generic toolset, 5 tools) and C (code toolset, 2 tools) against A (curated).

The curated eval (run.py) scores the first tool call. That cannot score B or C: their
first call is rightly a search or a describe. So here the model runs a loop, reads are
executed against the live Floci, and writes are recorded as a dry run and never sent.
A task passes when the recorded calls contain the expected operation.

    uv run python eval/generic.py static                 # tokens of A, B and C definitions
    uv run python eval/generic.py oracle                 # is every expected operation real, and classified as expected?
    uv run python eval/generic.py search                 # can search_operations put it in the top 5? (offline)
    uv run python eval/generic.py model --arms generic,code     # needs ANTHROPIC_API_KEY and a running Floci

Tasks that are not one cloud operation (health, cost, graph, drift, recipes, JWT, seed...) have
`curated: true` and are reported apart: they are where the curated tools are meant to stay.
"""
import argparse
import asyncio
import importlib.util
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mcp.server.fastmcp import FastMCP  # noqa: E402

import toolsets  # noqa: E402
from floci_generic import catalog, gateway as gateway_module  # noqa: E402
from floci_generic.classify import classify_rest  # noqa: E402

_spec = importlib.util.spec_from_file_location("floci_eval_run", os.path.join(ROOT, "eval", "run.py"))
curated = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(curated)

DEFAULT_MODEL = os.environ.get("FLOCI_EVAL_MODEL", "claude-sonnet-5-5")
MAX_TURNS = 8
SYSTEM = (
    "You operate local cloud emulators (AWS, Azure, GCP, OCI) through tools. Complete the user's request. "
    "Look operations up before guessing their names or parameters. Do not ask questions; use sensible defaults."
)

# id -> expectation. `any` lists acceptable operations (a task can be done in more than one way);
# `args` are substrings that must appear in the parameters of the matching call.
G = lambda cloud, service, *ops, **args: {"cloud": cloud, "service": service, "any": list(ops), "args": args}  # noqa: E731
EXPECTED = {
    "s3-list": G("aws", "s3", "ListBuckets"),
    "s3-create": G("aws", "s3", "CreateBucket", Bucket="invoices-2026"),
    "s3-put": G("aws", "s3", "PutObject", Bucket="demo", Key="greeting.txt"),
    "sqs-create": G("aws", "sqs", "CreateQueue", QueueName="orders"),
    "sqs-send": G("aws", "sqs", "SendMessage", MessageBody="ship it"),
    "sqs-receive": G("aws", "sqs", "ReceiveMessage"),
    "dlq-list": G("aws", "sqs", "ListDeadLetterSourceQueues", "ListQueues", "GetQueueAttributes"),
    "dlq-redrive": G("aws", "sqs", "StartMessageMoveTask"),
    "sns-publish": G("aws", "sns", "Publish", Message="deploy done"),
    "sns-subscribe": G("aws", "sns", "Subscribe"),
    "ddb-create": G("aws", "dynamodb", "CreateTable", TableName="users"),
    "ddb-partiql": G("aws", "dynamodb", "ExecuteStatement"),
    "ddb-get": G("aws", "dynamodb", "GetItem"),
    "secret-create": G("aws", "secretsmanager", "CreateSecret", Name="db-password"),
    "secret-read": G("aws", "secretsmanager", "GetSecretValue"),
    "kms-encrypt": G("aws", "kms", "Encrypt"),
    "lambda-create": G("aws", "lambda", "CreateFunction", FunctionName="hello"),
    "lambda-invoke": G("aws", "lambda", "Invoke", FunctionName="hello"),
    "lambda-logs": G("aws", "logs", "FilterLogEvents", "GetLogEvents", "DescribeLogStreams"),
    "athena": G("aws", "athena", "StartQueryExecution"),
    "sfn-start": G("aws", "stepfunctions", "StartExecution"),
    "events-rule": G("aws", "events", "PutRule", Name="nightly"),
    "ses-verify": G("aws", "ses", "VerifyEmailIdentity", "VerifyEmailAddress"),
    "tags-apply": G("aws", "resourcegroupstaggingapi", "TagResources"),
    "tags-find": G("aws", "resourcegroupstaggingapi", "GetResources"),
    "gcp-buckets": G("gcp", "storage", "ListBuckets"),
    "gcp-topic": G("gcp", "pubsub", "CreateTopic", topic="events"),
    "azure-queue": G("azure", "queue", "CreateQueue", queue="jobs"),
    "oci-buckets": G("oci", "objectstorage", "ListBuckets"),
}
# Several calls, sometimes across clouds. Every step must be reached. A curated tool cannot do these in
# one call, so these are where the code arm is expected to earn its keep. All of them are reads.
CHAINED = {
    "chain-queue-depth": ("How many messages are waiting in each of my SQS queues? Only list the queues that have any.",
                          [("aws", "sqs", "ListQueues"), ("aws", "sqs", "GetQueueAttributes")]),
    "chain-bucket-objects": ("List my S3 buckets and tell me how many objects each one holds.",
                             [("aws", "s3", "ListBuckets"), ("aws", "s3", "ListObjectsV2")]),
    "chain-bucket-compare": ("Which bucket names exist on both AWS S3 and GCP Cloud Storage?",
                             [("aws", "s3", "ListBuckets"), ("gcp", "storage", "ListBuckets")]),
    "chain-queue-inventory": ("How many queues do I have on AWS, Azure and OCI? Give me one count per cloud.",
                              [("aws", "sqs", "ListQueues"), ("azure", "queue", "ListQueues"), ("oci", "queue", "ListQueues")]),
    "chain-empty-tables": ("Which of my DynamoDB tables are empty?",
                           [("aws", "dynamodb", "ListTables"), ("aws", "dynamodb", "Scan")]),
}
# Not one cloud operation: they stay curated (health, cost, graph, drift, recipes, tokens, seeding...).
CURATED_ONLY = {"health", "clouds", "cost", "s3-presign", "graph", "drift", "recipes", "recipe-deploy", "jwt", "seed", "proxy"}


def load_tasks() -> list[dict]:
    with open(os.path.join(ROOT, "eval", "tasks.json")) as handle:
        tasks = json.load(handle)
    out = []
    for task in tasks:
        if task["id"] in EXPECTED:
            out.append({**task, **EXPECTED[task["id"]]})
        else:
            assert task["id"] in CURATED_ONLY, f"task {task['id']} has no expectation and is not marked curated"
            out.append({**task, "curated": True})
    for task_id, (prompt, steps) in CHAINED.items():
        out.append({"id": task_id, "prompt": prompt, "chained": True, "steps": steps, "cloud": steps[0][0],
                    "service": steps[0][1], "any": [steps[0][2]], "args": {}})
    return out


def arm_selection(arm: str) -> tuple[str, ...]:
    return {"generic": ("generic",), "code": ("code",)}[arm]


# --------------------------------------------------------------------- static
async def run_static() -> None:
    rows = []
    for name, selection in [("A  default (curated)", toolsets.DEFAULT_TOOLSETS), ("A  all (curated)", tuple(toolsets.TOOLSETS)),
                            ("B  generic", ("generic",)), ("C  code", ("code",))]:
        if name.startswith("A  all"):
            selection = tuple(t for t in toolsets.TOOLSETS if t not in ("generic", "code"))
        defs = await curated.definitions(selection)
        rows.append([name, len(defs), curated.tokens_of(defs)])
    print(curated.table(rows, ["arm", "tools", "~tokens"]))


# --------------------------------------------------------------------- oracle
def run_oracle(tasks: list[dict]) -> int:
    """Checks the ground truth itself: the operation exists and the verdict is the one the task expects."""
    problems = 0
    rows = []
    for task in tasks:
        if task.get("curated"):
            continue
        if task.get("chained"):
            for cloud, service, op in task["steps"]:
                if cloud == "aws":
                    resolved = catalog.resolve_aws_operation(service, op) if catalog.has_aws_service(service) else None
                    kind = catalog.aws_verdict(service, resolved).kind if resolved else "UNKNOWN"
                else:
                    info = catalog.describe_rest(cloud, service, op)
                    kind = info["kind"] if info else "UNKNOWN"
                if kind != "read":
                    problems += 1
                rows.append([task["id"], f"{cloud}:{service}.{op}", kind])
            continue
        for op in task["any"]:
            if task["cloud"] == "aws":
                if not catalog.has_aws_service(task["service"]):
                    rows.append([task["id"], op, "UNKNOWN SERVICE"]); problems += 1
                    continue
                resolved = catalog.resolve_aws_operation(task["service"], op)
                if resolved is None:
                    rows.append([task["id"], op, "UNKNOWN OPERATION"]); problems += 1
                    continue
                verdict = catalog.aws_verdict(task["service"], resolved)
                rows.append([task["id"], f"{task['service']}.{resolved}", verdict.kind + (" (sensitive)" if verdict.sensitive else "") + (" destructive" if verdict.destructive else "")])
            else:
                info = catalog.describe_rest(task["cloud"], task["service"], op)
                if info is None:
                    rows.append([task["id"], op, "NOT IN REST CATALOG"]); problems += 1
                    continue
                verdict = classify_rest(task["cloud"], info["method"], info["path"])
                rows.append([task["id"], f"{task['cloud']}:{task['service']}.{info['operation']}", verdict.kind])
    print(curated.table(rows, ["task", "operation", "verdict"]))
    print(f"\n{problems} problem(s)")
    return 1 if problems else 0


# --------------------------------------------------------------------- search
def run_search(tasks: list[dict]) -> None:
    """The offline floor for B: with only the prompt (and the cloud), is the operation in the top k?"""
    rows = []
    totals = {"top1": 0, "top3": 0, "top5": 0, "n": 0}
    misses = []
    for task in tasks:
        if task.get("curated") or task.get("chained"):
            continue
        hits = catalog.search(task["prompt"], task["cloud"], None, 10)
        wanted = {(task["service"], op.lower()) for op in task["any"]}
        ranked = [(h["service"], h["operation"].lower()) for h in hits]
        rank = next((i + 1 for i, h in enumerate(ranked) if h in wanted), None)
        totals["n"] += 1
        for k in (1, 3, 5):
            totals[f"top{k}"] += bool(rank and rank <= k)
        rows.append([task["id"], task["cloud"], rank or ">10", ", ".join(f"{s}.{o}" for s, o in ranked[:3])])
        if not rank or rank > 3:
            misses.append(task["id"])
    print(curated.table(rows, ["task", "cloud", "rank", "top 3"]))
    n = totals["n"]
    print(f"\nsearch_operations from the prompt alone: top1 {totals['top1']}/{n}, top3 {totals['top3']}/{n}, top5 {totals['top5']}/{n}")
    if misses:
        print("outside the top 3:", ", ".join(misses))


# ---------------------------------------------------------------------- model
def _matches(entry: dict, task: dict) -> bool:
    if entry["cloud"] != task["cloud"]:
        return False
    if entry.get("service") != task["service"]:
        return False
    return entry.get("operation", "").lower() in {op.lower() for op in task["any"]}


def _args_ok(entry: dict, task: dict) -> bool:
    blob = json.dumps(entry.get("params") or {}).lower()
    return all(str(v).lower() in blob for v in task["args"].values())


async def run_arm(arm: str, tasks: list[dict], model: str, concurrency: int) -> dict:
    import httpx

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("model mode needs ANTHROPIC_API_KEY. static, oracle and search run without it.")
    semaphore = asyncio.Semaphore(concurrency)

    async def one(task: dict) -> dict:
        # Fresh gateways per task: writes are recorded, never sent.
        pair = (gateway_module.Gateway(allow_write=False), gateway_module.Gateway(allow_write=True, dry_run_writes=True))
        original = gateway_module.make_pair
        gateway_module.make_pair = lambda: pair
        try:
            server = FastMCP("eval")
            toolsets.register_selected(server, arm_selection(arm))
        finally:
            gateway_module.make_pair = original
        defs = [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema} for t in await server.list_tools()]
        messages = [{"role": "user", "content": task["prompt"]}]
        usage = {"input": 0, "output": 0, "turns": 0}
        error = None
        async with semaphore, httpx.AsyncClient(timeout=120) as client:
            for _ in range(MAX_TURNS):
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": model, "max_tokens": 2048, "temperature": 0, "system": SYSTEM, "tools": defs, "messages": messages},
                )
                if response.status_code != 200:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    break
                data = response.json()
                usage["input"] += data["usage"]["input_tokens"]
                usage["output"] += data["usage"]["output_tokens"]
                usage["turns"] += 1
                messages.append({"role": "assistant", "content": data["content"]})
                calls = [b for b in data["content"] if b["type"] == "tool_use"]
                if not calls:
                    break
                results = []
                for call in calls:
                    try:
                        out = await server.call_tool(call["name"], call["input"])
                        text = out[0][0].text if isinstance(out, tuple) else str(out)
                    except Exception as exc:  # noqa: BLE001
                        text = json.dumps({"error": str(exc)[:300]})
                    results.append({"type": "tool_result", "tool_use_id": call["id"], "content": text[:8000]})
                messages.append({"role": "user", "content": results})
        log = pair[0].log + pair[1].log
        if task.get("chained"):
            reached = all(any(e["cloud"] == c and e.get("service") == sv and e.get("operation", "").lower() == o.lower()
                              for e in log) for c, sv, o in task["steps"])
            matched = [e for e in log if e["cloud"] == task["steps"][0][0]] if reached else []
        else:
            matched = [e for e in log if _matches(e, task)]
        # The sandbox logs through the same gateways, so code_read/code_write calls are in `log` too.
        return {
            "task": task["id"], "chained": bool(task.get("chained")), "correct": bool(matched),
            "args_ok": bool(matched) if task.get("chained") else any(_args_ok(e, task) for e in matched),
            "calls": len(log), **usage, "error": error,
            "log": [{k: v for k, v in e.items() if k != "params"} for e in log][:10],
        }

    started = time.time()
    results = await asyncio.gather(*(one(t) for t in tasks))
    ok = [r for r in results if not r["error"]]
    return {
        "tasks": len(tasks), "answered": len(ok), "correct": sum(r["correct"] for r in ok), "args_ok": sum(r["args_ok"] for r in ok),
        "single_correct": sum(r["correct"] for r in ok if not r["chained"]), "single": sum(1 for r in ok if not r["chained"]),
        "chained_correct": sum(r["correct"] for r in ok if r["chained"]), "chained": sum(1 for r in ok if r["chained"]),
        "avg_input_tokens": round(sum(r["input"] for r in ok) / max(len(ok), 1)),
        "avg_output_tokens": round(sum(r["output"] for r in ok) / max(len(ok), 1)),
        "avg_turns": round(sum(r["turns"] for r in ok) / max(len(ok), 1), 2),
        "seconds": round(time.time() - started, 1), "errors": [r for r in results if r["error"]], "results": results,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["static", "oracle", "search", "model"])
    parser.add_argument("--arms", default="generic,code")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--out")
    args = parser.parse_args()
    tasks = load_tasks()
    answerable = [t for t in tasks if not t.get("curated")]
    chained = [t for t in answerable if t.get("chained")]
    print(f"{len(answerable) - len(chained)} single-operation tasks, {len(chained)} chained, {len(tasks) - len(answerable)} curated-only\n")

    if args.mode == "static":
        await run_static()
        return 0
    if args.mode == "oracle":
        return run_oracle(tasks)
    if args.mode == "search":
        run_search(tasks)
        return 0
    report = {}
    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        report[arm] = await run_arm(arm, answerable, args.model, args.concurrency)
    rows = [[a, r["answered"], f"{r['single_correct']}/{r['single']}", f"{r['chained_correct']}/{r['chained']}", f"{r['args_ok']}/{r['answered']}", r["avg_turns"],
             r["avg_input_tokens"], r["avg_output_tokens"], r["seconds"], len(r["errors"])] for a, r in report.items()]
    print(curated.table(rows, ["arm", "answered", "single op", "chained", "args right", "turns", "in tok/task", "out tok/task", "secs", "errors"]))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump({"model": args.model, "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "report": report}, handle, indent=2)
        print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
