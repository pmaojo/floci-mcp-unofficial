"""Plugin SDK — discovery of community adapters (Area 6).

A Floci plugin is a directory inside ``mcp/plugins/<name>/`` with:

    plugin.json   manifest: {name, version, description, author, tools: [...]}
    tools.py      Python module exposing ``def register(mcp): ...``

The backend exposes the catalog of discovered plugins; the MCP server loads their
tools at startup (see mcp/floci_mcp.py). This lets the community add adapters for
less-common services without touching the Floci core.
"""
import json
import os
from typing import Any, Dict, List


def _default_plugins_dir() -> str:
    # mcp/floci_backend/application/plugin_registry.py -> mcp/plugins
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "plugins"))


class PluginRegistry:
    def __init__(self, plugins_dir: str | None = None):
        self.plugins_dir = plugins_dir or os.environ.get("FLOCI_PLUGINS_DIR") or _default_plugins_dir()

    def discover(self) -> List[Dict[str, Any]]:
        plugins: List[Dict[str, Any]] = []
        if not os.path.isdir(self.plugins_dir):
            return plugins
        for entry in sorted(os.listdir(self.plugins_dir)):
            plugin_path = os.path.join(self.plugins_dir, entry)
            manifest_path = os.path.join(plugin_path, "plugin.json")
            if not os.path.isfile(manifest_path):
                continue
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                plugins.append({"id": entry, "valid": False, "error": str(e)})
                continue
            manifest["id"] = entry
            manifest["valid"] = True
            manifest["hasTools"] = os.path.isfile(os.path.join(plugin_path, "tools.py"))
            manifest["path"] = plugin_path
            plugins.append(manifest)
        return plugins

    def list_plugins(self) -> Dict[str, Any]:
        plugins = self.discover()
        return {"pluginsDir": self.plugins_dir, "plugins": plugins, "count": len(plugins)}
