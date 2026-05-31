"""Observability: DLQ, flight recorder (time-travel) and service graph (Area 3)."""
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def list_dead_letter_queues() -> dict:
        """
        List the active Dead Letter Queues in the emulator.

        Detects queues referenced by another queue's RedrivePolicy and includes the
        number of failed messages and the source queues.
        """
        return await backend("GET", "/api/observability/dlq")

    @mcp.tool()
    async def inspect_dlq_messages(dlq_url: str, max_messages: int = 10) -> dict:
        """
        Inspect messages in a DLQ without consuming them (visibility_timeout=0).

        Returns the body, attributes and failure reason (receive count, source queue).
        """
        return await backend("GET", f"/api/observability/dlq/messages?dlq_url={dlq_url}&max_messages={max_messages}")

    @mcp.tool()
    async def redrive_dlq(dlq_url: str, source_url: str, max_messages: int = 10) -> dict:
        """
        Redrive messages from a DLQ back to their source queue.

        Use after fixing the code that caused the failures. Only deletes from the
        DLQ the messages that were successfully re-sent.
        """
        return await backend("POST", "/api/observability/dlq/redrive", json_data={
            "dlq_url": dlq_url, "source_url": source_url, "max_messages": max_messages,
        })

    @mcp.tool()
    async def get_service_graph() -> dict:
        """
        Return the X-Ray-style service graph (nodes + edges) with the real
        relationships: SNS→SQS, Lambda event source mappings, EventBridge
        rule→targets, SQS→DLQ redrive and S3→Lambda notifications.
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
        Hold an event in the flight recorder for inspection/editing and replay.

        target_type: 'sqs', 'sns', 'eventbridge' or 'lambda'.
        target: queue URL, topic ARN, event bus name or function name.
        The event stays in 'held' state until you call replay_captured_event.
        """
        return await backend("POST", "/api/observability/flight-recorder", json_data={
            "target_type": target_type, "target": target,
            "payload": payload, "source": source, "label": label,
        })

    @mcp.tool()
    async def list_captured_events() -> dict:
        """List the flight recorder events (held, replayed or discarded)."""
        return await backend("GET", "/api/observability/flight-recorder")

    @mcp.tool()
    async def edit_captured_event(event_id: str, payload: dict | str) -> dict:
        """Modify a held event's JSON payload on the fly before resuming it."""
        return await backend("PUT", f"/api/observability/flight-recorder/{event_id}", json_data={"payload": payload})

    @mcp.tool()
    async def replay_captured_event(event_id: str) -> dict:
        """Resume a held event's journey, dispatching it to its real target."""
        return await backend("POST", f"/api/observability/flight-recorder/{event_id}/replay")
