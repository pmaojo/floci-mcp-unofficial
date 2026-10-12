"""Toolsets, read-only mode and tool annotations.

A client sends every tool definition to the model on every conversation, so a
server that exposes everything pays for tools nobody uses (about 16K tokens for
all of them). Tools are grouped into toolsets and only the enabled ones are
registered.

    FLOCI_TOOLSETS=core,storage     # comma separated names, or "all"
    FLOCI_READ_ONLY=1               # drop every tool that changes state
"""
import hashlib
import json
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


def parse_allowed(raw: str | None) -> tuple[str, ...]:
    """FLOCI_TOOLSETS_ALLOWED: the toolsets an agent may enable at runtime.

    Unset means every toolset: the agent decides. Set it to a list to cap what it can
    reach, or to an empty value to forbid switching altogether.
    """
    if raw is None:
        return tuple(TOOLSETS)
    if not raw.strip():
        return ()
    return parse_selection(raw)


def read_only_enabled() -> bool:
    return os.environ.get("FLOCI_READ_ONLY", "").strip().lower() in ("1", "true", "yes", "on")


def register_selected(mcp: FastMCP, selection: tuple[str, ...]) -> None:
    for toolset in selection:
        for module_name in TOOLSETS[toolset]:
            MODULES[module_name].register(mcp)


class DynamicToolsets:
    """Enables and disables toolsets while the server runs.

    By default an agent may enable any toolset. FLOCI_TOOLSETS_ALLOWED caps that for
    whoever wants a restriction to hold against the agent.
    """

    def __init__(self, mcp: FastMCP, selection: tuple[str, ...], allowed: tuple[str, ...], read_only: bool):
        self.mcp = mcp
        self.enabled = list(selection)
        self.allowed = allowed
        self.read_only = read_only
        self._tools: dict[str, list[str]] = {}

    def _names(self) -> set[str]:
        return {t.name for t in self.mcp._tool_manager.list_tools()}

    def _register(self, toolset: str) -> list[str]:
        before = self._names()
        register_selected(self.mcp, (toolset,))
        added = sorted(self._names() - before)
        finalize_names(self.mcp, added, self.read_only)
        return [n for n in added if n in self._names()]

    def check(self, toolset: str) -> str | None:
        toolset = toolset.strip().lower()
        if toolset not in TOOLSETS:
            return f"Unknown toolset {toolset!r}. Available: {', '.join(TOOLSETS)}."
        if toolset not in self.allowed:
            return (
                f"Toolset {toolset!r} is not allowed to be enabled at runtime: this server was started "
                f"with FLOCI_TOOLSETS_ALLOWED={','.join(self.allowed)}. The user can change that and restart it."
            )
        return None

    def enable(self, toolset: str) -> list[str]:
        toolset = toolset.strip().lower()
        if toolset in self.enabled:
            return []
        added = self._register(toolset)
        self.enabled.append(toolset)
        self._tools[toolset] = added
        return added

    def disable(self, toolset: str) -> list[str]:
        toolset = toolset.strip().lower()
        if toolset not in self.enabled:
            return []
        removed = []
        for name in self._tools.get(toolset, []):
            try:
                self.mcp.remove_tool(name)
                removed.append(name)
            except Exception:  # noqa: BLE001
                pass
        self.enabled.remove(toolset)
        self._tools.pop(toolset, None)
        return removed


def finalize(mcp: FastMCP, read_only: bool) -> None:
    """Annotates every registered tool and, in read-only mode, removes the writers."""
    for tool in list(mcp._tool_manager.list_tools()):
        if read_only and is_write(tool.name):
            mcp.remove_tool(tool.name)
            continue
        tool.annotations = annotations_for(tool.name)


def finalize_names(mcp: FastMCP, names: list[str], read_only: bool) -> None:
    """Annotates the given tools and, in read-only mode, removes the writers among them."""
    for tool in list(mcp._tool_manager.list_tools()):
        if tool.name not in names:
            continue
        if read_only and is_write(tool.name):
            mcp.remove_tool(tool.name)
            continue
        tool.annotations = annotations_for(tool.name)


