"""Herramientas S3: buckets y objetos."""
from floci_tools._client import clean, config, make_client


def register(mcp):

    @mcp.tool()
    async def list_s3_buckets() -> dict:
        """Lists all S3 buckets in the environment."""
        r = make_client("s3").list_buckets()
        return {"buckets": clean([{"name": b["Name"], "created": b["CreationDate"]} for b in r.get("Buckets", [])])}

    @mcp.tool()
    async def create_s3_bucket(name: str) -> dict:
        """Creates an S3 bucket. The name must be unique: lowercase letters, digits and hyphens only."""
        c = make_client("s3")
        if config.aws_region == "us-east-1":
            c.create_bucket(Bucket=name)
        else:
            c.create_bucket(Bucket=name, CreateBucketConfiguration={"LocationConstraint": config.aws_region})
        return {"bucket": name, "created": True}

    @mcp.tool()
    async def delete_s3_bucket(name: str, force: bool = False) -> dict:
        """
        Deletes an S3 bucket.

        With force=true the bucket is emptied first. Without it, deleting a bucket that has objects fails.
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
        Lists the objects of an S3 bucket.

        Use prefix to filter by path, e.g. 'logs/' or 'data/2024/'.
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
        Uploads an object to S3 as plain text or serialized JSON.

        key is the full object path, e.g. 'data/config.json'.
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
        """Downloads an S3 object and returns its content as text."""
        r = make_client("s3").get_object(Bucket=bucket, Key=key)
        content = r["Body"].read().decode("utf-8", errors="replace")
        return {"bucket": bucket, "key": key, "content_type": r.get("ContentType"), "content": content}

    @mcp.tool()
    async def delete_s3_object(bucket: str, key: str) -> dict:
        """Deletes one object from an S3 bucket."""
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
        Generates a presigned URL for temporary access to an S3 object without credentials.

        operation: 'get_object' (download) or 'put_object' (upload).
        expires_in: validity in seconds (maximum 604800, 7 days).
        """
        url = make_client("s3").generate_presigned_url(
            ClientMethod=operation,
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return {"url": url, "expires_in": expires_in}
