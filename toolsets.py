"""Toolsets, read-only mode and tool annotations.

A client sends every tool definition to the model on every conversation, so a
server that exposes everything pays for tools nobody uses (about 16K tokens for
all of them). Tools are grouped into toolsets and only the enabled ones are
registered.

    FLOCI_TOOLSETS=core,storage     # comma separated names, or "all"
    FLOCI_READ_ONLY=1               # drop every tool that changes state
"""
import os

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from tools import (
    athena, clouds, devtools, dynamodb, eventbridge, extensibility, hybrid, iac, kms, lambda_,
    marketplace, meta, observability, pipeline, s3, secrets, ses, sns, sqs, stepfunctions, tags,
)

MODULES = {
    "meta": meta, "clouds": clouds, "s3": s3, "dynamodb": dynamodb, "secrets": secrets, "kms": kms,
    "sqs": sqs, "sns": sns, "eventbridge": eventbridge, "stepfunctions": stepfunctions, "ses": ses,
    "lambda": lambda_, "athena": athena, "tags": tags, "observability": observability, "iac": iac,
    "marketplace": marketplace, "pipeline": pipeline, "hybrid": hybrid, "devtools": devtools,
    "extensibility": extensibility,
}

TOOLSETS = {
    "core": ("meta", "clouds"),
    "storage": ("s3", "dynamodb", "secrets", "kms"),
    "messaging": ("sqs", "sns", "eventbridge", "stepfunctions", "ses"),
    "compute": ("lambda", "athena"),
    "ops": ("tags", "observability", "iac"),
    "marketplace": ("marketplace", "pipeline"),
    "hybrid": ("hybrid", "devtools", "extensibility"),
}

DEFAULT_TOOLSETS = ("core", "storage", "messaging", "compute")

WRITE_PREFIXES = (
    "create_", "delete_", "put_", "update_", "send_", "publish_", "subscribe_", "unsubscribe_", "purge_",
    "redrive_", "tag_", "untag_", "deploy_", "teardown_", "promote_", "register_", "emit_", "seed_",
    "start_", "stop_", "invoke_", "verify_", "replay_", "capture_", "edit_", "proxy_", "execute_",
)
# Names that change state without a write prefix.
WRITE_NAMES = {"run_local_aws_cmd", "run_athena_query", "run_kms_diagnostic", "run_ui_tests"}
DESTRUCTIVE_PREFIXES = ("delete_", "purge_", "teardown_", "untag_", "stop_", "unsubscribe_", "redrive_")
DESTRUCTIVE_NAMES = {"run_local_aws_cmd", "execute_partiql_dynamodb"}
# Reach beyond the local emulators.
OPEN_WORLD_NAMES = {"proxy_http_request", "seed_from_cloud_dynamodb", "proxy_cloud_sqs_to_local", "start_reverse_tunnel"}


def is_write(name: str) -> bool:
    return name in WRITE_NAMES or name.startswith(WRITE_PREFIXES)


def is_destructive(name: str) -> bool:
    return name in DESTRUCTIVE_NAMES or name.startswith(DESTRUCTIVE_PREFIXES)


def annotations_for(name: str) -> ToolAnnotations:
    write = is_write(name)
    return ToolAnnotations(
        readOnlyHint=not write,
        destructiveHint=is_destructive(name) if write else False,
        openWorldHint=name in OPEN_WORLD_NAMES,
    )


def toolset_of(module_name: str) -> str | None:
    for toolset, modules in TOOLSETS.items():
        if module_name in modules:
            return toolset
    return None


def parse_selection(raw: str | None) -> tuple[str, ...]:
    """Turns FLOCI_TOOLSETS into toolset names; fails fast on an unknown name."""
    if raw is None or not raw.strip():
        return DEFAULT_TOOLSETS
    names = tuple(part.strip().lower() for part in raw.split(",") if part.strip())
    if "all" in names:
        return tuple(TOOLSETS)
    unknown = [name for name in names if name not in TOOLSETS]
    if unknown:
        raise SystemExit(
            f"FLOCI_TOOLSETS: unknown toolset {', '.join(unknown)}. "
            f"Available: {', '.join(TOOLSETS)}, or 'all'."
        )
    return names


def read_only_enabled() -> bool:
    return os.environ.get("FLOCI_READ_ONLY", "").strip().lower() in ("1", "true", "yes", "on")


def register_selected(mcp: FastMCP, selection: tuple[str, ...]) -> None:
    for toolset in selection:
        for module_name in TOOLSETS[toolset]:
            MODULES[module_name].register(mcp)


def finalize(mcp: FastMCP, read_only: bool) -> None:
    """Annotates every registered tool and, in read-only mode, removes the writers."""
    for tool in list(mcp._tool_manager.list_tools()):
        if read_only and is_write(tool.name):
            mcp.remove_tool(tool.name)
            continue
        tool.annotations = annotations_for(tool.name)


def register_toolset_info(mcp: FastMCP, selection: tuple[str, ...], read_only: bool) -> None:
    @mcp.tool()
    async def list_toolsets() -> dict:
        """
        Lists the toolsets of this server and which ones are enabled.

        Tools outside the enabled toolsets are not registered. Enable more with the
        FLOCI_TOOLSETS environment variable (comma separated, or "all") and restart the server.
        """
        return {
            "enabled": list(selection),
            "read_only": read_only,
            "available": {
                toolset: {"modules": list(modules), "enabled": toolset in selection}
                for toolset, modules in TOOLSETS.items()
            },
            "how_to_enable": "Set FLOCI_TOOLSETS=core,storage,... (or all) and restart the server.",
        }
