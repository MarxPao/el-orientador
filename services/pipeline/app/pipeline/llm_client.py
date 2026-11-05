"""T0.4 - Concrete LLMClient (Gemini REST API, stdlib only).

Config via environment:
  LLM_API_KEY   (required; GEMINI_API_KEY also accepted)
  LLM_MODEL     (default: gemini-2.0-flash)
  LLM_BASE_URL  (default: https://generativelanguage.googleapis.com/v1beta)
  EMBED_MODEL   (default: gemini-embedding-001)   EMBED_DIM (default: 768)

Also here: OpenAICompatClient, for providers that speak the OpenAI "chat completions" protocol. Grok (xAI) is the
first one (LLM_PROVIDER=grok). It has no embedding endpoint here: semantic search then uses the local model.

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
DEFAULT_EMBED_MODEL = "gemini-embedding-001"
DEFAULT_EMBED_DIM = 768
EMBED_BATCH = 50
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
        self.model = model or os.environ.get("LLM_MODEL") or DEFAULT_MODEL
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._transport = transport or _urllib_transport
        self._sleep = sleep
        self.embed_model = os.environ.get("EMBED_MODEL", DEFAULT_EMBED_MODEL)
        self.embed_dim = int(os.environ.get("EMBED_DIM", DEFAULT_EMBED_DIM))

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

    # ------------------------------------------------------------------ embeddings
    def _embed_batch(self, texts: list[str], task: str) -> list[list[float]]:
        task_type = "RETRIEVAL_QUERY" if task == "query" else "RETRIEVAL_DOCUMENT"
        body = {
            "requests": [
                {
                    "model": f"models/{self.embed_model}",
                    "content": {"parts": [{"text": t}]},
                    "taskType": task_type,
                    "outputDimensionality": self.embed_dim,
                }
                for t in texts
            ]
        }
        url = f"{self.base_url}/models/{self.embed_model}:batchEmbedContents"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        data = json.loads(self._transport(url, headers, json.dumps(body).encode("utf-8")))
        vectors = [e["values"] for e in data["embeddings"]]
        if len(vectors) != len(texts) or any(len(v) != self.embed_dim for v in vectors):
            raise ValueError("embedding response has the wrong shape")
        out = []
        for v in vectors:  # truncated (Matryoshka) vectors are not unit length: normalise so cosine == dot
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / norm for x in v])
        return out

    def embed(self, texts: list[str], task: str = "document") -> list[list[float]]:
        """One unit-length vector per text. Retries transient errors like complete_json; never logs text."""
        result: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH):
            batch = texts[i : i + EMBED_BATCH]
            last = "desconhecido"
            for attempt in range(MAX_RETRIES + 1):
                try:
                    result.extend(self._embed_batch(batch, task))
                    break
                except urllib.error.HTTPError as exc:
                    last = f"HTTP {exc.code}"
                    if exc.code not in (408, 429, 500, 502, 503, 504):
                        raise LLMError(f"Falha ao gerar embeddings ({last}); não será repetida.") from None
                except urllib.error.URLError as exc:
                    last = f"erro de rede ({exc.reason})"
                except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
                    last = "resposta de embeddings em formato inesperado"
                if attempt < MAX_RETRIES:
                    self._sleep(2**attempt)
            else:
                raise LLMError(f"Embeddings falharam após {MAX_RETRIES + 1} tentativas: {last}.")
        return result


# --------------------------------------------------------------------------------------------- OpenAI-compatible
DEFAULT_GROK_MODEL = "grok-4"
DEFAULT_GROK_BASE_URL = "https://api.x.ai/v1"


class OpenAICompatClient(GeminiClient):
    """JSON completions through `POST {base_url}/chat/completions` (Grok / xAI and other compatible services).

    Reuses the retry and validation loop of GeminiClient; only the request and the response shape differ. It does
    not offer embeddings (`embed` is None), so the gateway reports can_embed=False and search uses the local model.
    """

    embed = None  # type: ignore[assignment]
    embed_model = None  # type: ignore[assignment]

    def __init__(self, api_key: str | None = None, model: str | None = None, base_url: str | None = None,
                 transport: Transport | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("XAI_API_KEY")
        if not key:
            raise LLMError("Chave de API ausente: defina LLM_API_KEY (ou XAI_API_KEY).")
        self.api_key = key
        self.model = model or os.environ.get("LLM_MODEL") or DEFAULT_GROK_MODEL
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL") or DEFAULT_GROK_BASE_URL).rstrip("/")
        self._transport = transport or _urllib_transport
        self._sleep = sleep

    def _request_once(self, system: str, user: str, temperature: float) -> str:
        body = {
            "model": self.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system + "\n\nResponda somente com um objeto JSON válido."},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        raw = self._transport(f"{self.base_url}/chat/completions", headers, json.dumps(body).encode("utf-8"))
        return json.loads(raw)["choices"][0]["message"]["content"]


def provider_name() -> str:
    return os.environ.get("LLM_PROVIDER", "gemini").strip().lower()


def build_client() -> "GeminiClient | None":
    """The configured LLM client, or None when no key is set. LLM_PROVIDER: gemini (default) | grok (aliases:
    xai, openai). Model and base URL stay configurable (LLM_MODEL, LLM_BASE_URL)."""
    p = provider_name()
    if p in ("grok", "xai", "openai"):
        if not (os.environ.get("LLM_API_KEY") or os.environ.get("XAI_API_KEY")):
            return None
        return OpenAICompatClient()
    if p != "gemini":
        raise LLMError(f"LLM_PROVIDER desconhecido: {p!r} (use gemini ou grok).")
    if not (os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        return None
    return GeminiClient()
