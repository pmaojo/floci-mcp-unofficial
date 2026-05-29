"""Herramientas KMS: claves de cifrado, encrypt y decrypt."""
import base64
from tools._client import backend, make_client


def register(mcp):

    @mcp.tool()
    async def run_kms_diagnostic() -> dict:
        """Ejecuta un test de cifrado/descifrado round-trip con KMS para verificar que el servicio funciona."""
        return await backend("GET", "/api/diagnostics/kms")

    @mcp.tool()
    async def list_kms_keys() -> dict:
        """Lista todas las claves KMS del entorno con sus IDs, ARNs y aliases."""
        c = make_client("kms")
        keys = c.list_keys().get("Keys", [])
        aliases = {a.get("TargetKeyId"): a.get("AliasName") for a in c.list_aliases().get("Aliases", []) if a.get("TargetKeyId")}
        return {"keys": [{"key_id": k["KeyId"], "arn": k["KeyArn"], "alias": aliases.get(k["KeyId"])} for k in keys]}

    @mcp.tool()
    async def create_kms_key(description: str | None = None, alias: str | None = None) -> dict:
        """
        Crea una nueva clave de cifrado KMS.

        alias debe empezar con 'alias/' (ej. 'alias/mi-clave'). Se añade automáticamente si falta el prefijo.
        """
        c = make_client("kms")
        params: dict = {}
        if description:
            params["Description"] = description
        r = c.create_key(**params)
        key_id = r["KeyMetadata"]["KeyId"]
        if alias:
            if not alias.startswith("alias/"):
                alias = f"alias/{alias}"
            c.create_alias(AliasName=alias, TargetKeyId=key_id)
        return {"key_id": key_id, "arn": r["KeyMetadata"]["Arn"], "alias": alias}

    @mcp.tool()
    async def kms_encrypt(key_id: str, plaintext: str) -> dict:
        """
        Cifra texto con una clave KMS. Devuelve el ciphertext en base64.

        key_id puede ser el ID, ARN o alias (ej. 'alias/mi-clave') de la clave.
        """
        r = make_client("kms").encrypt(KeyId=key_id, Plaintext=plaintext.encode())
        return {"ciphertext_blob": base64.b64encode(r["CiphertextBlob"]).decode(), "key_id": r["KeyId"]}

    @mcp.tool()
    async def kms_decrypt(ciphertext_blob: str) -> dict:
        """
        Descifra un ciphertext KMS (en base64) y devuelve el texto original.

        ciphertext_blob es el valor 'ciphertext_blob' devuelto por kms_encrypt.
        """
        r = make_client("kms").decrypt(CiphertextBlob=base64.b64decode(ciphertext_blob))
        return {"plaintext": r["Plaintext"].decode(), "key_id": r["KeyId"]}
