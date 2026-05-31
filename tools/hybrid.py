"""Hybrid development: cloud proxying, cloud seeding and reverse tunnels (Area 5)."""
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def seed_from_cloud_dynamodb(
        source_table: str,
        target_table: str | None = None,
        limit: int = 25,
        anonymize_fields: list[str] | None = None,
        region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> dict:
        """
        Extract a subset of a REAL DynamoDB table, anonymize it and inject it into
        the local emulator table.

        Requires real AWS credentials (parameters or the backend environment).
        If anonymize_fields is None, sensitive fields are anonymized automatically
        (email, name, phone, address); pass it to limit to specific fields.
        """
        return await backend("POST", "/api/hybrid/seed-from-cloud", json_data={
            "source_table": source_table, "target_table": target_table,
            "limit": limit, "anonymize_fields": anonymize_fields,
            "region": region, "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
        })

    @mcp.tool()
    async def proxy_cloud_sqs_to_local(
        source_queue_url: str,
        target_type: str,
        target: str,
        max_messages: int = 10,
        delete_after: bool = True,
        region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> dict:
        """
        Drain messages from a REAL SQS queue (e.g. staging) and forward them to a
        local resource (Lambda/SQS/SNS) for an immediate feedback loop.

        target_type: 'lambda', 'sqs' or 'sns'. One-shot drain of up to max_messages.
        """
        return await backend("POST", "/api/hybrid/cloud-proxy/sqs", json_data={
            "source_queue_url": source_queue_url, "target_type": target_type,
            "target": target, "max_messages": max_messages, "delete_after": delete_after,
            "region": region, "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
        })

    @mcp.tool()
    async def start_reverse_tunnel(port: int = 4566) -> dict:
        """
        Expose a local port to the internet with a temporary URL (ngrok-style).

        Useful to test third-party webhooks (Stripe, GitHub) against a local API
        Gateway. Requires 'cloudflared' or 'ngrok' installed on the host.
        """
        return await backend("POST", "/api/hybrid/tunnels", json_data={"port": port})

    @mcp.tool()
    async def list_reverse_tunnels() -> dict:
        """List the active reverse tunnels started by Floci."""
        return await backend("GET", "/api/hybrid/tunnels")

    @mcp.tool()
    async def stop_reverse_tunnel(pid: str) -> dict:
        """Stop a reverse tunnel by its PID."""
        return await backend("DELETE", f"/api/hybrid/tunnels/{pid}")
