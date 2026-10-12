---
name: floci-marketplace
description: Browse the Docker recipe catalog and start, inspect or remove local stacks such as PostgreSQL, Redis, Kafka, Keycloak or Ollama. Use when the user wants a local database, broker or tool running next to the emulator.
argument-hint: "[status | deploy <id> [KEY=value ...] | teardown <id> | logs <id>]"
---

# Floci marketplace

Manage the recipes in `recipes/` through the marketplace tools.

**Toolsets needed:** `marketplace` (not enabled by default) and Docker reachable from the server. If `list_marketplace_recipes` is missing, tell the user to add `marketplace` to `FLOCI_TOOLSETS` and restart.

## Actions

Read the first word of `$ARGUMENTS`.

- **none**: call `list_marketplace_recipes` and `get_marketplace_installations`; show name, what it is, and which are running.
- **`status`**: call `get_marketplace_installations` (states: IDLE, INSTALLING, RUNNING, UNINSTALLING, FAILED).
- **`deploy <id> [KEY=value ...]`**:
  1. Call `list_marketplace_recipes` and read the variables of that recipe.
  2. Ask for any variable that has no default and was not given. Do not invent passwords.
  3. Call `deploy_marketplace_app`. Starting a container changes the user's Docker: say what will start before doing it if the user did not ask for it by name.
  4. Poll `get_marketplace_installations` until `RUNNING` or `FAILED`, then report the access URL and port. On `FAILED` call `get_marketplace_logs`.
- **`teardown <id>`**: call `teardown_marketplace_app`. It removes containers **and volumes**; confirm first if the recipe holds data.
- **`logs <id>`**: call `get_marketplace_logs` and show the last 50 lines in a code block.

## Moving on

For the same recipe across `test` and `demo` environments use the `deploy_to_environment` and `promote_recipe` tools (`marketplace` toolset).
