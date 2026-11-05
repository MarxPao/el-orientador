"""Grok (xAI, OpenAI-compatible) next to Gemini: same contract, different wire format. No network."""
import json
import os
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.llm_gateway import LLMGateway  # noqa: E402
from app.pipeline.llm_client import GeminiClient, LLMError, OpenAICompatClient, build_client  # noqa: E402

SCHEMA = {"type": "object", "properties": {"resumo": {"type": "string"}}, "required": ["resumo"]}


class Recorder:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, url, headers, body):
        self.calls.append((url, headers, json.loads(body)))
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def ok(obj):
    return json.dumps({"choices": [{"message": {"content": json.dumps(obj)}}]})


def make(replies, **kw):
    t = Recorder(replies)
    return OpenAICompatClient(api_key="xai-secret", transport=t, sleep=lambda s: None, **kw), t


def test_request_shape_for_grok():
    c, t = make([ok({"resumo": "oi"})], model="grok-test")
    assert c.complete_json("Sistema", "Usuário", SCHEMA) == {"resumo": "oi"}
    url, headers, body = t.calls[0]
    assert url == "https://api.x.ai/v1/chat/completions"
    assert headers["Authorization"] == "Bearer xai-secret"
    assert body["model"] == "grok-test" and body["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"] and body["messages"][1]["content"] == "Usuário"


def test_schema_violation_and_bad_json_are_retried_then_fail():
    c, t = make([ok({"outro": 1}), json.dumps({"choices": [{"message": {"content": "não é json"}}]}), ok({"resumo": "certo"})])
    assert c.complete_json("s", "u", SCHEMA) == {"resumo": "certo"} and len(t.calls) == 3
    c, t = make([ok({"x": 1})] * 3)
    with pytest.raises(LLMError):
        c.complete_json("s", "u", SCHEMA)


def test_http_errors_retry_only_when_transient():
    err = lambda code: urllib.error.HTTPError("u", code, "m", {}, None)  # noqa: E731
    c, t = make([err(429), ok({"resumo": "depois"})])
    assert c.complete_json("s", "u", SCHEMA) == {"resumo": "depois"} and len(t.calls) == 2
    c, t = make([err(401), ok({"resumo": "nunca"})])
    with pytest.raises(LLMError):
        c.complete_json("s", "u", SCHEMA)
    assert len(t.calls) == 1  # bad key: not retried


def test_no_embeddings_so_gateway_reports_no_semantic_capability():
    c, _ = make([])
    gw = LLMGateway(c)
    assert gw.can_embed is False and gw.embed_model is None


def test_gemini_still_embeds():
    g = GeminiClient(api_key="k", transport=Recorder([]))
    assert LLMGateway(g).can_embed is True


def test_missing_key_is_an_explicit_error(monkeypatch):
    for v in ("LLM_API_KEY", "XAI_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(LLMError):
        OpenAICompatClient()


@pytest.mark.parametrize("provider,expected", [("gemini", GeminiClient), ("grok", OpenAICompatClient),
                                                ("xai", OpenAICompatClient), ("GROK", OpenAICompatClient)])
def test_factory_picks_provider(monkeypatch, provider, expected):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("LLM_API_KEY", "k")
    assert type(build_client()) is expected


def test_factory_without_key_or_with_unknown_provider(monkeypatch):
    for v in ("LLM_API_KEY", "XAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "grok")
    assert build_client() is None
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert build_client() is None
    monkeypatch.setenv("LLM_PROVIDER", "skynet")
    monkeypatch.setenv("LLM_API_KEY", "k")
    with pytest.raises(LLMError):
        build_client()


def test_xai_key_alias_and_model_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "grok")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("XAI_API_KEY", "xk")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    c = build_client()
    assert c.api_key == "xk" and c.model == "grok-4"


def test_empty_env_values_fall_back_to_defaults(monkeypatch):
    """docker-compose passes unset variables as empty strings: that must mean "use the default"."""
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_MODEL", "")
    g = GeminiClient(api_key="k", transport=Recorder([]))
    assert g.base_url.startswith("https://generativelanguage") and g.model == "gemini-2.0-flash"
    c, _ = make([])
    assert c.base_url == "https://api.x.ai/v1" and c.model == "grok-4"
