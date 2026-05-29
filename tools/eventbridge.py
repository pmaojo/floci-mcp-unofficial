"""Herramientas EventBridge: buses, reglas y envío de eventos."""
import json
from tools._client import clean, make_client


def register(mcp):

    @mcp.tool()
    async def list_eventbridge_buses() -> dict:
        """Lista todos los event buses de EventBridge, incluyendo el bus 'default'."""
        r = make_client("events").list_event_buses()
        return {"buses": clean([{"name": b["Name"], "arn": b["Arn"]} for b in r.get("EventBuses", [])])}

    @mcp.tool()
    async def put_eventbridge_events(entries: list) -> dict:
        """
        Envía eventos personalizados a un event bus de EventBridge.

        Útil para testear reglas y triggers sin necesidad de fuentes reales.
        Formato de cada entrada:
        {
          'Source': 'mi.aplicacion',
          'DetailType': 'OrderCreated',
          'Detail': '{"orderId": "123", "total": 99.90}',
          'EventBusName': 'default'
        }
        """
        r = make_client("events").put_events(Entries=entries)
        return clean({"failed_entry_count": r["FailedEntryCount"], "entries": r.get("Entries", [])})

    @mcp.tool()
    async def list_eventbridge_rules(bus_name: str = "default") -> dict:
        """Lista todas las reglas de un event bus de EventBridge."""
        r = make_client("events").list_rules(EventBusName=bus_name)
        return clean({"rules": r.get("Rules", [])})

    @mcp.tool()
    async def create_eventbridge_rule(
        name: str,
        schedule_expression: str | None = None,
        event_pattern: str | None = None,
        bus_name: str = "default",
        targets: list | None = None,
    ) -> dict:
        """
        Crea una regla de EventBridge con schedule o patrón de eventos, y targets opcionales.

        schedule_expression y event_pattern son mutuamente exclusivos. Usa uno de los dos.

        Ejemplos de schedule_expression: 'rate(5 minutes)', 'cron(0 12 * * ? *)'.
        Ejemplo de event_pattern: '{"source": ["mi.app"], "detail-type": ["OrderCreated"]}'.

        Formato de targets: [{'Id': 't1', 'Arn': 'arn:aws:lambda:...:function:mi-fn'}].
        """
        c = make_client("events")
        params: dict = {"Name": name, "EventBusName": bus_name, "State": "ENABLED"}
        if schedule_expression:
            params["ScheduleExpression"] = schedule_expression
        elif event_pattern:
            params["EventPattern"] = event_pattern if isinstance(event_pattern, str) else json.dumps(event_pattern)
        r = c.put_rule(**params)
        result: dict = {"rule_arn": r["RuleArn"]}
        if targets:
            c.put_targets(Rule=name, EventBusName=bus_name, Targets=targets)
            result["targets"] = targets
        return result

    @mcp.tool()
    async def delete_eventbridge_rule(name: str, bus_name: str = "default") -> dict:
        """
        Elimina una regla de EventBridge.

        Elimina automáticamente todos sus targets antes de borrar la regla.
        """
        c = make_client("events")
        try:
            targets = c.list_targets_by_rule(Rule=name, EventBusName=bus_name).get("Targets", [])
            if target_ids := [t["Id"] for t in targets]:
                c.remove_targets(Rule=name, EventBusName=bus_name, Ids=target_ids)
        except Exception:
            pass
        c.delete_rule(Name=name, EventBusName=bus_name)
        return {"deleted": name}
