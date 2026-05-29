"""Herramientas SNS: topics, publicación y suscripciones."""
from tools._client import clean, make_client


def register(mcp):

    @mcp.tool()
    async def list_sns_topics() -> dict:
        """Lista todos los topics SNS del entorno con sus ARNs."""
        r = make_client("sns").list_topics()
        return {"topics": r.get("Topics", [])}

    @mcp.tool()
    async def create_sns_topic(
        name: str,
        fifo: bool = False,
        display_name: str | None = None,
    ) -> dict:
        """
        Crea un topic SNS estándar o FIFO.

        Los topics FIFO garantizan orden y deduplicación de mensajes.
        El sufijo .fifo se añade automáticamente si falta.
        display_name aparece como remitente en emails enviados desde este topic.
        """
        if fifo and not name.endswith(".fifo"):
            name = name + ".fifo"
        attrs: dict[str, str] = {}
        if fifo:
            attrs["FifoTopic"] = "true"
            attrs["ContentBasedDeduplication"] = "true"
        if display_name:
            attrs["DisplayName"] = display_name
        r = make_client("sns").create_topic(Name=name, Attributes=attrs)
        return {"topic_arn": r["TopicArn"], "name": name}

    @mcp.tool()
    async def delete_sns_topic(topic_arn: str) -> dict:
        """Elimina un topic SNS y todas sus suscripciones activas."""
        make_client("sns").delete_topic(TopicArn=topic_arn)
        return {"deleted": topic_arn}

    @mcp.tool()
    async def publish_sns_message(
        topic_arn: str,
        message: str,
        subject: str | None = None,
        message_attributes: dict | None = None,
    ) -> dict:
        """
        Publica un mensaje en un topic SNS distribuyéndolo a todos los suscriptores.

        subject es visible en emails. message_attributes permite filtrado por suscripción.
        Formato de message_attributes: {'clave': {'DataType': 'String', 'StringValue': 'valor'}}.
        """
        params: dict = {"TopicArn": topic_arn, "Message": message}
        if subject:
            params["Subject"] = subject
        if message_attributes:
            params["MessageAttributes"] = message_attributes
        r = make_client("sns").publish(**params)
        return {"message_id": r["MessageId"]}

    @mcp.tool()
    async def list_sns_subscriptions(topic_arn: str) -> dict:
        """Lista todas las suscripciones de un topic SNS con su protocolo, endpoint y estado."""
        r = make_client("sns").list_subscriptions_by_topic(TopicArn=topic_arn)
        return {"subscriptions": r.get("Subscriptions", [])}

    @mcp.tool()
    async def subscribe_sns(topic_arn: str, protocol: str, endpoint: str) -> dict:
        """
        Suscribe un endpoint a un topic SNS.

        Protocolos soportados: 'email', 'email-json', 'sqs', 'lambda', 'http', 'https', 'sms'.
        Para SQS usa el ARN de la cola. Para Lambda usa el ARN de la función.
        """
        r = make_client("sns").subscribe(TopicArn=topic_arn, Protocol=protocol, Endpoint=endpoint)
        return {"subscription_arn": r.get("SubscriptionArn")}

    @mcp.tool()
    async def unsubscribe_sns(subscription_arn: str) -> dict:
        """Elimina una suscripción de un topic SNS usando su ARN."""
        make_client("sns").unsubscribe(SubscriptionArn=subscription_arn)
        return {"unsubscribed": subscription_arn}

    @mcp.tool()
    async def get_sns_topic_attributes(topic_arn: str) -> dict:
        """Obtiene los atributos de un topic SNS: nombre, tipo FIFO, política de entrega, etc."""
        r = make_client("sns").get_topic_attributes(TopicArn=topic_arn)
        return r.get("Attributes", {})
