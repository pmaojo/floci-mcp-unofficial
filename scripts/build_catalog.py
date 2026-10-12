"""Builds docs/catalog.json and docs/catalog.js for the landing page.

The tool list comes from the server itself, one module at a time so every tool
keeps the module it belongs to; the recipes come from recipes/*/recipe.json.

    uv run python scripts/build_catalog.py
"""
import asyncio
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mcp.server.fastmcp import FastMCP  # noqa: E402

import toolsets  # noqa: E402
from toolsets import MODULES, is_write, toolset_of  # noqa: E402

def cloud_of(name: str) -> str:
    for prefix in ("gcp_", "azure_", "oci_"):
        if name.startswith(prefix):
            return prefix[:-1]
    return "aws"


def first_paragraph(text: str) -> str:
    lines = [line.strip() for line in (text or "").strip().splitlines()]
    paragraph: list[str] = []
    for line in lines:
        if not line:
            if paragraph:
                break
            continue
        paragraph.append(line)
    return " ".join(paragraph)


async def collect_tools() -> list[dict]:
    result = []
    for group, module in MODULES.items():
        server = FastMCP(group)
        module.register(server)
        for tool in await server.list_tools():
            schema = tool.inputSchema or {}
            required = set(schema.get("required", []))
            params = [
                {
                    "name": name,
                    "type": spec.get("type") or "any",
                    "required": name in required,
                    **({"default": spec["default"]} if "default" in spec else {}),
                }
                for name, spec in schema.get("properties", {}).items()
            ]
            result.append({
                "name": tool.name,
                "group": group,
                "cloud": cloud_of(tool.name),
                "writes": is_write(tool.name),
                "toolset": toolset_of(group),
                "description": first_paragraph(tool.description),
                "params": params,
            })
    return result


def collect_recipes() -> list[dict]:
    recipes = []
    directory = os.path.join(ROOT, "recipes")
    for entry in sorted(os.listdir(directory)):
        path = os.path.join(directory, entry, "recipe.json")
        if not os.path.isfile(path):
            continue
        with open(path) as handle:
            data = json.load(handle)
        recipes.append({
            "id": data.get("id", entry),
            "name": data.get("name", entry),
            "description": data.get("description", ""),
            "version": data.get("version", ""),
            "accessUrl": data.get("accessUrl", ""),
            "aws": data.get("aws"),
            "variables": [
                {
                    "key": v.get("key"),
                    "label": v.get("label", v.get("key")),
                    "type": v.get("type", "string"),
                    "default": "" if v.get("type") == "password" else v.get("default"),
                    "description": v.get("description", ""),
                }
                for v in data.get("variables", [])
            ],
        })
    return recipes


async def main() -> None:
    tools = await collect_tools()
    recipes = collect_recipes()
    catalog = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": "https://github.com/pmaojo/floci-mcp-unofficial",
        "counts": {"tools": len(tools), "recipes": len(recipes)},
        "toolsets": {name: list(modules) for name, modules in toolsets.TOOLSETS.items()},
        "defaultToolsets": list(toolsets.DEFAULT_TOOLSETS),
        "tools": tools,
        "recipes": recipes,
    }
    out = os.path.join(ROOT, "docs")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "catalog.json"), "w") as handle:
        json.dump(catalog, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    with open(os.path.join(out, "catalog.js"), "w") as handle:
        handle.write("window.FLOCI_CATALOG = " + json.dumps(catalog, ensure_ascii=False) + ";\n")
    print(f"{len(tools)} tools, {len(recipes)} recipes")


asyncio.run(main())
