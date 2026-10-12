"""Herramientas SQS: colas estándar y FIFO, mensajes y atributos."""
from tools._client import clean, make_client


def register(mcp):

    @mcp.tool()
    async def list_sqs_queues() -> dict:
        """Lists all SQS queues in the environment with their URLs."""
        r = make_client("sqs").list_queues()
        return {"queues": r.get("QueueUrls", [])}

    @mcp.tool()
    async def create_sqs_queue(
        name: str,
        fifo: bool = False,
        visibility_timeout: int | None = None,
        message_retention_seconds: int | None = None,
        delay_seconds: int | None = None,
    ) -> dict:
        """
        Creates a standard or FIFO SQS queue.

        FIFO queues (fifo=true) deliver in order, exactly once. The .fifo suffix is added if missing.
        """
        if fifo and not name.endswith(".fifo"):
            name = name + ".fifo"
        attrs: dict[str, str] = {}
        if fifo:
            attrs["FifoQueue"] = "true"
            attrs["ContentBasedDeduplication"] = "true"
        if visibility_timeout is not None:
            attrs["VisibilityTimeout"] = str(visibility_timeout)
        if message_retention_seconds is not None:
            attrs["MessageRetentionPeriod"] = str(message_retention_seconds)
        if delay_seconds is not None:
            attrs["DelaySeconds"] = str(delay_seconds)
        r = make_client("sqs").create_queue(QueueName=name, Attributes=attrs)
        return {"queue_url": r["QueueUrl"], "name": name}

    @mcp.tool()
    async def delete_sqs_queue(queue_url: str) -> dict:
        """Permanently deletes an SQS queue and all of its messages."""
        make_client("sqs").delete_queue(QueueUrl=queue_url)
        return {"deleted": queue_url}

    @mcp.tool()
    async def send_sqs_message(
        queue_url: str,
        body: str,
        message_group_id: str | None = None,
        message_deduplication_id: str | None = None,
        delay_seconds: int | None = None,
    ) -> dict:
        """
        Sends a message to an SQS queue.

        For FIFO queues message_group_id is required. delay_seconds only applies to standard queues.
        """
        params: dict = {"QueueUrl": queue_url, "MessageBody": body}
        if message_group_id:
            params["MessageGroupId"] = message_group_id
        if message_deduplication_id:
            params["MessageDeduplicationId"] = message_deduplication_id
        if delay_seconds is not None:
            params["DelaySeconds"] = delay_seconds
        r = make_client("sqs").send_message(**params)
        return {"message_id": r["MessageId"], "md5": r.get("MD5OfMessageBody")}

    @mcp.tool()
    async def receive_sqs_messages(
        queue_url: str,
        max_messages: int = 10,
        wait_seconds: int = 0,
        visibility_timeout: int | None = None,
    ) -> dict:
        """
        Receives messages from an SQS queue.

        Messages stay invisible until deleted with delete_sqs_message.
        wait_seconds > 0 enables long polling (recommended for quiet queues).
        Returns up to max_messages messages (maximum 10).
        """
        params: dict = {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": min(max_messages, 10),
            "WaitTimeSeconds": wait_seconds,
            "AttributeNames": ["All"],
            "MessageAttributeNames": ["All"],
        }
        if visibility_timeout is not None:
            params["VisibilityTimeout"] = visibility_timeout
        r = make_client("sqs").receive_message(**params)
        messages = clean(r.get("Messages", []))
        return {"count": len(messages), "messages": messages}

    @mcp.tool()
    async def delete_sqs_message(queue_url: str, receipt_handle: str) -> dict:
        """
        Deletes a message from a queue using its receipt_handle.

        The receipt_handle comes from receive_sqs_messages. A message that is not deleted
        becomes visible again after the visibility_timeout.
        """
        make_client("sqs").delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
        return {"deleted": True}

    @mcp.tool()
    async def get_sqs_queue_attributes(queue_url: str) -> dict:
        """
        Gets every attribute of an SQS queue.

        Includes the number of available and in-flight messages, timeouts, the dead-letter
        queue configuration and the queue type (FIFO or standard).
        """
        r = make_client("sqs").get_queue_attributes(QueueUrl=queue_url, AttributeNames=["All"])
        return r.get("Attributes", {})

    @mcp.tool()
    async def purge_sqs_queue(queue_url: str) -> dict:
        """Removes all messages from an SQS queue immediately. The queue itself stays."""
        make_client("sqs").purge_queue(QueueUrl=queue_url)
        return {"purged": queue_url}
