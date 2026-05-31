"""Observabilidad: DLQ, flight recorder (time-travel) y grafo de servicios (Área 3)."""
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def list_dead_letter_queues() -> dict:
        """
        Lista las Dead Letter Queues activas del emulador.

        Detecta las colas referenciadas por la RedrivePolicy de otras colas e
        incluye el número de mensajes fallidos y las colas de origen.
        """
        return await backend("GET", "/api/observability/dlq")

    @mcp.tool()
    async def inspect_dlq_messages(dlq_url: str, max_messages: int = 10) -> dict:
        """
        Inspecciona mensajes de una DLQ sin consumirlos (visibility_timeout=0).

        Devuelve el cuerpo, atributos y el motivo del fallo (receive count, cola origen).
        """
        return await backend("GET", f"/api/observability/dlq/messages?dlq_url={dlq_url}&max_messages={max_messages}")

    @mcp.tool()
    async def redrive_dlq(dlq_url: str, source_url: str, max_messages: int = 10) -> dict:
        """
        Reinyecta (redrive) mensajes desde una DLQ hacia su cola de origen.

        Úsalo tras arreglar el código que provocaba los fallos. Solo elimina de la
        DLQ los mensajes reenviados correctamente.
        """
        return await backend("POST", "/api/observability/dlq/redrive", json_data={
            "dlq_url": dlq_url, "source_url": source_url, "max_messages": max_messages,
        })

    @mcp.tool()
    async def get_service_graph() -> dict:
        """
        Devuelve el grafo de servicios estilo X-Ray (nodos + aristas) con las
        relaciones reales: SNS→SQS, event source mappings de Lambda, reglas de
        EventBridge→targets, redrive SQS→DLQ y notificaciones S3→Lambda.
        """
        return await backend("GET", "/api/observability/service-graph")

    @mcp.tool()
    async def capture_event_for_replay(
        target_type: str,
        target: str,
        payload: dict | str,
        source: str | None = None,
        label: str | None = None,
    ) -> dict:
        """
        Retiene un evento en el flight recorder para inspección/edición y replay.

        target_type: 'sqs', 'sns', 'eventbridge' o 'lambda'.
        target: URL de la cola, ARN del topic, nombre del event bus o de la función.
        El evento queda en estado 'held' hasta que llames a replay_captured_event.
        """
        return await backend("POST", "/api/observability/flight-recorder", json_data={
            "target_type": target_type, "target": target,
            "payload": payload, "source": source, "label": label,
        })

    @mcp.tool()
    async def list_captured_events() -> dict:
        """Lista los eventos del flight recorder (retenidos, reproducidos o descartados)."""
        return await backend("GET", "/api/observability/flight-recorder")

    @mcp.tool()
    async def edit_captured_event(event_id: str, payload: dict | str) -> dict:
        """Modifica en caliente el payload JSON de un evento retenido antes de reanudarlo."""
        return await backend("PUT", f"/api/observability/flight-recorder/{event_id}", json_data={"payload": payload})

    @mcp.tool()
    async def replay_captured_event(event_id: str) -> dict:
        """Reanuda el viaje de un evento retenido, despachándolo a su destino real."""
        return await backend("POST", f"/api/observability/flight-recorder/{event_id}/replay")
