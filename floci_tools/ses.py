"""Herramientas SES: identidades verificadas y envío de emails."""
from floci_tools._client import make_client


def register(mcp):

    @mcp.tool()
    async def list_ses_identities() -> dict:
        """Lists the verified SES identities (email addresses and domains)."""
        r = make_client("ses").list_identities()
        return {"identities": r.get("Identities", [])}

    @mcp.tool()
    async def verify_ses_email(email: str) -> dict:
        """
        Starts the verification of an email address in SES.

        On the local emulator verification is instant. On real AWS a confirmation email is sent.
        """
        make_client("ses").verify_email_identity(EmailAddress=email)
        return {"email": email, "verification_initiated": True}

    @mcp.tool()
    async def send_ses_email(
        from_address: str,
        to_addresses: list,
        subject: str,
        body_text: str,
        body_html: str | None = None,
        cc_addresses: list | None = None,
    ) -> dict:
        """
        Sends an email through SES.

        from_address must be verified in SES. body_html complements body_text for HTML-capable clients.
        """
        body: dict = {"Text": {"Data": body_text, "Charset": "UTF-8"}}
        if body_html:
            body["Html"] = {"Data": body_html, "Charset": "UTF-8"}
        destination: dict = {"ToAddresses": to_addresses}
        if cc_addresses:
            destination["CcAddresses"] = cc_addresses
        r = make_client("ses").send_email(
            Source=from_address,
            Destination=destination,
            Message={"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": body},
        )
        return {"message_id": r["MessageId"]}

    @mcp.tool()
    async def get_ses_send_quota() -> dict:
        """
        Gets the SES sending statistics: maximum daily quota, maximum send rate
        (emails per second) and emails sent in the last 24 hours.
        """
        r = make_client("ses").get_send_quota()
        return {
            "max_24_hour_send": r.get("Max24HourSend"),
            "max_send_rate": r.get("MaxSendRate"),
            "sent_last_24_hours": r.get("SentLast24Hours"),
        }
