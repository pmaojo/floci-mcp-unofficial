"""Extensibility: lifecycle webhooks, HTTP interceptors and plugins (Area 6)."""
from tools._client import backend


def register(mcp):

    # ----------------------------------------------------------- webhooks
    @mcp.tool()
    async def list_lifecycle_webhooks() -> dict:
        """List the registered lifecycle webhooks."""
        return await backend("GET", "/api/extensibility/webhooks")

    @mcp.tool()
    async def register_lifecycle_webhook(event: str, url: str, description: str = "") -> dict:
        """
        Register a webhook that receives lifecycle events from the emulator.

        event: glob pattern, e.g. 'floci.resource.created' or '*' for all.
        url: endpoint that will receive a POST with {event, payload, timestamp}.
        """
        return await backend("POST", "/api/extensibility/webhooks", json_data={
            "event": event, "url": url, "description": description,
        })

    @mcp.tool()
    async def delete_lifecycle_webhook(webhook_id: str) -> dict:
        """Delete a lifecycle webhook by its id."""
        return await backend("DELETE", f"/api/extensibility/webhooks/{webhook_id}")

    @mcp.tool()
    async def emit_lifecycle_event(event: str, payload: dict | None = None) -> dict:
        """
        Manually fire a lifecycle event to all matching webhooks.

        Useful to test integrations or notify other AI agents.
        """
        return await backend("POST", "/api/extensibility/webhooks/emit", json_data={
            "event": event, "payload": payload,
        })

    # ------------------------------------------------------- interceptors
    @mcp.tool()
    async def list_http_interceptors() -> dict:
        """List the HTTP interception rules for Floci's proxy."""
        return await backend("GET", "/api/extensibility/interceptors")

    @mcp.tool()
    async def register_http_interceptor(
        url_pattern: str,
        phase: str = "request",
        action: str = "set_header",
        params: dict | None = None,
    ) -> dict:
        """
        Register a declarative rule that modifies traffic through Floci's proxy.

        phase: 'request' or 'response'.
        action: 'set_header' (params: {key: value}), 'set_status' (params: {status: 503})
                or 'delay_ms' (params: {ms: 3000}).
        url_pattern: substring or glob pattern to match the URL.
        """
        return await backend("POST", "/api/extensibility/interceptors", json_data={
            "url_pattern": url_pattern, "phase": phase, "action": action, "params": params,
        })

    @mcp.tool()
    async def delete_http_interceptor(interceptor_id: str) -> dict:
        """Delete an HTTP interception rule by its id."""
        return await backend("DELETE", f"/api/extensibility/interceptors/{interceptor_id}")

    # ------------------------------------------------------------ plugins
    @mcp.tool()
    async def list_floci_plugins() -> dict:
        """
        List the community plugins discovered in mcp/plugins/.

        Each plugin contributes additional MCP tools loaded at server startup.
        """
        return await backend("GET", "/api/extensibility/plugins")
