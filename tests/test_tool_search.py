"""search_tools: retrieval over the whole catalogue, offline."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tool_search  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def test_catalog_covers_unregistered_toolsets():
    toolsets_seen = {e["toolset"] for e in run(tool_search.catalog())}
    assert {"storage", "messaging", "hybrid", "ops"} <= toolsets_seen


def test_finds_the_tool_and_ranks_its_toolset_first():
    entries = run(tool_search.catalog())
    found = tool_search.rank(entries, "list my S3 buckets", 5)
    assert found["tools"][0]["tool"] == "list_s3_buckets"
    assert found["toolsets"][0]["toolset"] == "storage"
    assert found["toolsets"][0]["score"] == 1.0


def test_nothing_matches_gibberish():
    assert tool_search.rank(run(tool_search.catalog()), "zzqx", 5)["tools"] == []


def test_first_sentence_is_one_line():
    assert tool_search.first_sentence("Lists things.\n  More text.") == "Lists things."
