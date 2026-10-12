# 🗄️ DynamoDB Admin for Floci Studio

**DynamoDB Admin** is a web-based GUI for Amazon DynamoDB. Browse tables, items and indexes, run queries and edit data — all from your browser. This recipe comes pre-wired to your local Floci (LocalStack) DynamoDB endpoint, so it just works out of the box.

## ✨ Features
- **Visual table browser**: Explore tables, items and secondary indexes.
- **Query & scan**: Run queries and scans without writing CLI commands.
- **Inline editing**: Create, edit and delete items from the UI.
- **Floci-ready**: Points at `host.docker.internal:4566` by default.

## 🚀 Usage in Floci Studio
When you start the DynamoDB Admin recipe, you can configure:
- **Web UI Port**: Host port for the admin web UI (default: `8001`).
- **DynamoDB Endpoint**: URL of the DynamoDB endpoint (default: `http://host.docker.internal:4566`).
- **AWS Region**: Region used when connecting (default: `us-east-1`).

Open the UI at **http://localhost:8001** to browse the tables in your local Floci DynamoDB.

> ℹ️ Credentials default to dummy `test`/`test` values, which is exactly what LocalStack expects.

## 🚀 Path to AWS

**Managed service:** Amazon DynamoDB console

Browses the very same tables locally (via the Floci endpoint on 4566) that you will see in the DynamoDB console — zero schema drift.

**Deploy:** Already Floci-wired: set DYNAMO_ENDPOINT to your real regional endpoint (or drop it) to inspect production DynamoDB.
