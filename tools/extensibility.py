"""Extensibilidad: lifecycle webhooks, interceptores HTTP y plugins (Área 6)."""
from tools._client import backend


def register(mcp):

    # ----------------------------------------------------------- webhooks
    @mcp.tool()
    async def list_lifecycle_webhooks() -> dict:
        """Lista los webhooks de ciclo de vida registrados."""
        return await backend("GET", "/api/extensibility/webhooks")

    @mcp.tool()
    async def register_lifecycle_webhook(event: str, url: str, description: str = "") -> dict:
        """
        Registra un webhook que recibe eventos de ciclo de vida del emulador.

        event: patrón glob, ej. 'floci.resource.created' o '*' para todos.
        url: endpoint que recibirá un POST con {event, payload, timestamp}.
        """
        return await backend("POST", "/api/extensibility/webhooks", json_data={
            "event": event, "url": url, "description": description,
        })

    @mcp.tool()
    async def delete_lifecycle_webhook(webhook_id: str) -> dict:
        """Elimina un webhook de ciclo de vida por su id."""
        return await backend("DELETE", f"/api/extensibility/webhooks/{webhook_id}")

    @mcp.tool()
    async def emit_lifecycle_event(event: str, payload: dict | None = None) -> dict:
        """
        Dispara manualmente un evento de ciclo de vida hacia los webhooks que casen.

        Útil para probar integraciones o notificar a otros agentes de IA.
        """
        return await backend("POST", "/api/extensibility/webhooks/emit", json_data={
            "event": event, "payload": payload,
        })

    # ------------------------------------------------------- interceptors
    @mcp.tool()
    async def list_http_interceptors() -> dict:
        """Lista las reglas de interceptación HTTP del proxy de Floci."""
        return await backend("GET", "/api/extensibility/interceptors")

    @mcp.tool()
    async def register_http_interceptor(
        url_pattern: str,
        phase: str = "request",
        action: str = "set_header",
        params: dict | None = None,
    ) -> dict:
        """
        Registra una regla declarativa que modifica el tráfico del proxy de Floci.

        phase: 'request' o 'response'.
        action: 'set_header' (params: {clave: valor}), 'set_status' (params: {status: 503})
                o 'delay_ms' (params: {ms: 3000}).
        url_pattern: substring o patrón glob para casar la URL.
        """
        return await backend("POST", "/api/extensibility/interceptors", json_data={
            "url_pattern": url_pattern, "phase": phase, "action": action, "params": params,
        })

    @mcp.tool()
    async def delete_http_interceptor(interceptor_id: str) -> dict:
        """Elimina una regla de interceptación HTTP por su id."""
        return await backend("DELETE", f"/api/extensibility/interceptors/{interceptor_id}")

    # ------------------------------------------------------------ plugins
    @mcp.tool()
    async def list_floci_plugins() -> dict:
        """
        Lista los plugins de comunidad descubiertos en mcp/plugins/.

        Cada plugin aporta tools MCP adicionales cargadas en el arranque del servidor.
        """
        return await backend("GET", "/api/extensibility/plugins")
