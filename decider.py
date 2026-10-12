"""Optional decision-model router: which toolsets does a task need?

A decision model (TypeSafe Jev, Inception Mercury Decide) answers typed questions
about a piece of state and returns calibrated probabilities instead of text. Here
the state is the user's task and there is one yes/no question per toolset. It is
off unless FLOCI_DECIDER is set, and it never needs to be on: toolsets work without it.

    FLOCI_DECIDER=openrouter-jev          # or openrouter-mercury, zenmux-jev, digitalocean-jev, custom
    OPENROUTER_API_KEY=...                # the preset names which variable holds its key
    FLOCI_DECIDER_URL / _MODEL / _API_KEY # override a preset, or define "custom"
    FLOCI_DECIDER_MIN_CONFIDENCE=0.5      # a toolset is recommended at or above this probability

The request is the System One shape: {model, state, questions}, each question typed
"noul" (yes/no, answered with a probability), "choice" or "score".
"""
import os
from dataclasses import dataclass

import httpx

import toolsets

PRESETS = {
    # The OpenRouter Decisions API is an alpha path; the model id is the family alias.
    "openrouter-jev": {"url": "https://openrouter.ai/api/alpha/decisions", "model": "~typesafe/jev-latest", "key_env": "OPENROUTER_API_KEY"},
    # Mercury Decide on the same endpoint. The id comes from its OpenRouter model page and has not been tried here.
    "openrouter-mercury": {"url": "https://openrouter.ai/api/alpha/decisions", "model": "inception/mercury-decide", "key_env": "OPENROUTER_API_KEY"},
    "zenmux-jev": {"url": "https://zenmux.ai/api/v1/systemone", "model": "typesafe/jev-latest", "key_env": "ZENMUX_API_KEY"},
    "digitalocean-jev": {"url": "https://inference.do-ai.run/v1/systemone", "model": "typesafe-jev-1.13.0", "key_env": "MODEL_ACCESS_KEY"},
}


class DeciderError(Exception):
    """The decision model is not configured, or answered with an error."""


@dataclass
class DeciderConfig:
    preset: str
    url: str
    model: str
    api_key: str
    min_confidence: float


def load_config(env: dict[str, str] | None = None) -> DeciderConfig | None:
    """Reads the FLOCI_DECIDER* variables. None means the router is off."""
    env = env if env is not None else dict(os.environ)
    preset = (env.get("FLOCI_DECIDER") or "").strip().lower()
    if not preset:
        return None
    if preset != "custom" and preset not in PRESETS:
        raise DeciderError(f"FLOCI_DECIDER: unknown preset {preset!r}. Available: {', '.join(PRESETS)}, custom.")
    base = PRESETS.get(preset, {"url": "", "model": "", "key_env": ""})
    url = env.get("FLOCI_DECIDER_URL") or base["url"]
    model = env.get("FLOCI_DECIDER_MODEL") or base["model"]
    key = env.get("FLOCI_DECIDER_API_KEY") or (env.get(base["key_env"], "") if base["key_env"] else "")
    if not url or not model:
        raise DeciderError("FLOCI_DECIDER=custom needs FLOCI_DECIDER_URL and FLOCI_DECIDER_MODEL.")
    try:
        threshold = float(env.get("FLOCI_DECIDER_MIN_CONFIDENCE", "0.5"))
    except ValueError as error:
        raise DeciderError("FLOCI_DECIDER_MIN_CONFIDENCE must be a number between 0 and 1.") from error
    return DeciderConfig(preset, url, model, key, threshold)


def build_request(config: DeciderConfig, task: str, candidates: dict[str, str]) -> dict:
    """One yes/no question per candidate toolset, keyed by the toolset name."""
    return {
        "model": config.model,
        "state": task,
        "questions": {
            name: {
                "type": "noul",
                "instructions": f"Does completing this task require the '{name}' toolset? It provides: {description}",
            }
            for name, description in candidates.items()
        },
    }


def parse_answers(body: dict, names: list[str]) -> dict[str, float]:
    answers = body.get("answers")
    if not isinstance(answers, dict):
        raise DeciderError(f"The decision model returned no answers: {str(body)[:200]}")
    probabilities: dict[str, float] = {}
    for name in names:
        answer = answers.get(name)
        if not isinstance(answer, dict) or not isinstance(answer.get("noul"), (int, float)):
            raise DeciderError(f"The decision model gave no yes/no answer for {name!r}.")
        probabilities[name] = float(answer["noul"])
    return probabilities


async def decide(
    config: DeciderConfig,
    task: str,
    candidates: dict[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """Returns every toolset ranked by the probability that the task needs it."""
    if not config.api_key:
        raise DeciderError(
            f"No API key for FLOCI_DECIDER={config.preset}. Set FLOCI_DECIDER_API_KEY"
            + (f" or {PRESETS[config.preset]['key_env']}." if config.preset in PRESETS else ".")
        )
    candidates = candidates or toolsets.DESCRIPTIONS
    payload = build_request(config, task, candidates)
    try:
        async with httpx.AsyncClient(timeout=60, transport=transport) as client:
            response = await client.post(
                config.url,
                headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.HTTPError as error:
        raise DeciderError(f"Cannot reach the decision model at {config.url}: {error}") from error
    if response.status_code >= 400:
        raise DeciderError(f"The decision model answered HTTP {response.status_code}: {response.text.strip()[:300]}")
    probabilities = parse_answers(response.json(), list(candidates))
    ranked = sorted(probabilities.items(), key=lambda item: -item[1])
    return {
        "model": config.model,
        "ranked": [{"toolset": name, "probability": round(value, 3)} for name, value in ranked],
        "recommended": [name for name, value in ranked if value >= config.min_confidence],
        "min_confidence": config.min_confidence,
        "usage": response.json().get("usage"),
    }


def register_decider_tool(mcp, config: DeciderConfig, dynamic) -> None:
    """suggest_toolsets. Only registered when FLOCI_DECIDER is set."""
    from mcp.server.fastmcp import Context

    @mcp.tool()
    async def suggest_toolsets(task: str, apply: bool = False, ctx: Context = None) -> dict:
        """
        Asks a decision model which toolsets a task needs, and returns each one with a probability.

        Use it when a request spans services and you are unsure which toolsets to switch on.
        With apply=true the recommended toolsets that are not enabled yet are enabled right away.
        """
        try:
            result = await decide(config, task)
        except DeciderError as error:
            return {"suggested": False, "reason": str(error)}
        enabled_now = list(dynamic.enabled)
        result["already_enabled"] = [t for t in result["recommended"] if t in enabled_now]
        to_enable = [t for t in result["recommended"] if t not in enabled_now]
        result["to_enable"] = to_enable
        if apply and to_enable:
            applied, refused = [], {}
            for name in to_enable:
                problem = dynamic.check(name)
                if problem:
                    refused[name] = problem
                    continue
                dynamic.enable(name)
                applied.append(name)
            if applied and ctx is not None:
                await ctx.session.send_tool_list_changed()
            result["applied"] = applied
            result["refused"] = refused
        return result
