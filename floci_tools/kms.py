"""Herramientas KMS: claves de cifrado, encrypt y decrypt."""
import base64
from floci_tools._client import backend, make_client


def register(mcp):

    @mcp.tool()
    async def run_kms_diagnostic() -> dict:
        """Runs an encrypt/decrypt round trip with KMS to verify that the service works. Creates a key."""
        return await backend("GET", "/api/diagnostics/kms")

    @mcp.tool()
    async def list_kms_keys() -> dict:
        """Lists all KMS keys in the environment with their IDs, ARNs and aliases."""
        c = make_client("kms")
        keys = c.list_keys().get("Keys", [])
        aliases = {a.get("TargetKeyId"): a.get("AliasName") for a in c.list_aliases().get("Aliases", []) if a.get("TargetKeyId")}
        return {"keys": [{"key_id": k["KeyId"], "arn": k["KeyArn"], "alias": aliases.get(k["KeyId"])} for k in keys]}

    @mcp.tool()
    async def create_kms_key(description: str | None = None, alias: str | None = None) -> dict:
        """
        Creates a KMS encryption key.

        alias must start with 'alias/' (e.g. 'alias/my-key'); the prefix is added if missing.
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
        Encrypts text with a KMS key. Returns the ciphertext in base64.

        key_id can be the key ID, ARN or alias (e.g. 'alias/my-key').
        """
        r = make_client("kms").encrypt(KeyId=key_id, Plaintext=plaintext.encode())
        return {"ciphertext_blob": base64.b64encode(r["CiphertextBlob"]).decode(), "key_id": r["KeyId"]}

    @mcp.tool()
    async def kms_decrypt(ciphertext_blob: str) -> dict:
        """
        Decrypts a KMS ciphertext (base64) and returns the original text.

        ciphertext_blob is the 'ciphertext_blob' value returned by kms_encrypt.
        """
        r = make_client("kms").decrypt(CiphertextBlob=base64.b64decode(ciphertext_blob))
        return {"plaintext": r["Plaintext"].decode(), "key_id": r["KeyId"]}
