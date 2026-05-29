"""Herramientas Secrets Manager: crear, leer, actualizar y eliminar secretos."""
from tools._client import make_client


def register(mcp):

    @mcp.tool()
    async def list_secrets() -> dict:
        """Lista todos los secretos de AWS Secrets Manager del entorno."""
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
        Crea un nuevo secreto en Secrets Manager.

        value puede ser un string o un JSON serializado (ej. '{"user":"admin","pass":"xyz"}').
        """
        params: dict = {"Name": name, "SecretString": value}
        if description:
            params["Description"] = description
        r = make_client("secretsmanager").create_secret(**params)
        return {"arn": r["ARN"], "name": r["Name"]}

    @mcp.tool()
    async def get_secret_value(name_or_arn: str) -> dict:
        """Obtiene el valor de un secreto de Secrets Manager por nombre o ARN."""
        r = make_client("secretsmanager").get_secret_value(SecretId=name_or_arn)
        return {"name": r["Name"], "arn": r["ARN"], "value": r.get("SecretString")}

    @mcp.tool()
    async def update_secret(name_or_arn: str, value: str) -> dict:
        """Actualiza el valor de un secreto existente en Secrets Manager."""
        r = make_client("secretsmanager").update_secret(SecretId=name_or_arn, SecretString=value)
        return {"arn": r["ARN"], "updated": True}

    @mcp.tool()
    async def delete_secret(name_or_arn: str, force: bool = False) -> dict:
        """
        Elimina un secreto de Secrets Manager.

        Con force=true, elimina inmediatamente sin período de recuperación de 30 días.
        """
        params: dict = {"SecretId": name_or_arn}
        if force:
            params["ForceDeleteWithoutRecovery"] = True
        make_client("secretsmanager").delete_secret(**params)
        return {"deleted": name_or_arn}
