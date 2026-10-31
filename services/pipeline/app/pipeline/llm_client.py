"""T0.4 - Concrete LLMClient (Gemini REST API, stdlib only).

Config via environment:
  LLM_API_KEY   (required; GEMINI_API_KEY also accepted)
  LLM_MODEL     (default: gemini-2.0-flash)
  LLM_BASE_URL  (default: https://generativelanguage.googleapis.com/v1beta)

Privacy: prompts and responses are never logged; errors carry only status/reason.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Callable

import jsonschema

DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MAX_RETRIES = 2  # retries after the first attempt (3 attempts total)

# transport(url, headers, body) -> response text; raises urllib.error.HTTPError on HTTP errors
Transport = Callable[[str, dict, bytes], str]


class LLMError(RuntimeError):
    """Raised when the LLM call fails after all retries."""


def _urllib_transport(url: str, headers: dict, body: bytes) -> str:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8")


class GeminiClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise LLMError("Chave de API ausente: defina a variável de ambiente LLM_API_KEY.")
        self.model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self._transport = transport or _urllib_transport
        self._sleep = sleep

    def _request_once(self, system: str, user: str, temperature: float) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
        }
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        raw = self._transport(url, headers, json.dumps(body).encode("utf-8"))
        data = json.loads(raw)
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def complete_json(self, system: str, user: str, schema: dict, temperature: float = 0.1) -> dict:
        """Return a dict validated against `schema`. No regex JSON repair: invalid output is retried."""
        last = "desconhecido"
        for attempt in range(MAX_RETRIES + 1):
            try:
                text = self._request_once(system, user, temperature)
                result = json.loads(text)
                jsonschema.validate(result, schema)
                return result
            except urllib.error.HTTPError as exc:
                last = f"HTTP {exc.code}"
                if exc.code not in (408, 429, 500, 502, 503, 504):
                    raise LLMError(f"Falha na chamada ao LLM ({last}); não será repetida.") from None
            except urllib.error.URLError as exc:
                last = f"erro de rede ({exc.reason})"
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                last = "resposta não é JSON válido ou veio em formato inesperado"
            except jsonschema.ValidationError as exc:
                last = f"JSON não segue o schema ({exc.message[:120]})"
            if attempt < MAX_RETRIES:
                self._sleep(2**attempt)
        raise LLMError(f"LLM falhou após {MAX_RETRIES + 1} tentativas: {last}.")
