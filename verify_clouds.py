"""Live check of the multi-cloud tools against running Floci-AZ, Floci-GCP and Floci-OCI.

    docker compose --profile multicloud up -d      # in floci-ui
    uv run python verify_clouds.py
"""
import asyncio
import json
import sys
import uuid

from mcp.server.fastmcp import FastMCP

from tools import clouds

SUFFIX = uuid.uuid4().hex[:8]


async def main() -> int:
    mcp = FastMCP("floci-mcp-check")
    clouds.register(mcp)
    failures: list[str] = []

    async def call(tool: str, **arguments):
        result = await mcp.call_tool(tool, arguments)
        if isinstance(result, tuple):
            return result[1]
        return json.loads(result[0].text)

    def check(label: str, condition: bool, detail=None):
        print(f"{'ok  ' if condition else 'FAIL'} {label}")
        if not condition:
            failures.append(f"{label}: {json.dumps(detail, default=str)[:300]}")

    status = await call("list_clouds")
    online = {item["cloud"]: item["status"] for item in status["clouds"]}
    print("runtimes:", online)

    if online.get("gcp") == "online":
        bucket, topic = f"mcp-check-{SUFFIX}", f"mcp-check-{SUFFIX}"
        await call("gcp_create_bucket", name=bucket)
        await call("gcp_create_topic", name=topic)
        check("gcp bucket listed", bucket in (await call("gcp_list_buckets"))["buckets"])
        check("gcp topic listed", any(t.endswith(f"/{topic}") for t in (await call("gcp_list_topics"))["topics"]))
        check("gcp objects list", "objects" in await call("gcp_list_objects", bucket=bucket))
        check("gcp secrets list", "secrets" in await call("gcp_list_secrets"))

    if online.get("azure") == "online":
        container, queue = f"mcpcheck{SUFFIX}", f"mcpcheck{SUFFIX}"
        await call("azure_create_container", name=container)
        await call("azure_create_queue", name=queue)
        check("azure container listed", container in (await call("azure_list_containers"))["containers"])
        check("azure blobs list", "blobs" in await call("azure_list_blobs", container=container))
        check("azure queue listed", queue in (await call("azure_list_queues"))["queues"])
        check("azure secrets list", "secrets" in await call("azure_list_secrets"))

    if online.get("oci") == "online":
        bucket = f"mcp-check-{SUFFIX}"
        await call("oci_create_bucket", name=bucket)
        check("oci bucket listed", bucket in (await call("oci_list_buckets"))["buckets"])
        check("oci objects list", "objects" in await call("oci_list_objects", bucket=bucket))

    if failures:
        print("\n".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
