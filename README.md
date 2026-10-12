# floci-mcp-unofficial

[Model Context Protocol](https://modelcontextprotocol.io) server for [Floci](https://floci.io), the open-source local cloud emulator. It lets an AI agent (Claude, Cursor, any MCP client) inspect and provision your local AWS, Azure, GCP and OCI runtimes in natural language.

> **Unofficial community project.** Not affiliated with or endorsed by the Floci project. Floci does the emulation; this server only talks to it. Please support the [upstream project](https://github.com/floci-io/floci). Extracted from [Floci Studio](https://github.com/pmaojo/floci-studio), where it started.

**Site and live catalog of every tool, skill and recipe:** [`docs/index.html`](docs/index.html) (regenerate with `uv run python scripts/build_catalog.py`; the Vercel build does it on every deploy).

## Quick start

```bash
git clone https://github.com/pmaojo/floci-mcp-unofficial && cd floci-mcp-unofficial
uv sync
uv run python floci_mcp.py        # stdio; point your MCP client at it (see Install)
```

You need a running Floci (`localhost:4566`). Then install the skills below so the agent knows how to use the tools.

**Claude Code, in two commands** (server, skills and settings together):

```
/plugin marketplace add pmaojo/floci-mcp-unofficial
/plugin install floci@floci-mcp-unofficial
```

Claude Code asks for the toolsets, read-only mode and endpoints when you enable it, and the skills appear as `/floci:floci-explore` and so on. See [Use it from other agents](#use-it-from-other-agents) for Codex, DeepSeek-TUI/Codewhale, Cursor and Claude Desktop.

## Skills

Skills are short playbooks an agent loads on demand ([Agent Skills](https://docs.claude.com/en/docs/claude-code/skills): a folder with a `SKILL.md`). Each one names the tools it calls and the [toolsets](#toolsets-and-read-only-mode) it needs, and asks before it writes.

| Skill | Use it to | Toolsets |
|---|---|---|
| [`floci-explore`](skills/floci-explore/SKILL.md) | See what is running: health, services with resources, topology, cost | `core` |
| [`floci-multicloud`](skills/floci-multicloud/SKILL.md) | Line up storage, queues and secrets across AWS, Azure, GCP and OCI | `core`, `storage`, `messaging` |
| [`floci-triage`](skills/floci-triage/SKILL.md) | Find and explain stuck messages in dead-letter queues, then redrive on confirmation | `ops`, `messaging` |
| [`floci-seed`](skills/floci-seed/SKILL.md) | Fill a table, bucket or database with synthetic data | `storage`, `hybrid` |
| [`floci-iac`](skills/floci-iac/SKILL.md) | Export the emulator as Terraform or CDK, and check code for drift | `core`, `ops`, `hybrid` |
| [`floci-marketplace`](skills/floci-marketplace/SKILL.md) | Start, inspect and remove local Docker stacks from the recipe catalog | `marketplace` |

Install them for Claude Code (personal skills; use `.claude/skills/` inside a project for a per-project install):

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD"/skills/* ~/.claude/skills/      # or: cp -R skills/* ~/.claude/skills/
```

Skills that need a toolset which is not enabled by default tell the agent to ask you to enable it (see below).

## What it covers

| Cloud | Runtime | Default port | Tools |
|---|---|:-:|---|
| AWS | [floci](https://github.com/floci-io/floci) | 4566 | Lambda, SQS, SNS, S3, DynamoDB (incl. PartiQL), Secrets Manager, KMS, EventBridge, Step Functions, Athena, SES, tags, IaC, drift and more, through boto3 |
| Azure | [floci-az](https://github.com/floci-io/floci-az) | 4577 | Blob containers and blobs, queues, Key Vault secret names |
| GCP | [floci-gcp](https://github.com/floci-io/floci-gcp) | 4588 | Cloud Storage buckets and objects, Pub/Sub topics, Secret Manager secret names |
| OCI | [floci-oci](https://github.com/floci-io/floci-oci) | 4599 | Object Storage buckets and objects |

Azure, GCP and OCI are called through each provider's own REST contract, the same one their emulators serve. Start with `list_clouds`: it reports which runtimes answer, so the agent knows which tools can work.

Run the emulators with the `multicloud` profile of the [Floci UI compose file](https://github.com/floci-io/floci-ui/blob/main/docker-compose.yml), or on their own.

## Toolsets and read-only mode

A client sends every tool definition to the model on every conversation. All 138 tools cost about 16K tokens, and models pick worse when many similar tools are visible. So tools are grouped and only some are registered.

| Toolset | Modules | Default |
|---|---|:-:|
| `core` | meta, clouds | yes |
| `storage` | s3, dynamodb, secrets, kms | yes |
| `messaging` | sqs, sns, eventbridge, stepfunctions, ses | yes |
| `compute` | lambda, athena | yes |
| `ops` | tags, observability, iac | |
| `marketplace` | marketplace, pipeline | |
| `hybrid` | hybrid, devtools, extensibility | |

The default registers 90 tools (about 9K tokens). `FLOCI_TOOLSETS=all` registers everything.

```bash
FLOCI_TOOLSETS=core,storage    # only these (comma separated, case insensitive)
FLOCI_TOOLSETS=all             # everything
FLOCI_READ_ONLY=1              # remove every tool that changes state
```

An unknown toolset name stops the server at startup and lists the valid ones. Every tool carries MCP annotations (`readOnlyHint`, `destructiveHint`, `openWorldHint`) so a client can ask before a write, and `list_toolsets` tells an agent what is enabled and how to enable the rest.

Claude Code also defers MCP tool definitions by itself (tool search is on by default there), so the token cost above matters most for clients without that.

### Switching toolsets while it runs

The agent decides what it needs. The server registers `enable_toolset` and `disable_toolset`, advertises `tools.listChanged` and sends `notifications/tools/list_changed` after each change, so a toolset that was not registered at the start can be switched on without a restart and switched off again to save context. Read-only mode still applies to whatever gets enabled.

```bash
FLOCI_TOOLSETS=core                          # what is registered at the start
FLOCI_TOOLSETS_ALLOWED=ops,marketplace       # optional: cap what an agent may enable
FLOCI_TOOLSETS_ALLOWED=                      # optional: forbid switching altogether
```

Unset, an agent can reach every toolset, `hybrid` included. That toolset holds the tools that use real AWS credentials and request arbitrary URLs; they carry `openWorldHint`, so a client can confirm before one runs, and `FLOCI_READ_ONLY=1` removes the ones that write. If you want a restriction to hold against the agent, set `FLOCI_TOOLSETS_ALLOWED`.

Claude Code applies `list_changed` in interactive sessions and in `-p` mode. Other clients vary; if yours ignores it, set the toolsets up front.

### Measuring it

```bash
uv run python eval/run.py static       # tokens per configuration
uv run python eval/run.py retrieval    # does BM25 find the expected tool? (offline)
ANTHROPIC_API_KEY=... uv run python eval/run.py model   # real tool selection by a model
```

`eval/tasks.json` holds 40 realistic tasks. The model mode sends only the definitions and the task, reads the first tool call and executes nothing.

## Recipes as a kickstarter

`recipes/` holds a catalog of local Docker recipes (PostgreSQL, Redis, MinIO, Keycloak, RabbitMQ, Kafka, Temporal and others, each with a `recipe.json` and a Compose file). They need the `marketplace` toolset:

- `list_marketplace_recipes`: the catalog with each recipe's configurable variables.
- `deploy_marketplace_app` / `teardown_marketplace_app`: install and remove a recipe with Docker Compose.
- `get_marketplace_installations` and `get_marketplace_logs`: state and logs.
- `deploy_to_environment` and `promote_recipe`: the same recipe across `test` and `demo`.

A recipe is plain data, so you can add your own under `recipes/<name>/`.

## Install

Requirements:

| Needs | For |
|---|---|
| Python 3.10+ and [uv](https://docs.astral.sh/uv/) | everything |
| A running Floci | everything |
| The [`aws` CLI](https://aws.amazon.com/cli/) on `PATH` | `run_local_aws_cmd`, creating Lambda functions and the Glue catalog |
| Docker with Compose | the marketplace and pipeline tools |

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
        "FLOCI_OCI_ENDPOINT": "http://localhost:4599",
        "FLOCI_TOOLSETS": "core,storage,messaging,compute"
      }
    }
  }
}
```

### Docker

The image bundles the `aws` CLI and the Docker CLI. It reaches the emulators on `host.docker.internal`; mount the Docker socket to use the marketplace tools.

```bash
docker build -t floci-mcp-unofficial .
docker run -i --rm \
  --add-host=host.docker.internal:host-gateway \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e FLOCI_TOOLSETS=all \
  floci-mcp-unofficial
```

Mounting the socket gives the server control of your Docker daemon. Leave it out unless you need the marketplace.

## Use it from other agents

The server speaks plain MCP over stdio, so any MCP client works. The snippets below come from each tool's own documentation; only the Claude Code plugin is validated here.

| Agent | How |
|---|---|
| **Claude Code** | The plugin above, or `claude mcp add floci -- uv run --project /path/to/floci-mcp-unofficial python /path/to/floci-mcp-unofficial/floci_mcp.py` |
| **Claude Desktop, Cursor** | The JSON under [Install](#install) |
| **Codex CLI** | `codex mcp add floci -- uv run --project /path/to/floci-mcp-unofficial python /path/to/floci-mcp-unofficial/floci_mcp.py`, or a `[mcp_servers.floci]` table in `~/.codex/config.toml` |
| **DeepSeek-TUI / Codewhale** | `~/.codewhale/mcp.json` with the same entry under `servers` (or `mcpServers`), then `codewhale mcp validate` |

Skills are plain `SKILL.md` folders. Codewhale discovers `.claude/skills/<name>/SKILL.md` in the workspace or globally, so the `ln -s` command in [Skills](#skills) serves it too. Its Claude-plugin import does not expand `${CLAUDE_PLUGIN_ROOT}`, so use the explicit paths above there rather than the plugin.

Wherever you run it, the client starts the server from its own directory. The recipe catalog is found relative to the code, and state is kept in `~/.floci-mcp`, never in your project.

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
| `FLOCI_TOOLSETS` | `core,storage,messaging,compute` (`all` for everything) |
| `FLOCI_TOOLSETS_ALLOWED` | every toolset (an empty value forbids switching) |
| `FLOCI_READ_ONLY` | off |
| `FLOCI_PLUGINS_DIR` | `plugins/` next to the server |
| `SIDECAR_STATE_DIR` | `~/.floci-mcp` |
| `FLOCI_RECIPES_DIR` | `recipes/` next to the server |

The endpoint and project variables match [Floci UI](https://github.com/floci-io/floci-ui), so one `.env` serves both. The server writes its state (webhooks, captured events, a topology file) under `SIDECAR_STATE_DIR`.

## Safety

An agent with these tools can change your machine. What to know:

- **60 tools write.** `FLOCI_READ_ONLY=1` removes them; the annotations let a client confirm before one runs.
- **Secrets.** `gcp_list_secrets` and `azure_list_secrets` return names only. `get_secret_value` (AWS) returns the value.
- **`run_local_aws_cmd`** runs the `aws` CLI with the emulator endpoint and test credentials, but a command can pass its own `--endpoint-url`. Treat it as full CLI access.
- **`proxy_http_request`** sends a request to any URL from the machine running the server.
- **Hybrid tools** (`seed_from_cloud_dynamodb`, `proxy_cloud_sqs_to_local`) can use real AWS credentials. They are in the `hybrid` toolset, off at the start, but an agent can enable it with `enable_toolset` unless you cap it with `FLOCI_TOOLSETS_ALLOWED`.
- **The marketplace** starts containers on your Docker, and `teardown_marketplace_app` removes their volumes.
- **Tool definitions are text the model obeys.** A server that changes a description after you approved it can steer the agent (a "rug pull"). `list_toolsets` returns `definitions_sha256`, a digest of every registered name, description and schema: record it and compare after an update. Skills are instructions too; read a `SKILL.md` before installing one from anywhere.

## Verify

```bash
uv run python verify_all.py                 # every tool, protocol, toolsets, skills, error paths, runtimes down
VERIFY_DOCKER=1 uv run python verify_all.py marketplace   # also deploy, promote and remove a real container
uv run python verify_all.py skills toolsets # only the groups whose name matches
uv run python verify_mcp.py                 # handshake and tool listing
uv run python verify_clouds.py              # live round trip against Azure, GCP and OCI
uv run --with pytest python -m pytest tests # unit tests
claude plugin validate . --strict           # the Claude Code plugin and marketplace manifests
```

`verify_all.py` needs Floci on `:4566`; Azure, GCP and OCI groups run when their runtimes answer. It fails when a tool is neither exercised nor skipped with a written reason, when a description is not in English, when a skill names a tool that does not exist or states the wrong toolsets, when the plugin manifest drifts from the server, and when the server cannot find its recipes from another working directory.

## Plugins

A plugin is a directory `plugins/<name>/` with a `plugin.json` and a `tools.py` exposing `register(mcp)`. See `plugins/example_hello`.

## License

MIT
