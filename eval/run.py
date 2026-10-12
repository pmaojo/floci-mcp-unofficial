"""Tool selection eval for the Floci MCP server.

Anthropic's guidance on tools is to evaluate them with realistic tasks and to
measure accuracy and token cost, not to guess. This runs the same task list
against different toolset configurations.

    uv run python eval/run.py static                     # tokens per configuration
    uv run python eval/run.py retrieval                  # can BM25 find the tool? (offline)
    uv run python eval/run.py model                      # needs ANTHROPIC_API_KEY

    --configs default,all,core+storage                   # "+" joins toolsets; default is the server default
    --tasks eval/tasks.json  --limit 10  --model <id>  --out eval/results/run.json

The model mode sends only the tool definitions and the task, reads the first
tool call and does not execute anything.
"""
import argparse
import asyncio
import json
import math
import os
import re
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mcp.server.fastmcp import FastMCP  # noqa: E402

import toolsets  # noqa: E402

DEFAULT_MODEL = os.environ.get("FLOCI_EVAL_MODEL", "claude-sonnet-5-5")
SYSTEM = (
    "You operate local cloud emulators (AWS, Azure, GCP, OCI) through tools. "
    "Answer the user's request by calling the single most appropriate tool."
)


def resolve(config: str) -> tuple[str, ...]:
    if config == "default":
        return toolsets.DEFAULT_TOOLSETS
    return toolsets.parse_selection(config.replace("+", ","))


async def definitions(selection: tuple[str, ...]) -> list[dict]:
    server = FastMCP("eval")
    toolsets.register_selected(server, selection)
    out = []
    for tool in await server.list_tools():
        out.append({"name": tool.name, "description": tool.description or "", "input_schema": tool.inputSchema})
    return out


def tokens_of(defs: list[dict]) -> int:
    """Rough size of what a client sends: one token is about four characters."""
    return sum(len(json.dumps(d)) for d in defs) // 4


def load_tasks(path: str, limit: int | None) -> list[dict]:
    with open(path) as handle:
        tasks = json.load(handle)
    return tasks[:limit] if limit else tasks


# ------------------------------------------------------------------ retrieval
def tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


class BM25:
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
        result = []
        for doc, tf in zip(self.docs, self.tf):
            score = 0.0
            for term in query:
                if term not in tf:
                    continue
                freq = tf[term]
                norm = freq + self.k1 * (1 - self.b + self.b * len(doc) / self.avg)
                score += self.idf[term] * freq * (self.k1 + 1) / norm
            result.append(score)
        return result


def tool_document(defn: dict) -> list[str]:
    params = " ".join((defn["input_schema"].get("properties") or {}).keys())
    # The name counts triple: it is the part written to be matched.
    return tokenize(f"{defn['name']} {defn['name']} {defn['name']} {defn['description']} {params}")


async def run_retrieval(configs: list[str], tasks: list[dict]) -> dict:
    report = {}
    for config in configs:
        defs = await definitions(resolve(config))
        names = [d["name"] for d in defs]
        index = BM25([tool_document(d) for d in defs])
        covered = hit1 = hit3 = hit5 = 0
        rr = 0.0
        misses = []
        for task in tasks:
            expected = task["tool"] if isinstance(task["tool"], list) else [task["tool"]]
            if not any(e in names for e in expected):
                continue
            covered += 1
            scores = index.scores(tokenize(task["prompt"]))
            ranked = [names[i] for i in sorted(range(len(names)), key=lambda i: -scores[i])]
            rank = min(ranked.index(e) + 1 for e in expected if e in ranked)
            hit1 += rank == 1
            hit3 += rank <= 3
            hit5 += rank <= 5
            rr += 1 / rank
            if rank > 3:
                misses.append({"task": task["id"], "expected": expected[0], "rank": rank, "top": ranked[:3]})
        report[config] = {
            "tools": len(defs), "tokens": tokens_of(defs), "tasks": len(tasks), "covered": covered,
            "top1": hit1, "top3": hit3, "top5": hit5, "mrr": round(rr / covered, 3) if covered else 0,
            "misses": misses,
        }
    return report


