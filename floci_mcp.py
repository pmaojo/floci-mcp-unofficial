"""
Floci MCP Server — entry point.

Tools are organized by service under tools/ and grouped into toolsets (see toolsets.py).
FLOCI_TOOLSETS picks the toolsets that are registered; FLOCI_READ_ONLY=1 drops the writers.

Modules:
  meta.py        — health, architecture, inventory
  clouds.py      — Azure, GCP and OCI runtimes (Floci-AZ, Floci-GCP, Floci-OCI)
  lambda_.py     — serverless functions
  sqs.py         — message queues
  sns.py         — notifications and pub/sub
  s3.py          — object storage
  dynamodb.py    — NoSQL database
  secrets.py     — Secrets Manager
  kms.py         — key encryption
  eventbridge.py — events and rules
  stepfunctions.py — workflow orchestration
  athena.py      — analytical SQL queries
  ses.py         — email sending
  marketplace.py — local Docker recipes
  devtools.py    — IaC, seed data, proxy, JWT, tests
  observability.py — DLQ, flight recorder (time-travel), service graph
  iac.py         — drift detection and IaC auto-discovery
  hybrid.py      — cloud proxying, cloud seeding, reverse tunnels
  extensibility.py — lifecycle webhooks, HTTP interceptors, plugins
  tags.py        — gestión de tags en todos los recursos AWS
  pipeline.py    — test/demo/production pipeline, Copilot manifests
"""
import importlib.util
import os

from mcp.server.fastmcp import FastMCP

import toolsets

mcp = FastMCP("floci-mcp")

SELECTION = toolsets.parse_selection(os.environ.get("FLOCI_TOOLSETS"))
ALLOWED = toolsets.parse_allowed(os.environ.get("FLOCI_TOOLSETS_ALLOWED"))
READ_ONLY = toolsets.read_only_enabled()
toolsets.register_selected(mcp, SELECTION)
DYNAMIC = toolsets.DynamicToolsets(mcp, SELECTION, ALLOWED, READ_ONLY)
toolsets.register_toolset_info(mcp, SELECTION, READ_ONLY, DYNAMIC)
if ALLOWED:
    toolsets.register_dynamic_tools(mcp, DYNAMIC)

import decider  # noqa: E402

DECIDER = decider.load_config()
if DECIDER:
    decider.register_decider_tool(mcp, DECIDER, DYNAMIC)


def _load_community_plugins(mcp_instance) -> None:
    """Discover and load community plugin tools from mcp/plugins/<name>/tools.py."""
    plugins_dir = os.environ.get("FLOCI_PLUGINS_DIR") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "plugins"
    )
    if not os.path.isdir(plugins_dir):
        return
    for entry in sorted(os.listdir(plugins_dir)):
        tools_path = os.path.join(plugins_dir, entry, "tools.py")
        if not os.path.isfile(tools_path):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"floci_plugin_{entry}", tools_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "register"):
                module.register(mcp_instance)
        except Exception as exc:  # noqa: BLE001
            print(f"[floci] Could not load plugin '{entry}': {exc}")


_load_community_plugins(mcp)
toolsets.finalize(mcp, READ_ONLY)

def main() -> None:
    """Console entry point (`floci-mcp`, `uvx floci-mcp`): serve over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
