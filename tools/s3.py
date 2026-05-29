"""Herramientas S3: buckets y objetos."""
from tools._client import clean, config, make_client


def register(mcp):

    @mcp.tool()
    async def list_s3_buckets() -> dict:
        """Lista todos los buckets S3 del entorno."""
        r = make_client("s3").list_buckets()
        return {"buckets": clean([{"name": b["Name"], "created": b["CreationDate"]} for b in r.get("Buckets", [])])}

    @mcp.tool()
    async def create_s3_bucket(name: str) -> dict:
        """Crea un nuevo bucket S3. El nombre debe ser único, solo minúsculas, números y guiones."""
        c = make_client("s3")
        if config.aws_region == "us-east-1":
            c.create_bucket(Bucket=name)
        else:
            c.create_bucket(Bucket=name, CreateBucketConfiguration={"LocationConstraint": config.aws_region})
        return {"bucket": name, "created": True}

    @mcp.tool()
    async def delete_s3_bucket(name: str, force: bool = False) -> dict:
        """
        Elimina un bucket S3.

        Si force=true, vacía todos los objetos del bucket antes de eliminarlo.
        Sin force=true, falla si el bucket tiene contenido.
        """
        c = make_client("s3")
        if force:
            paginator = c.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=name):
                objects = page.get("Contents", [])
                if objects:
                    c.delete_objects(Bucket=name, Delete={"Objects": [{"Key": o["Key"]} for o in objects]})
        c.delete_bucket(Bucket=name)
        return {"deleted": name}

    @mcp.tool()
    async def list_s3_objects(
        bucket: str,
        prefix: str | None = None,
        max_keys: int = 100,
    ) -> dict:
        """
        Lista objetos de un bucket S3.

        Usa prefix para filtrar por ruta (ej. 'logs/', 'data/2024/').
        """
        params: dict = {"Bucket": bucket, "MaxKeys": max_keys}
        if prefix:
            params["Prefix"] = prefix
        r = make_client("s3").list_objects_v2(**params)
        objects = clean([{"key": o["Key"], "size": o["Size"], "last_modified": o["LastModified"]} for o in r.get("Contents", [])])
        return {"bucket": bucket, "count": len(objects), "objects": objects}

    @mcp.tool()
    async def put_s3_object(
        bucket: str,
        key: str,
        content: str,
        content_type: str = "text/plain",
    ) -> dict:
        """
        Sube un objeto a S3 con contenido en texto plano o JSON serializado.

        key es la ruta completa del objeto, ej. 'data/config.json'.
        """
        make_client("s3").put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode(),
            ContentType=content_type,
        )
        return {"bucket": bucket, "key": key, "uploaded": True}

    @mcp.tool()
    async def get_s3_object(bucket: str, key: str) -> dict:
        """Descarga y devuelve el contenido de un objeto S3 como texto."""
        r = make_client("s3").get_object(Bucket=bucket, Key=key)
        content = r["Body"].read().decode("utf-8", errors="replace")
        return {"bucket": bucket, "key": key, "content_type": r.get("ContentType"), "content": content}

    @mcp.tool()
    async def delete_s3_object(bucket: str, key: str) -> dict:
        """Elimina un objeto de un bucket S3."""
        make_client("s3").delete_object(Bucket=bucket, Key=key)
        return {"deleted": f"s3://{bucket}/{key}"}

    @mcp.tool()
    async def generate_s3_presigned_url(
        bucket: str,
        key: str,
        operation: str = "get_object",
        expires_in: int = 3600,
    ) -> dict:
        """
        Genera una URL pre-firmada para acceso temporal a un objeto S3 sin autenticación.

        operation: 'get_object' (descarga) o 'put_object' (subida).
        expires_in: segundos de validez (máximo 604800 = 7 días).
        """
        url = make_client("s3").generate_presigned_url(
            ClientMethod=operation,
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return {"url": url, "expires_in": expires_in}