# ---------------------------------------------------------------------- model
async def run_model(configs: list[str], tasks: list[dict], model: str, concurrency: int) -> dict:
    import httpx

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("model mode needs ANTHROPIC_API_KEY. The static and retrieval modes run without it.")
    semaphore = asyncio.Semaphore(concurrency)
    report = {}
    async with httpx.AsyncClient(timeout=120) as client:

        async def ask(defs, task):
            body = {
                "model": model, "max_tokens": 512, "temperature": 0, "system": SYSTEM,
                "tools": defs, "tool_choice": {"type": "any"},
                "messages": [{"role": "user", "content": task["prompt"]}],
            }
            async with semaphore:
                started = time.time()
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json=body,
                )
                seconds = time.time() - started
            if response.status_code != 200:
                return {"task": task["id"], "error": f"HTTP {response.status_code}: {response.text[:200]}"}
            data = response.json()
            call = next((b for b in data.get("content", []) if b.get("type") == "tool_use"), None)
            return {
                "task": task["id"], "called": call["name"] if call else None,
                "input": call["input"] if call else None,
                "input_tokens": data.get("usage", {}).get("input_tokens"), "seconds": round(seconds, 2),
            }

        for config in configs:
            defs = await definitions(resolve(config))
            names = {d["name"] for d in defs}
            results = await asyncio.gather(*(ask(defs, t) for t in tasks))
            correct = answerable = args_ok = 0
            for task, result in zip(tasks, results):
                expected = task["tool"] if isinstance(task["tool"], list) else [task["tool"]]
                result["answerable"] = any(e in names for e in expected)
                answerable += result["answerable"]
                result["correct"] = result.get("called") in expected
                correct += result["correct"] and result["answerable"]
                wanted = task.get("args") or {}
                got = result.get("input") or {}
                result["args_ok"] = result["correct"] and all(str(v).lower() in json.dumps(got.get(k, "")).lower() for k, v in wanted.items())
                args_ok += result["args_ok"] and result["answerable"]
            ok = [r for r in results if "error" not in r]
            report[config] = {
                "tools": len(defs), "tokens": tokens_of(defs), "tasks": len(tasks), "answerable": answerable,
                "correct_tool": correct, "correct_args": args_ok,
                "avg_input_tokens": round(sum(r["input_tokens"] or 0 for r in ok) / max(len(ok), 1)),
                "avg_seconds": round(sum(r["seconds"] for r in ok) / max(len(ok), 1), 2),
                "errors": [r for r in results if "error" in r], "results": results,
            }
    return report


# ---------------------------------------------------------------------- views
def table(rows: list[list], header: list[str]) -> str:
    widths = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    line = lambda r: "  ".join(str(c).ljust(w) for c, w in zip(r, widths))  # noqa: E731
    return "\n".join([line(header), line(["-" * w for w in widths])] + [line(r) for r in rows])


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["static", "retrieval", "model"])
    parser.add_argument("--configs", default="default,all,core,core+storage,core+messaging")
    parser.add_argument("--tasks", default=os.path.join(ROOT, "eval", "tasks.json"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--out")
    args = parser.parse_args()
    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    tasks = load_tasks(args.tasks, args.limit)

    if args.mode == "static":
        report = {}
        rows = []
        for config in configs:
            defs = await definitions(resolve(config))
            report[config] = {"tools": len(defs), "tokens": tokens_of(defs)}
            rows.append([config, len(defs), tokens_of(defs)])
        print(table(rows, ["config", "tools", "~tokens"]))
    elif args.mode == "retrieval":
        report = await run_retrieval(configs, tasks)
        rows = [[c, r["tools"], r["tokens"], f"{r['covered']}/{r['tasks']}", f"{r['top1']}/{r['covered']}",
                 f"{r['top3']}/{r['covered']}", f"{r['top5']}/{r['covered']}", r["mrr"]] for c, r in report.items()]
        print(table(rows, ["config", "tools", "~tokens", "answerable", "top1", "top3", "top5", "mrr"]))
        for config, r in report.items():
            if r["misses"]:
                print(f"\n[{config}] tasks where the tool is not in the top 3:")
                for miss in r["misses"]:
                    print(f"  {miss['task']}: want {miss['expected']} (rank {miss['rank']}), got {miss['top']}")
    else:
        report = await run_model(configs, tasks, args.model, args.concurrency)
        rows = [[c, r["tools"], r["avg_input_tokens"], f"{r['answerable']}/{r['tasks']}",
                 f"{r['correct_tool']}/{r['answerable']}", f"{r['correct_args']}/{r['answerable']}",
                 r["avg_seconds"], len(r["errors"])] for c, r in report.items()]
        print(table(rows, ["config", "tools", "input_tokens", "answerable", "right tool", "right args", "secs", "errors"]))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump({"mode": args.mode, "configs": configs, "model": args.model if args.mode == "model" else None,
                       "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "report": report}, handle, indent=2)
        print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
