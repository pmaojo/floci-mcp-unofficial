# floci-mcp-unofficial

[Model Context Protocol](https://modelcontextprotocol.io) server for [Floci](https://floci.io), the open-source local cloud emulator. It lets an AI agent (Claude, Cursor, any MCP client) inspect and provision your local AWS, Azure, GCP and OCI runtimes in natural language.

> **Unofficial community project.** Not affiliated with or endorsed by the Floci project. Floci does the emulation; this server only talks to it. Please support the [upstream project](https://github.com/floci-io/floci). Extracted from [Floci Studio](https://github.com/pmaojo/floci-studio), where it started.

**Site and live catalog of every tool, skill and recipe:** [`docs/index.html`](docs/index.html) (regenerate with `uv run python scripts/build_catalog.py`; the Vercel build does it on every deploy).

> ### Whole cloud, small context
>
> The `generic` toolset (5 tools, about 0.9K tokens) and the `code` toolset (2 tools, about 0.6K) can address every
> operation of AWS, Azure, GCP and OCI, and the Docker recipes, instead of one tool per operation. Reads and writes are
> separate tools, so `FLOCI_READ_ONLY=1` removes the writer. See [Whole-cloud access](#whole-cloud-access-generic-and-code-toolsets).
>
> *Not yet measured against a live model: tokens, classification and offline search are tested; accuracy needs `eval/generic.py model`.*

## Quick start

```bash
git clone https://github.com/pmaojo/floci-mcp-unofficial && cd floci-mcp-unofficial
uv sync
uv run python floci_mcp.py        # stdio; point your MCP client at it (see Install)
```

You need a running Floci (`localhost:4566`). For the smallest context start with `FLOCI_TOOLSETS=generic,core`; the default is still the curated toolsets until the eval says otherwise. Then install the skills below so the agent knows how to use the tools.

**Claude Code, in two commands** (server, skills and settings together):

```
/plugin marketplace add pmaojo/floci-mcp-unofficial
/plugin install floci@floci-mcp-unofficial
```

Claude Code asks for the toolsets, read-only mode and endpoints when you enable it, and the skills appear as `/floci:floci-explore` and so on. See [Use it from other agents](#use-it-from-other-agents) for Codex, DeepSeek-TUI/Codewhale, Cursor and Claude Desktop.

## How it works

```
agent (Claude, Cursor, Codex, ...)
        |  MCP over stdio
        v
floci_mcp.py  -- toolsets decide which tools are registered
        |            generic / code -> one gateway: classifies every call read or write
        |-- boto3 ----------------------------> Floci core        :4566  (AWS)
        |-- REST (per provider) --------------> Floci-AZ          :4577
        |                                       Floci-GCP         :4588
        |                                       Floci-OCI         :4599
        `-- in-process backend (floci_backend)
              |-- aws CLI   (run_local_aws_cmd, Glue catalog, Lambda deploy)
              `-- docker compose (recipes: marketplace, generic cloud="recipes")  --> recipes/
```

The server is a thin layer: it never emulates anything. Tools that can be answered by an SDK call use it; the few that need the `aws` CLI or Docker go through the in-process backend, which is why those two are listed under requirements.

## Skills

Skills are short playbooks an agent loads on demand ([Agent Skills](https://docs.claude.com/en/docs/claude-code/skills): a folder with a `SKILL.md`). Each one names the tools it calls and the [toolsets](#toolsets-and-read-only-mode) it needs, and asks before it writes.

| Skill | Use it to | Toolsets |
|---|---|---|
| [`floci-explore`](skills/floci-explore/SKILL.md) | See what is running: health, services with resources, topology, cost | `core` |
| [`floci-multicloud`](skills/floci-multicloud/SKILL.md) | Line up storage, queues and secrets across AWS, Azure, GCP and OCI | `core`, `storage`, `messaging` |
| [`floci-triage`](skills/floci-triage/SKILL.md) | Find and explain stuck messages in dead-letter queues, then redrive on confirmation | `ops`, `messaging` |
| [`floci-seed`](skills/floci-seed/SKILL.md) | Fill a table, bucket or database with synthetic data | `storage`, `hybrid` |
| [`floci-iac`](skills/floci-iac/SKILL.md) | Export the emulator as Terraform or CDK, and check code for drift | `core`, `ops`, `hybrid` |
| [`floci-marketplace`](skills/floci-marketplace/SKILL.md) | Start, inspect and remove local Docker stacks from the recipe catalog; prefers the Floci-native service when there is one | `generic` or `marketplace`, `pipeline` |
| [`floci-generic`](skills/floci-generic/SKILL.md) | Operate any service of any cloud, and chain calls in code, with a handful of tools | `generic`, `code` |

Install them for Claude Code (personal skills; use `.claude/skills/` inside a project for a per-project install):

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD"/skills/* ~/.claude/skills/      # or: cp -R skills/* ~/.claude/skills/
```

Skills that need a toolset which is not enabled by default tell the agent to ask you to enable it (see below).

## Cookbook

Things to ask the agent, and what it ends up calling. The toolset in brackets is where the tools live; an agent can enable a missing one with `enable_toolset`.

| Ask | It calls | Toolset |
|---|---|---|
| "Is my local cloud up, and what is in it?" | skill `floci-explore`: `list_clouds`, `check_floci_health`, `list_aws_services`, `get_service_resources` | core |
| "Create a queue `orders`, send a test message and read it back." | `create_sqs_queue`, `send_sqs_message`, `receive_sqs_messages`, `delete_sqs_message` | messaging |
| "Make a table `users`, add three items and list the ones older than 21." | `create_dynamodb_table`, `put_dynamodb_item`, `execute_partiql_dynamodb` | storage |
| "Why are my messages stuck?" | skill `floci-triage`: `list_dead_letter_queues`, `inspect_dlq_messages`, `get_sqs_queue_attributes`, then `redrive_dlq` only after you say yes | ops, messaging |
| "Compare my buckets and queues across AWS, Azure, GCP and OCI." | skill `floci-multicloud`: `list_clouds` and each cloud's list tools | core, storage, messaging |
| "Store a secret and encrypt a value with a new key." | `create_secret`, `create_kms_key`, `kms_encrypt` | storage |
| "Run `SELECT 1` on Athena." | `run_athena_query` | compute |
| "Start a local Redis and tell me the port." | `list_marketplace_recipes`, `deploy_marketplace_app`; or with no extra tools, `call_write(cloud="recipes", operation="DeployRecipe")` | marketplace, or generic |
| "Fill `orders` with test data." | skill `floci-seed`: `list_dynamodb_tables`, `seed_mock_data`, `scan_dynamodb` | storage, hybrid |
| "Write the Terraform for what I have running." | skill `floci-iac`: `export_to_terraform`; `detect_iac_drift` to compare with code | hybrid, ops |

## What it covers

| Cloud | Runtime | Default port | Tools |
|---|---|:-:|---|
| AWS | [floci](https://github.com/floci-io/floci) | 4566 | Lambda, SQS, SNS, S3, DynamoDB (incl. PartiQL), Secrets Manager, KMS, EventBridge, Step Functions, Athena, SES, tags, IaC, drift and more, through boto3 |
| Azure | [floci-az](https://github.com/floci-io/floci-az) | 4577 | Blob containers and blobs, queues, Key Vault secret names |
| GCP | [floci-gcp](https://github.com/floci-io/floci-gcp) | 4588 | Cloud Storage buckets and objects, Pub/Sub topics, Secret Manager secret names |
| OCI | [floci-oci](https://github.com/floci-io/floci-oci) | 4599 | Object Storage buckets and objects |

Azure, GCP and OCI are called through each provider's own REST contract, the same one their emulators serve. Start with `list_clouds`: it reports which runtimes answer, so the agent knows which tools can work.

### Coverage

Counted from each emulator's own "Supported Services" list, and from the generic toolset's catalog, which is checked against a running Floci (`scripts/build_rest_catalog.py`):

| Cloud | Services the emulator lists | Curated tools | `generic` / `code` catalog |
|---|:-:|---|---|
| **AWS** (floci) | about 130 | about 14 services | every operation in the boto3 models (~18,000 over ~420 services); `list_services(probe=true)` shows which ones answer |
| **Azure** (floci-az) | 28 | Blob, Queue, Key Vault names | data plane (blob, queue, table, key vault) and **15 ARM resource types** that answer: storage, SQL, Redis, virtual networks, VMs, AKS, Container Apps, ACR, ACI, managed identity, PostgreSQL, MySQL, MariaDB, Email. Service Bus, Event Hubs, Functions, Cosmos DB, API Management, Event Grid, Monitor, Policy, SignalR and App Configuration did not answer on the ARM paths tried |
| **GCP** (floci-gcp) | 26 | Cloud Storage, Pub/Sub, Secret Manager names | **20 APIs, 2,283 operations** generated from Google's discovery documents (Compute, IAM, KMS, BigQuery, Cloud SQL, Firestore, GKE, Cloud Run, Scheduler, Logging...). 70 list operations were verified against Floci; the rest are the provider's contract, not proof that Floci implements them |
| **OCI** (floci-oci) | 8 | Object Storage | all 8: Object Storage, Identity, Queue, Streaming, Vault, Secrets, Functions, OKE, each with list, get, create and delete; every list answers |

The catalog is a map of the provider's API, and `verified_on_floci` in `describe_operation` says whether Floci answered it when the catalog was built. A route that is not catalogued is still reachable with `request={method, path}`. The curated tools stay thin (no object upload or delete, no publish or receive on Azure, GCP and OCI queues, secret tools never return values); the generic toolset is how the rest is reached.

Run the emulators with the `multicloud` profile of the [Floci UI compose file](https://github.com/floci-io/floci-ui/blob/main/docker-compose.yml), or on their own.

## Toolsets and read-only mode

A client sends every tool definition to the model on every conversation. All 142 tools cost about 17K tokens, and models pick worse when many similar tools are visible. So tools are grouped and only some are registered.

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

### Decision-model router (optional)

> **★ `suggest_toolsets`.** One yes/no question per toolset, answered in one call by a decision model (**TypeSafe Jev** or **Mercury Decide**),
> with calibrated probabilities. With `apply=true` the toolsets switch themselves on. It exists for clients that cannot defer tool
> definitions and keep the curated toolsets; with `generic` or `code` there is nothing to route.
>
> *Tested end to end against a fake, not yet against a live provider. Needs an API key. The OpenRouter path is `alpha`.*

A decision model answers typed questions about a piece of state and returns calibrated probabilities instead of text. Here the state is the task and there is one yes/no question per toolset, so one cheap call says which toolsets a request needs. It is off unless you set `FLOCI_DECIDER`; toolsets, `enable_toolset` and the agent's own judgement work without it.

| `FLOCI_DECIDER` | Endpoint | Model | Key from |
|---|---|---|---|
| `openrouter-jev` | `https://openrouter.ai/api/alpha/decisions` | `~typesafe/jev-latest` | `OPENROUTER_API_KEY` |
| `openrouter-mercury` | same | `inception/mercury-decide` | `OPENROUTER_API_KEY` |
| `zenmux-jev` | `https://zenmux.ai/api/v1/systemone` | `typesafe/jev-latest` | `ZENMUX_API_KEY` |
| `digitalocean-jev` | `https://inference.do-ai.run/v1/systemone` | `typesafe-jev-1.13.0` | `MODEL_ACCESS_KEY` |
| `custom` | `FLOCI_DECIDER_URL` | `FLOCI_DECIDER_MODEL` | `FLOCI_DECIDER_API_KEY` |

```bash
FLOCI_DECIDER=openrouter-jev OPENROUTER_API_KEY=... uv run python floci_mcp.py
FLOCI_DECIDER=openrouter-mercury FLOCI_DECIDER_MODEL=inception/mercury-decide:free ...   # the free variant
FLOCI_DECIDER_MIN_CONFIDENCE=0.5     # recommend a toolset at or above this probability (default 0.5)
```

It registers one tool, `suggest_toolsets(task, apply=false)`: it returns every toolset ranked by probability, the recommended ones and which are not enabled yet; with `apply=true` it enables them, within `FLOCI_TOOLSETS_ALLOWED`. Measure it on the same 40 tasks with `uv run python eval/run.py decision`.

What is and is not verified: the request and response shapes follow the System One schema as documented by [ZenMux](https://zenmux.ai/docs/api/typesafe/systemone), [DigitalOcean](https://docs.digitalocean.com/products/inference/how-to/use-system-one-api/index.html.md) and the `pi-decider` package (question type `noul`, options and levels under `criteria`). The server is tested end to end against a fake endpoint, not against a live provider. The OpenRouter path is `alpha`, so it may change, and the Mercury Decide model id is the one on its OpenRouter model page, which has not been tried against that path here. Jev is the one documented on the Decisions API.

### Measuring it

```bash
uv run python eval/run.py static       # tokens per configuration
uv run python eval/run.py retrieval    # does BM25 find the expected tool? (offline)
FLOCI_DECIDER=openrouter-jev OPENROUTER_API_KEY=... uv run python eval/run.py decision
ANTHROPIC_API_KEY=... uv run python eval/run.py model   # real tool selection by a model
```

`eval/tasks.json` holds 40 realistic tasks. The model mode sends only the definitions and the task, reads the first tool call and executes nothing.

## Whole-cloud access: `generic` and `code` toolsets

Two toolsets can address **every** operation of AWS, Azure, GCP and OCI with a handful of tools, instead of one tool per operation. What answers is what Floci emulates; `list_services(probe=true)` shows which AWS services do. Neither depends on the decision model: with 2 to 5 tools there is nothing to route.

| Toolset | Tools | ~Tokens | Use |
|---|---|---|---|
| `generic` | `list_services`, `search_operations`, `describe_operation`, `call_read`, `call_write` | ~0.9K | Look up an operation, read its parameters, call it |
| `code` | `code_read`, `code_write` | ~0.6K | Chain calls and filter large results in Python before they reach the model |

(The 135 curated tools weigh ~15.6K; the default selection ~9.3K.)

- **AWS** is driven by the botocore service models: all ~18,000 operations of ~420 services can be addressed, and new boto3 releases are picked up with no change here. Floci implements a subset of them.
- **Azure, GCP, OCI** have no botocore-style model, so their catalog is generated: GCP from Google's discovery documents (2,283 operations), Azure as the data plane plus the ARM resource types that answer, OCI as list/get/create/delete over its eight services. `describe_operation` reports `verified_on_floci`. `request={method, path, query, json}` (or `rest(...)` in code) reaches any route that is not catalogued.
- **Read and write are separate tools.** `FLOCI_READ_ONLY=1` removes `call_write` and `code_write`. The decision is also enforced inside the gateway, so `code_read` cannot write whatever the code says.
- **Classification is default-deny** (`floci_generic/classify.py`): an operation is a read only when its verb says so and nothing contradicts it. AWS is cross-checked against each operation's HTTP method; the other clouds are classified by HTTP method. `tests/test_generic.py` checks it against every operation of every service model.
- **Secret values** (`GetSecretValue`, SSM parameters) need `FLOCI_ALLOW_SECRET_VALUES=1`.
- **The code sandbox is a guardrail, not isolation.** The child process has the standard library only and an empty environment, and every cloud call goes back through the gateway, but it can still open a socket to localhost. It is meant for local emulators with throwaway credentials, never for a real cloud.

```bash
FLOCI_TOOLSETS=generic,core uv run python floci_mcp.py     # or code, or both
uv run python tests/test_generic.py                          # classification, guard, sandbox, live reads
uv run python eval/generic.py static|oracle|search           # offline
uv run python eval/generic.py model --arms generic,code      # needs ANTHROPIC_API_KEY
```

## Recipes as a kickstarter

`recipes/` holds a catalog of local Docker recipes (PostgreSQL, Redis, MinIO, Keycloak, RabbitMQ, Kafka, Temporal and others, each with a `recipe.json` and a Compose file). They ship with the server and need only Docker.

**They cost no context.** The `generic` and `code` toolsets reach them as one more cloud, `recipes`, with the same five tools:

```
search_operations("start a local redis", cloud="recipes")     -> DeployRecipe
call_read (cloud="recipes", operation="ListRecipes")           -> id, what it is, AWS counterpart, floci_native
call_write(cloud="recipes", operation="DeployRecipe", params={"recipe_id": "redis"})
```

- `ListRecipes` marks `floci_native` when Floci already emulates the AWS service a recipe stands in for (RDS for `postgres`, ElastiCache for `redis`, MSK for `kafka`...). It is checked against the running Floci, so it is never stale. Prefer the native service; use a recipe for what Floci does not emulate (Keycloak, Metabase, n8n, Ollama...).
- `DeployRecipe` waits for `RUNNING` or `FAILED` and returns the access URL. A default port already taken on your machine is moved to a free one and reported (`ports_adjusted`); a port you set that is taken is refused with a suggestion.
- `TeardownRecipe` removes containers **and volumes**. It is a write and flagged destructive.
- Only the server process touches Docker. The code sandbox reaches recipes through the same gateway and its read/write rule.

If you prefer named tools, the `marketplace` toolset has three: `list_marketplace_recipes` (also state and logs), `deploy_marketplace_app` and `teardown_marketplace_app`. `deploy_to_environment` and `promote_recipe` moved to their own `pipeline` toolset.

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

### Without cloning

The package builds as a wheel with the recipes and the route catalogs inside, and installs a `floci-mcp` command. Until it is on PyPI, install straight from the repository:

```bash
uvx --from git+https://github.com/pmaojo/floci-mcp-unofficial floci-mcp
```

```json
{ "mcpServers": { "floci": {
  "command": "uvx",
  "args": ["--from", "git+https://github.com/pmaojo/floci-mcp-unofficial", "floci-mcp"],
  "env": { "FLOCI_TOOLSETS": "generic,core" }
} } }
```

The wheel was built and run from a clean environment outside the checkout. The `git+` form needs this branch to be on the default branch of the remote.

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
| `FLOCI_DECIDER` | off (`openrouter-jev`, `openrouter-mercury`, `zenmux-jev`, `digitalocean-jev`, `custom`) |
| `FLOCI_DECIDER_URL`, `FLOCI_DECIDER_MODEL`, `FLOCI_DECIDER_API_KEY` | the preset's, or required for `custom` |
| `FLOCI_DECIDER_MIN_CONFIDENCE` | `0.5` |
| `OPENROUTER_API_KEY`, `ZENMUX_API_KEY`, `MODEL_ACCESS_KEY` | the key a decider preset reads |
| `FLOCI_PLUGINS_DIR` | `plugins/` next to the server |
| `SIDECAR_STATE_DIR` | `~/.floci-mcp` |
| `FLOCI_RECIPES_DIR` | `recipes/` next to the server |

The endpoint and project variables match [Floci UI](https://github.com/floci-io/floci-ui), so one `.env` serves both. The server writes its state (webhooks, captured events, a topology file) under `SIDECAR_STATE_DIR`.

## Troubleshooting

The messages below are the ones the server returns.

| You see | Why | Do |
|---|---|---|
| `Could not connect to the endpoint URL: "http://localhost:4566/"` | Floci core is not running, or `AWS_ENDPOINT_URL` points elsewhere | Start Floci; call `list_clouds` to see what answers |
| `Cannot reach the gcp runtime at http://localhost:4588: All connection attempts failed` (or `azure`, `oci`) | That emulator is not running | Start it, for example with the `multicloud` profile of the Floci UI compose file |
| `list_clouds` shows `unreachable` | Same, one entry per runtime | Same |
| `The aws CLI is not on PATH. Install it from https://aws.amazon.com/cli/` | `run_local_aws_cmd`, the Glue catalog and Lambda deployment shell out to `aws` | Install the CLI, or use the Docker image, which includes it |
| An installation ends `FAILED` with `'docker' was not found on PATH` | The marketplace runs `docker compose` | Install Docker with Compose, or mount the socket into the image |
| The tool you want is not in the list | Its toolset is not registered | `list_toolsets`, then `enable_toolset`; or set `FLOCI_TOOLSETS` and restart |
| `Toolset 'x' is not allowed to be enabled at runtime` | The server was started with `FLOCI_TOOLSETS_ALLOWED` | Change that variable and restart |
| `FLOCI_TOOLSETS: unknown toolset ...` at startup | A typo in the toolset list | The message lists the valid names |
| `Statement wasn't well formed` on PartiQL | More than one statement in a call | One statement per `execute_partiql_dynamodb` |
| The first Athena query takes several seconds | Floci starts its DuckDB container on first use | Wait; later queries are fast |
| From Docker on Linux the emulators are unreachable | `host.docker.internal` is not defined there | `--add-host=host.docker.internal:host-gateway` |

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

## Contributing

Adding a tool is a short checklist, and `verify_all.py` fails if a step is missed:

1. Write it in the right `floci_tools/<module>.py`, with a description in English that says what it does, its parameters and when to use it. Models and tool search match on that text.
2. Make sure the module belongs to a toolset in `toolsets.py`. If the name changes state, `is_write` must see it (a known prefix, or add it to `WRITE_NAMES`) so read-only mode and the annotations are right.
3. Exercise it in `verify_all.py`, or give it a reason in `SKIPPED`. The coverage check fails otherwise.
4. Run `uv run python scripts/build_catalog.py` so the site lists it.

A skill is a folder `skills/<name>/SKILL.md` with `name` and `description` frontmatter, a `**Toolsets needed:**` line and the steps. The `skills` group of `verify_all.py` checks that the tools it names exist and that the stated toolsets are the right ones.

## License

MIT
