---
name: floci-explore
description: Survey everything running in the local Floci environment (health, AWS services with resources, network topology, estimated cost) and report it as one scannable table. Use when the user asks what is running, what exists, or whether the local cloud is healthy.
argument-hint: "[service key to focus on, e.g. s3]"
---

# Floci explore

Survey the local Floci environment through the floci MCP server and report one summary.

**Toolsets needed:** `core` (enabled by default). Run `list_toolsets` if a tool below is missing.

## Steps

1. Call `list_clouds`. Note which runtimes answer (aws, azure, gcp, oci).
2. Call `check_floci_health`. If the backend or the AWS emulator is down, stop and say so clearly.
3. Call `list_aws_services` to see which services have resources.
4. For each service with resources (or only `$ARGUMENTS` if given), call `get_service_resources` with its service key.
5. Call `get_network_topology` for the Docker networks and exposed ports.
6. Optionally call `get_cost_forecast` for the monthly estimate on real AWS.

## Output

One markdown report:

- **Runtimes**: a line per cloud with `✓` online or `✗` unreachable.
- **Services**: table of service, resource count, key resources (names or IDs).
- **Topology**: the connections found.
- **Summary**: two or three sentences on what is running, what is empty, anything odd.

Report only what the tools returned. If a service has no resources, say it is empty; do not invent examples.
