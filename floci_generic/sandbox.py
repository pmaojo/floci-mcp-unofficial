"""Runs agent-written Python against the gateway, in a child process.

The child is `python -I -S`: standard library only, no site-packages, an empty
environment. It cannot import boto3. The only way it reaches a cloud is `aws(...)`
and `rest(...)`, which send each call back to this process, where the Gateway
classifies it. So `code_read` stays read-only whatever the code does.

This is a guardrail, not an isolation boundary: the child can still open a socket
to localhost. What bounds the damage is that Floci is a local emulator with
throwaway credentials. Do not point this at a real cloud.
"""
import ast
import asyncio
import json
import sys
from typing import Callable

from floci_generic.errors import Blocked
from floci_generic.gateway import Gateway
from floci_generic.payload import cap

MAX_CALLS = 200
OUTPUT_LIMIT = 20_000

ALLOWED_IMPORTS = {
    "json", "re", "math", "datetime", "collections", "itertools", "statistics", "base64", "textwrap",
    "string", "functools", "decimal", "time", "uuid", "hashlib", "fnmatch", "operator", "typing",
}
FORBIDDEN_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals", "locals",
    "vars", "getattr", "setattr", "delattr", "memoryview", "exit", "quit", "help",
}

RUNNER = r'''
import sys, json, io
_out = sys.stdout
_in = sys.stdin
class CloudError(Exception):
    pass
def _rpc(payload):
    _out.write(json.dumps({"call": payload}) + "\n"); _out.flush()
    line = _in.readline()
    if not line:
        raise CloudError("host closed the channel")
    reply = json.loads(line)
    if "error" in reply:
        raise CloudError(reply["error"])
    return reply["result"]
def aws(service, operation, **params):
    return _rpc({"cloud": "aws", "service": service, "operation": operation, "params": params})
def rest(cloud, method, path, query=None, json=None, body=None, headers=None):
    return _rpc({"cloud": cloud, "request": {"method": method, "path": path, "query": query, "json": json, "body": body, "headers": headers}})
def call(cloud, service, operation, **params):
    return _rpc({"cloud": cloud, "service": service, "operation": operation, "params": params})
_buf = io.StringIO()
_code = json.loads(_in.readline())["code"]
_ns = {"aws": aws, "rest": rest, "call": call, "CloudError": CloudError, "__name__": "__main__"}
sys.stdout = _buf
_err = None
try:
    exec(compile(_code, "<code>", "exec"), _ns)
except BaseException as exc:
    _err = type(exc).__name__ + ": " + str(exc)
sys.stdout = _out
_out.write(json.dumps({"done": {"stdout": _buf.getvalue(), "result": _ns.get("result"), "error": _err}}, default=str) + "\n")
_out.flush()
'''


def validate(code: str) -> list[str]:
    """Problems that stop the code from running at all. Empty list means it may run."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"SyntaxError: {exc.msg} (line {exc.lineno})"]
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    problems.append(f"import {alias.name!r} is not allowed")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS or node.level:
                problems.append(f"import from {node.module!r} is not allowed")
        elif isinstance(node, ast.Name) and (node.id in FORBIDDEN_NAMES or (node.id.startswith("__") and node.id != "__name__")):
            problems.append(f"name {node.id!r} is not allowed")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            problems.append(f"attribute {node.attr!r} is not allowed")
    return sorted(set(problems))


async def run(code: str, gateway: Gateway, timeout: float = 30.0, max_calls: int = MAX_CALLS,
              on_call: Callable[[dict], None] | None = None) -> dict:
    problems = validate(code)
    if problems:
        return {"ok": False, "error": "Code refused before running: " + "; ".join(problems)}

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-I", "-S", "-c", RUNNER,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env={},
    )
    calls = 0
    blocked: list[str] = []

    async def conversation() -> dict:
        nonlocal calls
        proc.stdin.write((json.dumps({"code": code}) + "\n").encode())
        await proc.stdin.drain()
        while True:
            line = await proc.stdout.readline()
            if not line:
                raise RuntimeError("the code exited without finishing")
            message = json.loads(line)
            if "done" in message:
                return message["done"]
            payload = message["call"]
            calls += 1
            if on_call:
                on_call(payload)
            if calls > max_calls:
                reply = {"error": f"More than {max_calls} cloud calls in one run; split the work."}
            else:
                try:
                    result = await gateway.acall(**payload)
                    reply = {"result": result}
                except Blocked as exc:
                    blocked.append(str(exc))
                    reply = {"error": str(exc)}
                except TypeError as exc:
                    reply = {"error": f"Bad call arguments: {exc}"}
            proc.stdin.write((json.dumps(reply, default=str) + "\n").encode())
            await proc.stdin.drain()

    try:
        done = await asyncio.wait_for(conversation(), timeout)
    except asyncio.TimeoutError:
        return {"ok": False, "error": f"Timed out after {timeout:.0f}s", "calls": calls}
    except Exception as exc:  # noqa: BLE001
        stderr = (await proc.stderr.read()).decode(errors="replace")[-500:] if proc.returncode is not None else ""
        return {"ok": False, "error": f"{type(exc).__name__}: {exc} {stderr}".strip(), "calls": calls}
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()

    out = {"ok": done["error"] is None, "calls": calls}
    if done["error"]:
        out["error"] = done["error"]
    if done["stdout"]:
        out["stdout"] = done["stdout"][:OUTPUT_LIMIT] + ("…[truncated]" if len(done["stdout"]) > OUTPUT_LIMIT else "")
    if done["result"] is not None:
        out["result"] = cap(done["result"])
    if blocked:
        out["blocked"] = blocked
    return out
