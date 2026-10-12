# 🪣 S3 Admin for Floci Studio

**S3 Admin** is a lightweight web GUI for Amazon S3 — browse buckets, upload and download objects, and create or delete buckets, all from your browser. This recipe comes **pre-wired to your local Floci (LocalStack) S3 endpoint** on port `4566`, so what you test locally behaves exactly like real Amazon S3.

It mirrors the `dynamodb-admin` recipe: an AWS-SDK client pointed at the Floci emulator for true local↔AWS parity.

## ✨ Features
- **Bucket & object browser**: Explore buckets and their contents visually.
- **Upload / download**: Move objects in and out without the CLI.
- **Floci-ready**: Points at `host.docker.internal:4566` with dummy `test`/`test` credentials out of the box.

## 🚀 Usage in Floci Studio
When you start the S3 Admin recipe, you can configure:
- **Web UI Port**: Host port for the admin web UI (default: `8002`).
- **S3 Endpoint**: Host:port of the S3 endpoint (default: `host.docker.internal:4566`).
- **AWS Region**: Region used when connecting (default: `us-east-1`).

Open the UI at **http://localhost:8002** to browse the buckets in your local Floci S3.

```bash
# Seed a bucket via the Floci endpoint, then refresh the UI
aws --endpoint-url http://localhost:4566 s3 mb s3://my-bucket
aws --endpoint-url http://localhost:4566 s3 cp ./file.txt s3://my-bucket/
```

> ℹ️ Credentials default to dummy `test`/`test` values, which is exactly what LocalStack expects.

## 🚀 Path to AWS

**Managed service:** Amazon S3 console

Browses the very same buckets and objects locally (via the Floci endpoint on 4566) that you will see in the S3 console — same API, same presigned URLs.

**Deploy:** Already Floci-wired: set S3_ENDPOINT to your real regional S3 endpoint (or drop it) to point the browser at production S3.
