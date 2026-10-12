"""Herramientas SNS: topics, publicación y suscripciones."""
from tools._client import clean, make_client


def register(mcp):

    @mcp.tool()
    async def list_sns_topics() -> dict:
        """Lists all SNS topics in the environment with their ARNs."""
        r = make_client("sns").list_topics()
        return {"topics": r.get("Topics", [])}

    @mcp.tool()
    async def create_sns_topic(
        name: str,
        fifo: bool = False,
        display_name: str | None = None,
    ) -> dict:
        """
        Creates a standard or FIFO SNS topic.

        FIFO topics guarantee ordering and deduplication. The .fifo suffix is added if missing.
        display_name appears as the sender of emails sent from this topic.
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
        """Deletes an SNS topic and all of its active subscriptions."""
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
        Publishes a message to an SNS topic, fanning it out to every subscriber.

        subject is visible in emails. message_attributes enables per-subscription filtering:
        {'key': {'DataType': 'String', 'StringValue': 'value'}}.
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
        """Lists the subscriptions of an SNS topic with protocol, endpoint and status."""
        r = make_client("sns").list_subscriptions_by_topic(TopicArn=topic_arn)
        return {"subscriptions": r.get("Subscriptions", [])}

    @mcp.tool()
    async def subscribe_sns(topic_arn: str, protocol: str, endpoint: str) -> dict:
        """
        Subscribes an endpoint to an SNS topic.

        Protocols: 'email', 'email-json', 'sqs', 'lambda', 'http', 'https', 'sms'.
        For SQS use the queue ARN. For Lambda use the function ARN.
        """
        r = make_client("sns").subscribe(TopicArn=topic_arn, Protocol=protocol, Endpoint=endpoint)
        return {"subscription_arn": r.get("SubscriptionArn")}

    @mcp.tool()
    async def unsubscribe_sns(subscription_arn: str) -> dict:
        """Removes an SNS subscription by its ARN."""
        make_client("sns").unsubscribe(SubscriptionArn=subscription_arn)
        return {"unsubscribed": subscription_arn}

    @mcp.tool()
    async def get_sns_topic_attributes(topic_arn: str) -> dict:
        """Gets the attributes of an SNS topic: name, FIFO type, delivery policy and more."""
        r = make_client("sns").get_topic_attributes(TopicArn=topic_arn)
        return r.get("Attributes", {})
