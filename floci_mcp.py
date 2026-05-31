"""
Floci MCP Server — punto de entrada.

Los tools están organizados por servicio AWS en mcp/tools/:
  meta.py        — health, arquitectura, inventario
  lambda_.py     — funciones serverless
  sqs.py         — colas de mensajes
  sns.py         — notificaciones y pub/sub
  s3.py          — object storage
  dynamodb.py    — base de datos NoSQL
  secrets.py     — Secrets Manager
  kms.py         — cifrado de claves
  eventbridge.py — eventos y reglas
  stepfunctions.py — orquestación de flujos
  athena.py      — consultas SQL analíticas
  ses.py         — envío de emails
  marketplace.py — recetas Docker locales
  devtools.py    — IaC, seed data, proxy, JWT, tests
  observability.py — DLQ, flight recorder (time-travel), grafo de servicios
  iac.py         — detección de drift y auto-descubrimiento de IaC
  hybrid.py      — cloud proxying, seeding desde la nube, túneles inversos
  extensibility.py — lifecycle webhooks, interceptores HTTP, plugins

Los plugins de comunidad en mcp/plugins/<nombre>/tools.py se cargan al final.
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
]:
    module.register(mcp)


def _load_community_plugins(mcp_instance) -> None:
    """Descubre y carga tools de plugins de comunidad en mcp/plugins/<nombre>/tools.py."""
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
            print(f"[floci] No se pudo cargar el plugin '{entry}': {exc}")


_load_community_plugins(mcp)

if __name__ == "__main__":
    mcp.run()
