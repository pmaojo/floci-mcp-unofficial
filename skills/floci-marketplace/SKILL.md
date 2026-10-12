---
name: floci-marketplace
description: Browse the Docker recipe catalog and start, inspect or remove local stacks such as PostgreSQL, Redis, Kafka, Keycloak or Ollama. Use when the user wants a local database, broker or tool running next to the emulator.
argument-hint: "[status | deploy <id> [KEY=value ...] | teardown <id> | logs <id>]"
---

# Floci marketplace

Manage the recipes in `recipes/`. They are Docker Compose stacks, so Docker must be reachable from the server.

**Toolsets needed:** `generic` or `marketplace`, and `pipeline` only for promoting between environments (none is enabled by default).

**How to reach them (use the first that exists):**

1. `generic` or `code` toolset: `call_read` / `call_write` with `cloud="recipes"`. Operations: `ListRecipes`, `GetRecipe`, `GetStatus`, `GetLogs`, `DeployRecipe`, `TeardownRecipe`. Use `search_operations(cloud="recipes")` if unsure.
2. `marketplace` toolset: `list_marketplace_recipes` (with `recipe_id`, `status`, `logs`), `deploy_marketplace_app`, `teardown_marketplace_app`.

If neither is available, tell the user to add `generic` (or `marketplace`) to `FLOCI_TOOLSETS`, or call `enable_toolset` when that tool exists.

## Floci first

Many recipes stand in for an AWS service that Floci may already emulate. `ListRecipes` marks those `floci_native`. Before deploying one, say so and offer the native route:

| Recipe | Floci service | Use the recipe when |
|---|---|---|
| `postgres`, `mysql` | RDS | you need a plain engine on a fixed port, or an extension Floci's RDS lacks |
| `redis` | ElastiCache | same |
| `kafka`, `redpanda` | MSK | you need the real broker tooling |
| `minio` | S3 | you need the MinIO console or its API |
| `mailpit` | SES | you want to read the mail in a web UI |

For recipes without `floci_native` (Keycloak, Metabase, n8n, Ollama, Jaeger, Loki...) deploying the recipe is the way.

## Actions

Read the first word of `$ARGUMENTS`.

- **none**: `ListRecipes` and `GetStatus`; show name, what it is, floci_native, and which are running.
- **`status`**: `GetStatus` (IDLE, INSTALLING, RUNNING, UNINSTALLING, FAILED), with the access URL of the running ones.
- **`deploy <id> [KEY=value ...]`**:
  1. `GetRecipe` and read its variables. Ask for any variable with no default that was not given. Do not invent passwords.
  2. If the recipe is `floci_native`, mention it once and continue only if the user wants the recipe.
  3. Starting a container changes the user's Docker: say what will start unless they named it.
  4. `DeployRecipe`. It waits for `RUNNING` or `FAILED` and returns `access_url`. Report the URL and any `ports_adjusted` (the default port was taken, so a free one was used). On `FAILED` show `log_tail`.
- **`teardown <id>`**: `TeardownRecipe`. It removes containers **and volumes**; confirm first if the recipe holds data.
- **`logs <id>`**: `GetLogs` and show the lines in a code block.

## Moving on

For the same recipe across `test` and `demo` use `deploy_to_environment` and `promote_recipe` (`pipeline` toolset).
