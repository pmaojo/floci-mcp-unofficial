"""Herramientas Secrets Manager: crear, leer, actualizar y eliminar secretos."""
from floci_tools._client import make_client


def register(mcp):

    @mcp.tool()
    async def list_secrets() -> dict:
        """Lists all AWS Secrets Manager secrets in the environment."""
        r = make_client("secretsmanager").list_secrets()
        return {
            "secrets": [
                {"name": s["Name"], "arn": s["ARN"], "description": s.get("Description", "")}
                for s in r.get("SecretList", [])
            ]
        }

    @mcp.tool()
    async def create_secret(name: str, value: str, description: str | None = None) -> dict:
        """
        Creates a Secrets Manager secret.

        value can be a string or serialized JSON, e.g. '{"user":"admin","pass":"xyz"}'.
        """
        params: dict = {"Name": name, "SecretString": value}
        if description:
            params["Description"] = description
        r = make_client("secretsmanager").create_secret(**params)
        return {"arn": r["ARN"], "name": r["Name"]}

    @mcp.tool()
    async def get_secret_value(name_or_arn: str) -> dict:
        """Gets the value of a Secrets Manager secret by name or ARN."""
        r = make_client("secretsmanager").get_secret_value(SecretId=name_or_arn)
        return {"name": r["Name"], "arn": r["ARN"], "value": r.get("SecretString")}

    @mcp.tool()
    async def update_secret(name_or_arn: str, value: str) -> dict:
        """Updates the value of an existing Secrets Manager secret."""
        r = make_client("secretsmanager").update_secret(SecretId=name_or_arn, SecretString=value)
        return {"arn": r["ARN"], "updated": True}

    @mcp.tool()
    async def delete_secret(name_or_arn: str, force: bool = False) -> dict:
        """
        Deletes a Secrets Manager secret.

        With force=true it is deleted immediately, without the 30-day recovery window.
        """
        params: dict = {"SecretId": name_or_arn}
        if force:
            params["ForceDeleteWithoutRecovery"] = True
        make_client("secretsmanager").delete_secret(**params)
        return {"deleted": name_or_arn}
