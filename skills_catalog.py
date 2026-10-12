"""Reads skills/*/SKILL.md: frontmatter, the tools a skill calls and the toolsets it needs."""
import os
import re

import toolsets

ROOT = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(ROOT, "skills")
TOOLSET_LINE = re.compile(r"\*\*Toolsets needed:\*\*(.*)")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not match:
        return {}, text
    meta: dict = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        if key.strip():
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, match.group(2)


async def load_skills() -> list[dict]:
    index = await toolsets.tool_index()
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills
    for entry in sorted(os.listdir(SKILLS_DIR)):
        path = os.path.join(SKILLS_DIR, entry, "SKILL.md")
        if not os.path.isfile(path):
            continue
        with open(path) as handle:
            text = handle.read()
        meta, body = parse_frontmatter(text)
        backticked = set(re.findall(r"`([a-z0-9_]+)`", body))
        tools = sorted(t for t in backticked if t in index)
        requires = sorted({index[t]["toolset"] for t in tools if index[t]["toolset"]}, key=list(toolsets.TOOLSETS).index)
        stated_line = TOOLSET_LINE.search(body)
        stated = sorted(set(re.findall(r"`([a-z]+)`", stated_line.group(1))) & set(toolsets.TOOLSETS)) if stated_line else []
        skills.append({
            "dir": entry,
            "name": meta.get("name", ""),
            "description": meta.get("description", ""),
            "argumentHint": meta.get("argument-hint", ""),
            "tools": tools,
            "requires": requires,
            "statedToolsets": stated,
            "enabledByDefault": all(t in toolsets.DEFAULT_TOOLSETS for t in requires),
            "candidates": sorted(c for c in backticked if c not in index),
            "path": f"skills/{entry}/SKILL.md",
        })
    return skills
