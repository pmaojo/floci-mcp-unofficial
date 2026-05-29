"""Herramientas SES: identidades verificadas y envío de emails."""
from tools._client import make_client


def register(mcp):

    @mcp.tool()
    async def list_ses_identities() -> dict:
        """Lista todas las identidades (emails y dominios) verificadas en SES."""
        r = make_client("ses").list_identities()
        return {"identities": r.get("Identities", [])}

    @mcp.tool()
    async def verify_ses_email(email: str) -> dict:
        """
        Inicia la verificación de una dirección de email en SES.

        En entornos locales (Floci) la verificación es instantánea.
        En AWS real, se envía un email de confirmación a la dirección indicada.
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
        Envía un email a través de SES.

        from_address debe estar verificado en SES.
        body_html complementa a body_text para clientes de email con soporte HTML.
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
        Obtiene las estadísticas de envío de SES: cuota máxima diaria,
        tasa máxima de envío (emails/segundo) y emails enviados en las últimas 24h.
        """
        r = make_client("ses").get_send_quota()
        return {
            "max_24_hour_send": r.get("Max24HourSend"),
            "max_send_rate": r.get("MaxSendRate"),
            "sent_last_24_hours": r.get("SentLast24Hours"),
        }
