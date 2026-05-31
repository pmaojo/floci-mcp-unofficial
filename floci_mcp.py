"""
Floci MCP Server — entry point.

Tools are organized by AWS service under mcp/tools/:
  meta.py        — health, architecture, inventory
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
"""
import importlib.util
import os

from mcp.server.fastmcp import FastMCP
from tools import (
    athena,
    devtools,
    dynamodb,
    eventbridge,
    extensibility,
    hybrid,
    iac,
    kms,
    lambda_,
    marketplace,
    meta,
    observability,
    s3,
    secrets,
    ses,
    sns,
    sqs,
    stepfunctions,
    tags,
)

mcp = FastMCP("floci-mcp")

for module in [
    meta,
    lambda_,
    sqs,
    sns,
    s3,
    dynamodb,
    secrets,
    kms,
    eventbridge,
    stepfunctions,
    athena,
    ses,
    marketplace,
    devtools,
    observability,
    iac,
    hybrid,
    extensibility,
    tags,
]:
    module.register(mcp)


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

if __name__ == "__main__":
    mcp.run()
