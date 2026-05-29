"""Herramientas SQS: colas estándar y FIFO, mensajes y atributos."""
from tools._client import clean, make_client


def register(mcp):

    @mcp.tool()
    async def list_sqs_queues() -> dict:
        """Lista todas las colas SQS del entorno con sus URLs."""
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
        Crea una cola SQS estándar o FIFO.

        Las colas FIFO (fifo=true) tienen entrega ordenada y exactamente una vez.
        El sufijo .fifo se añade automáticamente si falta.
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
        """Elimina permanentemente una cola SQS y todos sus mensajes."""
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
        Envía un mensaje a una cola SQS.

        Para colas FIFO, message_group_id es obligatorio.
        delay_seconds solo aplica a colas estándar.
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
        Recibe mensajes de una cola SQS.

        Los mensajes quedan invisibles hasta que se eliminen con delete_sqs_message.
        wait_seconds > 0 activa long polling (recomendado para colas poco activas).
        Devuelve hasta max_messages mensajes (máximo 10).
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
        Elimina un mensaje de la cola usando su receipt_handle.

        El receipt_handle se obtiene al llamar a receive_sqs_messages.
        Un mensaje no eliminado vuelve a ser visible tras el visibility_timeout.
        """
        make_client("sqs").delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
        return {"deleted": True}

    @mcp.tool()
    async def get_sqs_queue_attributes(queue_url: str) -> dict:
        """
        Obtiene todos los atributos de una cola SQS.

        Incluye: número de mensajes disponibles e invisibles, timeouts,
        configuración de DLQ, tipo de cola (FIFO/estándar), etc.
        """
        r = make_client("sqs").get_queue_attributes(QueueUrl=queue_url, AttributeNames=["All"])
        return r.get("Attributes", {})

    @mcp.tool()
    async def purge_sqs_queue(queue_url: str) -> dict:
        """Vacía todos los mensajes de una cola SQS al instante. La cola permanece activa."""
        make_client("sqs").purge_queue(QueueUrl=queue_url)
        return {"purged": queue_url}
