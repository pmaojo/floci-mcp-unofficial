"""Retrieval over the whole tool catalogue, so an agent finds a tool without loading them all.

Two papers argue the same thing for servers with many tools. RAG-MCP (arXiv 2505.03275) retrieves the few
relevant tool definitions instead of putting all of them in the prompt. MCP-Zero (arXiv 2506.01056) has the
agent ask for what it needs and routes hierarchically: first the server, then the tool inside it. Here the
"server" is a toolset. `search_tools` ranks the toolsets, then the tools of the best ones, over every
toolset including those that are not registered, and with `apply=true` enables the toolsets it found.

The index is BM25 over name, description and parameter names. It runs offline, with no model and no key.
"""
import re

from mcp.server.fastmcp import Context, FastMCP

import toolsets
from floci_generic.domain.search import BM25, expand, stem, tokens

# A toolset is scored by its best tool plus a small share of the next ones, so one exact hit
# is enough but a toolset full of partial hits still beats a lone weak match.
RUNNER_UP_SHARE = 0.25
MAX_TOOLSETS_APPLIED = 2

_CATALOG: list[dict] | None = None


def first_sentence(text: str) -> str:
    """The opening sentence of a tool description, on one line."""
    flat = " ".join((text or "").split())
    match = re.match(r"(.+?[.!?])(\s|$)", flat)
    return (match.group(1) if match else flat)[:200]


async def catalog() -> list[dict]:
    """Every built-in tool with the toolset it belongs to. Built once: the definitions do not change while running."""
    global _CATALOG
    if _CATALOG is not None:
        return _CATALOG
    entries = []
    for module_name, module in toolsets.MODULES.items():
        toolset = toolsets.toolset_of(module_name)
        if toolset is None:
            continue
        server = FastMCP(module_name)
        module.register(server)
        for tool in await server.list_tools():
            params = list((tool.inputSchema.get("properties") or {}).keys())
            summary = first_sentence(tool.description or "")
            words = tool.name.split("_")
            # The name counts triple and the whole description is indexed (the first sentence alone lost hits): the name is the part written to be matched.
            text = f"{toolset} {' '.join(words * 3)} {tool.description or ''} {' '.join(params)}"
            entries.append({
                "tool": tool.name, "toolset": toolset, "summary": summary,
                "name_tokens": [stem(w) for w in words], "tokens": tokens(text),
            })
    _CATALOG = entries
    return entries


def _tool_boost(entry: dict, wanted: set[str]) -> float:
    """Name coverage: 'list my buckets' should prefer list_s3_buckets to a tool that merely mentions buckets."""
    words = entry["name_tokens"]
    return 0.5 + 0.5 * (sum(w in wanted for w in words) / max(len(words), 1))


def rank(entries: list[dict], query: str, limit: int) -> dict:
    """The best tools, and the toolsets they point to. Pure: no I/O."""
    expanded = expand(query)
    wanted = set(expanded)
    bm25 = BM25([e["tokens"] for e in entries])
    scored = [
        (score * _tool_boost(e, wanted), e) for score, e in zip(bm25.scores(expanded), entries)
    ]
    scored = [(s, e) for s, e in scored if s > 0]
    by_toolset: dict[str, list[tuple[float, dict]]] = {}
    for score, entry in sorted(scored, key=lambda pair: -pair[0]):
        by_toolset.setdefault(entry["toolset"], []).append((score, entry))
    toolset_scores = {
        name: hits[0][0] + RUNNER_UP_SHARE * sum(s for s, _ in hits[1:3]) for name, hits in by_toolset.items()
    }
    ranked_toolsets = sorted(toolset_scores, key=lambda name: -toolset_scores[name])
    top = max(toolset_scores.values(), default=0.0)
    # Tools are ranked across all toolsets: cutting them to the best toolsets lost hits in the eval.
    # The toolset ranking decides what apply=true enables.
    tools = [entry for _, entry in sorted(scored, key=lambda pair: -pair[0])[:limit]]
    return {
        "toolsets": [{"toolset": n, "score": round(toolset_scores[n] / top, 2)} for n in ranked_toolsets[:3]],
        "tools": tools,
    }


def register(mcp: FastMCP, dynamic: toolsets.DynamicToolsets) -> None:
    """search_tools. Registered next to enable_toolset, only when something may be enabled."""

    @mcp.tool()
    async def search_tools(query: str, ctx: Context, limit: int = 5, apply: bool = False) -> dict:
        """
        Finds which tool does a job, across every toolset, including those that are not enabled.

        Describe the task in plain words ("copy a file into a bucket", "replay failed messages").
        It returns the best tools with their toolset and whether it is enabled, ranked toolset first.
        With apply=true the toolsets of the best hits that are not enabled get enabled, so the tools
        appear without a restart. Prefer this to enabling toolsets by guesswork.
        """
        limit = max(1, min(limit, 10))
        found = rank(await catalog(), query, limit)
        enabled = set(dynamic.enabled)
        results = [
            {"tool": e["tool"], "toolset": e["toolset"], "enabled": e["toolset"] in enabled, "summary": e["summary"]}
            for e in found["tools"]
        ]
        out = {"query": query, "toolsets": found["toolsets"], "results": results}
        if not results:
            out["hint"] = "Nothing matched. Try other words, or call list_toolsets."
            return out
        if apply:
            applied, refused = [], {}
            for item in found["toolsets"][:MAX_TOOLSETS_APPLIED]:
                name = item["toolset"]
                if name in enabled:
                    continue
                problem = dynamic.check(name)
                if problem:
                    refused[name] = problem
                    continue
                dynamic.enable(name)
                applied.append(name)
            if applied:
                await ctx.session.send_tool_list_changed()
            out.update({"enabled_now": applied, "refused": refused, "enabled_toolsets": list(dynamic.enabled)})
        return out
