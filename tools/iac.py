"""Bidirectional IaC: auto-discovery and drift detection (Area 4)."""
from urllib.parse import quote

from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def discover_iac_resources(path: str = ".") -> dict:
        """
        Auto-discover resources declared in local IaC under `path`.

        Reads terraform.tfstate (recursively) and JSON exported from Serverless/CDK
        (floci-resources.json) and returns the resources grouped by category.
        """
        return await backend("GET", f"/api/iac/discover?path={quote(path)}")

    @mcp.tool()
    async def detect_iac_drift(path: str = ".") -> dict:
        """
        Compare local IaC against the real emulator state and report drift.

        Returns:
          - missing:   declared in code but absent from the emulator.
          - unmanaged: exists in the emulator but not in code (created manually).
          - managed:   in sync on both sides.
        """
        return await backend("GET", f"/api/iac/drift?path={quote(path)}")
