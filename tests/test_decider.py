"""The decision-model router, against a fake endpoint. No network, no key."""
import asyncio
import json
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import decider  # noqa: E402
import toolsets  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def fake(probabilities, status=200, capture=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture["request"] = request
            capture["body"] = json.loads(request.content)
        if status != 200:
            return httpx.Response(status, text="nope")
        answers = {name: {"type": "noul", "noul": value} for name, value in probabilities.items()}
        return httpx.Response(200, json={"model": "m", "answers": answers, "usage": {"input_tokens": 10, "output_tokens": 2}})
    return httpx.MockTransport(handler)


def cfg(**env):
    return decider.load_config({"FLOCI_DECIDER": "openrouter-jev", "OPENROUTER_API_KEY": "k", **env})


def test_off_by_default():
    assert decider.load_config({}) is None
    assert decider.load_config({"FLOCI_DECIDER": ""}) is None


def test_presets_cover_jev_and_mercury():
    jev = decider.load_config({"FLOCI_DECIDER": "openrouter-jev", "OPENROUTER_API_KEY": "k"})
    mercury = decider.load_config({"FLOCI_DECIDER": "openrouter-mercury", "OPENROUTER_API_KEY": "k"})
    assert jev.model == "~typesafe/jev-latest" and "jev" in jev.model
    assert mercury.model == "inception/mercury-decide"
    assert jev.url == mercury.url == "https://openrouter.ai/api/alpha/decisions"
    assert decider.load_config({"FLOCI_DECIDER": "zenmux-jev"}).url.endswith("/v1/systemone")
    assert decider.load_config({"FLOCI_DECIDER": "digitalocean-jev"}).model == "typesafe-jev-1.13.0"


def test_overrides_and_custom():
    config = decider.load_config({"FLOCI_DECIDER": "openrouter-jev", "FLOCI_DECIDER_MODEL": "inception/mercury-decide:free",
                                  "FLOCI_DECIDER_API_KEY": "x", "FLOCI_DECIDER_MIN_CONFIDENCE": "0.7"})
    assert config.model == "inception/mercury-decide:free" and config.api_key == "x" and config.min_confidence == 0.7
    custom = decider.load_config({"FLOCI_DECIDER": "custom", "FLOCI_DECIDER_URL": "http://h/v1/systemone", "FLOCI_DECIDER_MODEL": "m"})
    assert custom.url == "http://h/v1/systemone"


def test_bad_configuration_is_explained():
    for env, needle in [({"FLOCI_DECIDER": "nope"}, "unknown preset"),
                        ({"FLOCI_DECIDER": "custom"}, "FLOCI_DECIDER_URL"),
                        ({"FLOCI_DECIDER": "openrouter-jev", "FLOCI_DECIDER_MIN_CONFIDENCE": "high"}, "number")]:
        try:
            decider.load_config(env)
        except decider.DeciderError as error:
            assert needle in str(error), str(error)
        else:
            raise AssertionError(f"expected an error for {env}")


def test_request_is_one_yes_no_question_per_toolset():
    seen = {}
    run(decider.decide(cfg(), "make a queue", transport=fake({t: 0.1 for t in toolsets.TOOLSETS}, capture=seen)))
    body = seen["body"]
    assert body["model"] == "~typesafe/jev-latest" and body["state"] == "make a queue"
    assert set(body["questions"]) == set(toolsets.TOOLSETS)
    assert all(q["type"] == "noul" and q["instructions"] for q in body["questions"].values())
    assert seen["request"].headers["authorization"] == "Bearer k"
    assert str(seen["request"].url) == "https://openrouter.ai/api/alpha/decisions"


def test_ranks_and_applies_the_threshold():
    probabilities = {t: 0.05 for t in toolsets.TOOLSETS}
    probabilities.update({"messaging": 0.93, "ops": 0.55, "storage": 0.49})
    result = run(decider.decide(cfg(), "why are my messages stuck", transport=fake(probabilities)))
    assert [r["toolset"] for r in result["ranked"][:3]] == ["messaging", "ops", "storage"]
    assert result["recommended"] == ["messaging", "ops"]
    stricter = run(decider.decide(cfg(FLOCI_DECIDER_MIN_CONFIDENCE="0.9"), "x", transport=fake(probabilities)))
    assert stricter["recommended"] == ["messaging"]


def test_errors_are_readable():
    keyless = decider.load_config({"FLOCI_DECIDER": "openrouter-jev"})
    for config, transport, needle in [
        (keyless, fake({}), "OPENROUTER_API_KEY"),
        (cfg(), fake({}, status=429), "HTTP 429"),
    ]:
        try:
            run(decider.decide(config, "x", transport=transport))
        except decider.DeciderError as error:
            assert needle in str(error), str(error)
        else:
            raise AssertionError("expected an error")
    incomplete = httpx.MockTransport(lambda r: httpx.Response(200, json={"answers": {"core": {"type": "noul", "noul": 0.5}}}))
    try:
        run(decider.decide(cfg(), "x", transport=incomplete))
    except decider.DeciderError as error:
        assert "no yes/no answer" in str(error)
    else:
        raise AssertionError("expected an error for a missing answer")
