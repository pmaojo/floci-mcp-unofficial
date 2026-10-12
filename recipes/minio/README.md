# 📦 MinIO for Floci

**MinIO** is a high-performance, S3-compatible object storage server. It is perfectly suited for large scale AI/ML, data lake, and database workloads.

For local development in Floci, MinIO acts as an incredible stand-in for Amazon S3, allowing you to test file uploads, bucket policies, and object lifecycle rules locally with zero cost.

## ✨ Features
- **S3 API Compatibility**: Use standard AWS SDKs (Boto3, AWS CLI, etc.) to interact with MinIO just like you would with real Amazon S3.
- **Visual Web Console**: A sleek, modern web interface to create buckets, manage access keys, and explore your stored objects interactively.
- **High Performance**: Built from the ground up to be blazingly fast.

## 🚀 Usage in Floci
You can customize the following parameters before launching MinIO:
- **S3 API Port**: The port your application connects to for S3 operations (default: `9000`).
- **Web Console Port**: The port used to access the visual dashboard (default: `9001`).
- **Root Credentials**: Secure your local instance with custom User and Password variables.

To connect your application to this MinIO instance, simply point your AWS SDK's `endpoint_url` to `http://localhost:<S3_API_PORT>`.

## 🚀 Path to AWS

**Managed service:** Amazon S3

MinIO speaks the S3 API, so buckets, objects and presigned URLs behave locally exactly as on real S3.

**Deploy:** Drop the custom endpoint from your AWS SDK config so the S3 client talks to real Amazon S3.
