"""Gestión visual de Dead Letter Queues (Área 3 — Observabilidad).

Descubre las DLQ activas (colas referenciadas por la RedrivePolicy de otras
colas), permite inspeccionar mensajes fallidos sin consumirlos y reinyectarlos
(redrive) en la cola de origen tras arreglar el código.
"""
import json
from typing import Any, Dict, List, Optional

from floci_backend.infrastructure.boto_factory import make_client


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
    def __init__(self):
        self._sqs = make_client("sqs")

    def _queue_arn(self, queue_url: str) -> Optional[str]:
        attrs = self._sqs.get_queue_attributes(
            QueueUrl=queue_url, AttributeNames=["QueueArn"]
        ).get("Attributes", {})
        return attrs.get("QueueArn")

    def _url_from_arn(self, arn: str) -> Optional[str]:
        # arn:aws:sqs:region:account:name -> resolve url by name
        name = arn.split(":")[-1]
        try:
            return self._sqs.get_queue_url(QueueName=name).get("QueueUrl")
        except Exception:
            return None

    def list_dead_letter_queues(self) -> Dict[str, Any]:
        """Lista las colas usadas como DLQ y qué cola(s) de origen las alimentan."""
        urls = self._sqs.list_queues().get("QueueUrls", [])

        # Mapa DLQ ARN -> [colas de origen]
        sources_by_dlq: Dict[str, List[str]] = {}
        arn_to_url: Dict[str, str] = {}

        for url in urls:
            attrs = self._sqs.get_queue_attributes(
                QueueUrl=url, AttributeNames=["QueueArn", "RedrivePolicy"]
            ).get("Attributes", {})
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
                c = self._sqs.get_queue_attributes(
                    QueueUrl=dlq_url,
                    AttributeNames=["ApproximateNumberOfMessages"],
                ).get("Attributes", {})
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
        """Lee mensajes de la DLQ sin eliminarlos (visibility_timeout=0)."""
        resp = self._sqs.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=min(max_messages, 10),
            VisibilityTimeout=0,
            WaitTimeSeconds=1,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )
        messages = _to_jsonable(resp.get("Messages", []))
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
        """Reinyecta mensajes desde la DLQ a la cola de origen (redrive manual).

        Compatible con LocalStack: recibe, reenvía a la cola de origen y elimina
        de la DLQ solo tras un reenvío correcto.
        """
        moved = 0
        errors: List[str] = []
        remaining = max_messages
        while remaining > 0:
            batch = self._sqs.receive_message(
                QueueUrl=dlq_url,
                MaxNumberOfMessages=min(remaining, 10),
                VisibilityTimeout=30,
                WaitTimeSeconds=1,
                MessageAttributeNames=["All"],
            ).get("Messages", [])
            if not batch:
                break
            for msg in batch:
                try:
                    self._sqs.send_message(
                        QueueUrl=source_url,
                        MessageBody=msg["Body"],
                        MessageAttributes=msg.get("MessageAttributes", {}),
                    )
                    self._sqs.delete_message(
                        QueueUrl=dlq_url, ReceiptHandle=msg["ReceiptHandle"]
                    )
                    moved += 1
                except Exception as e:  # noqa: BLE001
                    errors.append(str(e))
            remaining -= len(batch)

        return {"redriven": moved, "target": source_url, "errors": errors}
