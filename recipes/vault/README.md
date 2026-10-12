# 🔐 HashiCorp Vault for Floci Studio

**Vault** centralizes secrets management, dynamic credentials, and encryption-as-a-service. This recipe runs Vault in **dev mode** — an in-memory, pre-unsealed server that's perfect for local development and a great local analogue to **AWS Secrets Manager** and **SSM Parameter Store**.

> ⚠️ Dev mode stores everything in memory and is **not** for production. Data is lost when the container stops.

## ✨ Features
- **Auto-unsealed dev server**: Ready to use the moment it boots.
- **Web UI + HTTP API**: Manage secrets visually or programmatically.
- **KV secrets engine**: Mounted at `secret/` out of the box.

## 🚀 Usage in Floci Studio
When you start the Vault recipe, you can configure:
- **HTTP / UI Port**: Host port for the API and web UI (default: `8200`).
- **Root Token**: Token used to authenticate (default: `root`).

### Write and read a secret
```bash
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root

# Store a secret
docker exec -e VAULT_TOKEN=root floci-vault \
  vault kv put secret/myapp db_password=s3cr3t

# Read it back
docker exec -e VAULT_TOKEN=root floci-vault \
  vault kv get secret/myapp
```

Open the UI at **http://localhost:8200** and sign in with the root token.

## 🚀 Path to AWS

**Managed service:** AWS Secrets Manager + KMS

Read/write secrets locally through Vault's API exactly as you will via Secrets Manager — same get/put lifecycle.

**Deploy:** Migrate the KV secrets into AWS Secrets Manager and swap the SDK; use KMS for the encryption keys.
