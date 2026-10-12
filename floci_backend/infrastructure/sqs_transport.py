"""boto3 adapter for the QueueTransport port."""
from typing import Any, Dict, List, Optional

from floci_backend.infrastructure.boto_factory import make_client


class BotoQueueTransport:
    def __init__(self) -> None:
        self._client = None

    @property
    def _sqs(self):
        if self._client is None:
            self._client = make_client("sqs")
        return self._client

    def list_queue_urls(self) -> List[str]:
        return self._sqs.list_queues().get("QueueUrls", [])

    def queue_attributes(self, queue_url: str, names: List[str]) -> Dict[str, str]:
        return self._sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=names).get("Attributes", {})

    def queue_url(self, queue_name: str) -> Optional[str]:
        return self._sqs.get_queue_url(QueueName=queue_name).get("QueueUrl")

    def receive(
        self,
        queue_url: str,
        *,
        max_messages: int,
        visibility_timeout: int,
        wait_seconds: int,
        all_attributes: bool = False,
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": max_messages,
            "VisibilityTimeout": visibility_timeout,
            "WaitTimeSeconds": wait_seconds,
            "MessageAttributeNames": ["All"],
        }
        if all_attributes:
            kwargs["AttributeNames"] = ["All"]
        return self._sqs.receive_message(**kwargs).get("Messages", [])

    def send(self, queue_url: str, body: str, message_attributes: Dict[str, Any]) -> None:
        self._sqs.send_message(QueueUrl=queue_url, MessageBody=body, MessageAttributes=message_attributes)

    def delete(self, queue_url: str, receipt_handle: str) -> None:
        self._sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
