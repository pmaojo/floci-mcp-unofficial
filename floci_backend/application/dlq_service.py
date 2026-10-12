"""Visual Dead Letter Queue management (Area 3 — Observability).

Discovers active DLQs (queues referenced by another queue's RedrivePolicy), lets
you inspect failed messages without consuming them, and redrive them back to the
source queue once the code is fixed.
"""
import json
from typing import Any, Dict, List, Optional

from floci_backend.application.ports import QueueTransport


def _to_jsonable(obj: Any) -> Any:
    import base64
    from datetime import date, datetime
    from decimal import Decimal
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(i) for i in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode()
    return obj


class DlqService:
    def __init__(self, queues: QueueTransport):
        self._queues = queues

    def _queue_arn(self, queue_url: str) -> Optional[str]:
        return self._queues.queue_attributes(queue_url, ["QueueArn"]).get("QueueArn")

    def _url_from_arn(self, arn: str) -> Optional[str]:
        # arn:aws:sqs:region:account:name -> resolve url by name
        name = arn.split(":")[-1]
        try:
            return self._queues.queue_url(name)
        except Exception:
            return None

    def list_dead_letter_queues(self) -> Dict[str, Any]:
        """List queues used as a DLQ and which source queue(s) feed them."""
        urls = self._queues.list_queue_urls()

        # Map DLQ ARN -> [source queues]
        sources_by_dlq: Dict[str, List[str]] = {}
        arn_to_url: Dict[str, str] = {}

        for url in urls:
            attrs = self._queues.queue_attributes(url, ["QueueArn", "RedrivePolicy"])
            arn = attrs.get("QueueArn")
            if arn:
                arn_to_url[arn] = url
            policy_raw = attrs.get("RedrivePolicy")
            if policy_raw:
                try:
                    policy = json.loads(policy_raw)
                    dlq_arn = policy.get("deadLetterTargetArn")
                    if dlq_arn:
                        sources_by_dlq.setdefault(dlq_arn, []).append(url)
                except (json.JSONDecodeError, TypeError):
                    pass

        dlqs = []
        for dlq_arn, source_urls in sources_by_dlq.items():
            dlq_url = arn_to_url.get(dlq_arn) or self._url_from_arn(dlq_arn)
            count = 0
            if dlq_url:
                c = self._queues.queue_attributes(dlq_url, ["ApproximateNumberOfMessages"])
                count = int(c.get("ApproximateNumberOfMessages", 0))
            dlqs.append({
                "dlqArn": dlq_arn,
                "dlqUrl": dlq_url,
                "name": dlq_arn.split(":")[-1],
                "messageCount": count,
                "sources": [{"url": u, "name": u.split("/")[-1]} for u in source_urls],
            })

        return {"deadLetterQueues": dlqs, "count": len(dlqs)}

    def inspect_messages(self, dlq_url: str, max_messages: int = 10) -> Dict[str, Any]:
        """Read messages from the DLQ without deleting them (visibility_timeout=0)."""
        received = self._queues.receive(
            dlq_url,
            max_messages=min(max_messages, 10),
            visibility_timeout=0,
            wait_seconds=1,
            all_attributes=True,
        )
        messages = _to_jsonable(received)
        for m in messages:
            attrs = m.get("Attributes", {})
            m["failureReason"] = {
                "approximateReceiveCount": attrs.get("ApproximateReceiveCount"),
                "deadLetterSourceQueue": attrs.get("DeadLetterQueueSourceArn"),
                "sentTimestamp": attrs.get("SentTimestamp"),
            }
        return {"count": len(messages), "messages": messages}

    def redrive(
        self, dlq_url: str, source_url: str, max_messages: int = 10
    ) -> Dict[str, Any]:
        """Redrive messages from the DLQ back to the source queue (manual redrive).

        LocalStack-compatible: receive, re-send to the source queue, and only
        delete from the DLQ after a successful re-send.
        """
        moved = 0
        errors: List[str] = []
        remaining = max_messages
        while remaining > 0:
            batch = self._queues.receive(
                dlq_url,
                max_messages=min(remaining, 10),
                visibility_timeout=30,
                wait_seconds=1,
            )
            if not batch:
                break
            for msg in batch:
                try:
                    self._queues.send(source_url, msg["Body"], msg.get("MessageAttributes", {}))
                    self._queues.delete(dlq_url, msg["ReceiptHandle"])
                    moved += 1
                except Exception as e:  # noqa: BLE001
                    errors.append(str(e))
            remaining -= len(batch)

        return {"redriven": moved, "target": source_url, "errors": errors}
