"""IaC bidireccional: auto-descubrimiento y detección de drift (Área 4)."""
from urllib.parse import quote

from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def discover_iac_resources(path: str = ".") -> dict:
        """
        Auto-descubre recursos declarados en IaC local bajo `path`.

        Lee terraform.tfstate (recursivo) y JSON exportado de Serverless/CDK
        (floci-resources.json) y devuelve los recursos agrupados por categoría.
        """
        return await backend("GET", f"/api/iac/discover?path={quote(path)}")

    @mcp.tool()
    async def detect_iac_drift(path: str = ".") -> dict:
        """
        Compara la IaC local con el estado real del emulador y reporta drift.

        Devuelve:
          - missing:   declarado en código pero ausente en el emulador.
          - unmanaged: existe en el emulador pero no en el código (creado a mano).
          - managed:   en sincronía en ambos lados.
        """
        return await backend("GET", f"/api/iac/drift?path={quote(path)}")
