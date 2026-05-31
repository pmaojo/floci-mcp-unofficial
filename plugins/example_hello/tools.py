"""Plugin de ejemplo del SDK de Floci.

Expone ``register(mcp)`` para que el servidor MCP cargue sus tools en arranque.
Copia este directorio como plantilla para tus propios adaptadores.
"""


def register(mcp):
    @mcp.tool()
    async def floci_hello(name: str = "world") -> dict:
        """Tool de ejemplo de un plugin de comunidad. Devuelve un saludo."""
        return {"message": f"Hello, {name}! — desde el plugin example_hello."}
