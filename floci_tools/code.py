"""Code tools: write Python, run it against every Floci runtime.

Two tools. code_read can only read; code_write can change things. Both run the
snippet in a child process whose only way out is aws(), rest() and call(), and every
call is classified by the gateway, so the read-only tool cannot write whatever the
code says. Use it when a task chains calls or needs to filter a large result before
it reaches you.
"""
from floci_generic import gateway
from floci_generic.sandbox import run

DOC = """
Runs Python 3 (standard library only) with three helpers:
  aws(service, operation, **params)   e.g. aws("s3", "ListBuckets"), aws("sqs", "GetQueueUrl", QueueName="orders")
  call(cloud, service, operation, **params)   catalogued Azure, GCP and OCI routes
  rest(cloud, method, path, query=None, json=None, body=None, headers=None)   any route of azure, gcp or oci
Each returns the decoded response (errors come back as {"error": ...}; CloudError is raised when a call is refused).
Print what you need or set `result`; keep output small by filtering in code. Parameter names are the
service model's (PascalCase for AWS). Imports are limited to json, re, math, datetime, collections,
itertools, statistics, base64, textwrap, string, functools, decimal, time, uuid, hashlib.
"""


def register(mcp):
    reader, writer = gateway.make_pair()

    @mcp.tool(description="Reads from AWS, Azure, GCP and OCI by running Python. Refuses any call that changes state." + DOC)
    async def code_read(code: str, timeout_seconds: int = 30) -> dict:
        return await run(code, reader, timeout=max(1, min(timeout_seconds, 120)))

    @mcp.tool(description="Reads and changes AWS, Azure, GCP and OCI by running Python. Ask the user before anything destructive." + DOC)
    async def code_write(code: str, timeout_seconds: int = 30) -> dict:
        return await run(code, writer, timeout=max(1, min(timeout_seconds, 120)))
