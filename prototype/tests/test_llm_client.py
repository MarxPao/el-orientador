import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from llm_client import GeminiClient, LLMError  # noqa: E402

SCHEMA = {"type": "object", "required": ["claims"], "properties": {"claims": {"type": "array"}}}


def envelope(text: str) -> str:
    return json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]})


class Fake:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, url, headers, body):
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def client(fake):
    return GeminiClient(api_key="k", transport=fake, sleep=lambda s: None)


def http_error(code):
    return urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(b""))


def test_returns_validated_json():
    fake = Fake(envelope('{"claims": []}'))
    assert client(fake).complete_json("s", "u", SCHEMA) == {"claims": []}
    assert fake.calls == 1


def test_retries_invalid_json_then_succeeds():
    fake = Fake(envelope("not json"), envelope('{"wrong": 1}'), envelope('{"claims": [1]}'))
    assert client(fake).complete_json("s", "u", SCHEMA) == {"claims": [1]}
    assert fake.calls == 3  # first attempt + 2 retries


def test_fails_clearly_after_two_retries():
    fake = Fake(envelope("x"), envelope("y"), envelope("z"))
    with pytest.raises(LLMError, match="3 tentativas"):
        client(fake).complete_json("s", "u", SCHEMA)
    assert fake.calls == 3


def test_retries_on_429_but_not_on_401():
    fake = Fake(http_error(429), envelope('{"claims": []}'))
    assert client(fake).complete_json("s", "u", SCHEMA) == {"claims": []}
    fake = Fake(http_error(401))
    with pytest.raises(LLMError, match="401"):
        client(fake).complete_json("s", "u", SCHEMA)
    assert fake.calls == 1


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        GeminiClient()
