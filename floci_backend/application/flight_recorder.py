"""Flight Recorder — time-travel debugging for asynchronous events (Area 3).

Lets you "intercept" an in-flight event by holding it in a buffer, inspect and
modify its JSON payload on the fly, and resume its journey (replay) to the real
target (SQS, SNS, EventBridge or Lambda). Held events live in an in-memory buffer
in the backend process.
"""
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from floci_backend.infrastructure.boto_factory import make_client

VALID_TARGETS = {"sqs", "sns", "eventbridge", "lambda"}


class FlightRecorder:
    def __init__(self, capacity: int = 200):
        self._events: Dict[str, Dict[str, Any]] = {}
        self._capacity = capacity

    def _prune(self) -> None:
        if len(self._events) <= self._capacity:
            return
        # Drop the oldest already-replayed/discarded events first
        ordered = sorted(self._events.values(), key=lambda e: e["capturedAt"])
        for ev in ordered:
            if len(self._events) <= self._capacity:
                break
            if ev["status"] != "held":
                self._events.pop(ev["id"], None)

    def capture(
        self,
        target_type: str,
        target: str,
        payload: Any,
        source: Optional[str] = None,
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        if target_type not in VALID_TARGETS:
            raise ValueError(f"target_type must be one of {sorted(VALID_TARGETS)}")
        event = {
            "id": str(uuid.uuid4()),
            "status": "held",
            "targetType": target_type,
            "target": target,
            "source": source,
            "label": label or f"{target_type}:{target}",
            "payload": payload,
            "capturedAt": time.time(),
            "replayedAt": None,
            "result": None,
        }
        self._events[event["id"]] = event
        self._prune()
        return event

    def list_events(self) -> Dict[str, Any]:
        events = sorted(self._events.values(), key=lambda e: e["capturedAt"], reverse=True)
        return {"events": events, "count": len(events)}

    def get(self, event_id: str) -> Dict[str, Any]:
        if event_id not in self._events:
            raise KeyError(event_id)
        return self._events[event_id]

    def update_payload(self, event_id: str, payload: Any) -> Dict[str, Any]:
        event = self.get(event_id)
        if event["status"] != "held":
            raise ValueError("Only held events can be edited")
        event["payload"] = payload
        return event

    def discard(self, event_id: str) -> Dict[str, Any]:
        event = self.get(event_id)
        event["status"] = "discarded"
        return event

    def replay(self, event_id: str) -> Dict[str, Any]:
        event = self.get(event_id)
        payload = event["payload"]
        body = payload if isinstance(payload, str) else json.dumps(payload)
        target_type = event["targetType"]
        target = event["target"]

        if target_type == "sqs":
            client = make_client("sqs")
            result = client.send_message(QueueUrl=target, MessageBody=body)
            out = {"messageId": result.get("MessageId")}
        elif target_type == "sns":
            client = make_client("sns")
            result = client.publish(TopicArn=target, Message=body)
            out = {"messageId": result.get("MessageId")}
        elif target_type == "lambda":
            client = make_client("lambda")
            result = client.invoke(FunctionName=target, Payload=body.encode())
            out = {
                "statusCode": result.get("StatusCode"),
                "functionError": result.get("FunctionError"),
                "response": result["Payload"].read().decode("utf-8", "replace"),
            }
        else:  # eventbridge
            client = make_client("events")
            detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
            entry = {
                "Source": (payload.get("source") if isinstance(payload, dict) else None) or event.get("source") or "floci.flight-recorder",
                "DetailType": (payload.get("detail-type") if isinstance(payload, dict) else None) or "FlociReplay",
                "Detail": detail if isinstance(detail, str) else json.dumps(detail),
                "EventBusName": target or "default",
            }
            result = client.put_events(Entries=[entry])
            out = {"failedEntryCount": result.get("FailedEntryCount")}

        event["status"] = "replayed"
        event["replayedAt"] = time.time()
        event["result"] = out
        return event
