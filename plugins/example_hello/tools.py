"""Example plugin for the Floci SDK.

Exposes ``register(mcp)`` so the MCP server loads its tools at startup. Copy this
directory as a template for your own adapters.
"""


def register(mcp):
    @mcp.tool()
    async def floci_hello(name: str = "world") -> dict:
        """Example tool from a community plugin. Returns a greeting."""
        return {"message": f"Hello, {name}! — from the example_hello plugin."}
