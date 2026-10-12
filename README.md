# floci-mcp-unofficial

[Model Context Protocol](https://modelcontextprotocol.io) server for [Floci](https://floci.io), the open-source local cloud emulator. It lets an AI agent (Claude, Cursor, any MCP client) inspect and provision your local AWS, Azure, GCP and OCI runtimes in natural language.

> **Unofficial community project.** Not affiliated with or endorsed by the Floci project. Floci does the emulation; this server only talks to it. Please support the [upstream project](https://github.com/floci-io/floci). Extracted from [Floci Studio](https://github.com/pmaojo/floci-studio), where it started.

## What it covers

| Cloud | Runtime | Default port | Tools |
|---|---|:-:|---|
| AWS | [floci](https://github.com/floci-io/floci) | 4566 | Lambda, SQS, SNS, S3, DynamoDB (incl. PartiQL), Secrets Manager, KMS, EventBridge, Step Functions, Athena, SES, tags, IaC, drift and more, through boto3 |
| Azure | [floci-az](https://github.com/floci-io/floci-az) | 4577 | Blob containers and blobs, queues, Key Vault secret names |
| GCP | [floci-gcp](https://github.com/floci-io/floci-gcp) | 4588 | Cloud Storage buckets and objects, Pub/Sub topics, Secret Manager secret names |
| OCI | [floci-oci](https://github.com/floci-io/floci-oci) | 4599 | Object Storage buckets and objects |

Azure, GCP and OCI are called through each provider's own REST contract, the same one their emulators serve. Start with `list_clouds`: it reports which runtimes answer, so the agent knows which tools can work. Reading secrets never returns their values.

Run the emulators with the `multicloud` profile of the [Floci UI compose file](https://github.com/floci-io/floci-ui/blob/main/docker-compose.yml), or on their own.

## Recipes as a kickstarter

`recipes/` holds a catalog of local Docker recipes (PostgreSQL, Redis, MinIO, Keycloak, RabbitMQ, Kafka, Temporal and others, each with a `recipe.json` and a Compose file). The marketplace tools let an agent bootstrap a stack from them:

- `list_marketplace_recipes`: the catalog with each recipe's configurable variables.
- `deploy_marketplace_app` / `teardown_marketplace_app`: install and remove a recipe with Docker Compose.
- `get_marketplace_installations` and `get_marketplace_logs`: state and logs.

A recipe is plain data, so you can add your own under `recipes/<name>/`. Docker has to be reachable from the machine running the server.

## Install

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/pmaojo/floci-mcp-unofficial
cd floci-mcp-unofficial
uv sync
uv run python floci_mcp.py     # stdio
```

Client configuration (Claude Desktop, Cursor, Claude Code):

```json
{
  "mcpServers": {
    "floci": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/floci-mcp-unofficial", "python", "/path/to/floci-mcp-unofficial/floci_mcp.py"],
      "env": {
        "AWS_ENDPOINT_URL": "http://localhost:4566",
        "FLOCI_AZURE_ENDPOINT": "http://localhost:4577",
        "FLOCI_GCP_ENDPOINT": "http://localhost:4588",
        "FLOCI_OCI_ENDPOINT": "http://localhost:4599"
      }
    }
  }
}
```

Docker instead of uv:

```bash
docker build -t floci-mcp-unofficial .
docker run -i --rm floci-mcp-unofficial
```

## Configuration

| Variable | Default |
|---|---|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` |
| `FLOCI_AZURE_ENDPOINT` | `http://localhost:4577` |
| `FLOCI_AZURE_ACCOUNT_NAME` | `devstoreaccount1` |
| `FLOCI_GCP_ENDPOINT` | `http://localhost:4588` |
| `FLOCI_GCP_PROJECT` | `floci-local` |
| `FLOCI_OCI_ENDPOINT` | `http://localhost:4599` |
| `FLOCI_OCI_TENANCY_ID` | Floci-OCI's built-in tenancy |
| `FLOCI_PLUGINS_DIR` | `plugins/` next to the server |

The variable names match [Floci UI](https://github.com/floci-io/floci-ui), so one `.env` serves both.

## Verify

```bash
uv run python verify_mcp.py       # handshake and tool listing (needs the AWS runtime)
uv run python verify_clouds.py    # live round trip against the Azure, GCP and OCI runtimes
```

## Plugins

A plugin is a directory `plugins/<name>/` with a `plugin.json` and a `tools.py` exposing `register(mcp)`. See `plugins/example_hello`.

## License

MIT