def register_dynamic_tools(mcp: FastMCP, dynamic: DynamicToolsets) -> None:
    """enable_toolset and disable_toolset. Only registered when something may be enabled."""
    from mcp.server.fastmcp import Context
    from mcp.server.lowlevel.server import NotificationOptions

    # Clients only listen for list_changed when the server advertises it.
    original = mcp._mcp_server.create_initialization_options

    def with_list_changed(notification_options=None, experimental_capabilities=None, **kwargs):
        return original(
            notification_options=NotificationOptions(tools_changed=True),
            experimental_capabilities=experimental_capabilities,
            **kwargs,
        )

    mcp._mcp_server.create_initialization_options = with_list_changed

    @mcp.tool()
    async def enable_toolset(name: str, ctx: Context) -> dict:
        """
        Enables a toolset for this session so its tools appear without restarting the server.

        Call it when a task needs tools that are not registered, then use the new tools. Call
        list_toolsets to see what exists and what is enabled. Disable what you no longer need.
        """
        problem = dynamic.check(name)
        if problem:
            return {"enabled": False, "reason": problem, "allowed": list(dynamic.allowed)}
        added = dynamic.enable(name)
        await ctx.session.send_tool_list_changed()
        return {"enabled": True, "toolset": name.strip().lower(), "tools_added": added, "enabled_toolsets": list(dynamic.enabled)}

    @mcp.tool()
    async def disable_toolset(name: str, ctx: Context) -> dict:
        """Disables a toolset enabled earlier, removing its tools from this session to save context."""
        problem = dynamic.check(name)
        if problem:
            return {"disabled": False, "reason": problem, "allowed": list(dynamic.allowed)}
        removed = dynamic.disable(name)
        await ctx.session.send_tool_list_changed()
        return {"disabled": True, "toolset": name.strip().lower(), "tools_removed": removed, "enabled_toolsets": list(dynamic.enabled)}


def register_toolset_info(mcp: FastMCP, selection: tuple[str, ...], read_only: bool, dynamic: "DynamicToolsets | None" = None) -> None:
    @mcp.tool()
    async def list_toolsets() -> dict:
        """
        Lists the toolsets of this server and which ones are enabled.

        Tools outside the enabled toolsets are not registered. Enable more with the
        FLOCI_TOOLSETS environment variable (comma separated, or "all") and restart the server.
        definitions_sha256 is a digest of every registered tool definition: pin it to notice
        when names, descriptions or schemas change between versions.
        """
        tools = await mcp.list_tools()
        return {
            "enabled": list(dynamic.enabled) if dynamic else list(selection),
            "allowed_at_runtime": list(dynamic.allowed) if dynamic else [],
            "read_only": read_only,
            "tools": len(tools),
            "definitions_sha256": definitions_digest(tools),
            "available": {
                toolset: {"modules": list(modules), "enabled": toolset in (dynamic.enabled if dynamic else selection)}
                for toolset, modules in TOOLSETS.items()
            },
            "how_to_enable": (
                "Call enable_toolset with one of allowed_at_runtime."
                if dynamic and dynamic.allowed
                else "Set FLOCI_TOOLSETS=core,storage,... (or all) and restart the server."
            ),
        }


async def tool_index() -> dict[str, dict]:
    """Maps every built-in tool name to its module and toolset."""
    index: dict[str, dict] = {}
    for module_name, module in MODULES.items():
        server = FastMCP(module_name)
        module.register(server)
        for tool in await server.list_tools():
            index[tool.name] = {"module": module_name, "toolset": toolset_of(module_name)}
    # Always registered, whatever the selection.
    for always in ("list_toolsets", "enable_toolset", "disable_toolset"):
        index[always] = {"module": "toolsets", "toolset": None}
    return index


def definitions_digest(tools) -> str:
    """SHA-256 over the sorted name, description and schema of each tool."""
    canonical = sorted(
        (t.name, t.description or "", json.dumps(t.inputSchema, sort_keys=True)) for t in tools
    )
    return hashlib.sha256(json.dumps(canonical).encode()).hexdigest()
