"""Where embeddings come from. Local by default: nothing leaves the machine and no internet is needed.

  EMBED_PROVIDER=local   (default) a model that runs on this computer (fastembed / ONNX)
  EMBED_PROVIDER=gemini  the LLM client's embedding endpoint (needs a key and internet)
  EMBED_PROVIDER=none    keyword search only

A project is searched with ONE model at a time: vectors are stored with the model that made them, the query is
embedded with the active model and only vectors of that model are compared. Changing the provider or the model
therefore never mixes spaces; `POST /library/reindex` embeds the library again with the new one.

The local model is downloaded once (FASTEMBED_CACHE_PATH; the Docker image bakes it in at build time).
"""
from __future__ import annotations

import logging
import math
import os
import threading
from typing import Any

from .llm_gateway import LLMUnavailable

log = logging.getLogger("orientador.embeddings")

DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 384 dims, ~0.2 GB; fits 8 GB machines (e5-large: better, ~2.2 GB, ~2 GB RAM per process)
LOCAL_BATCH = 16


def provider() -> str:
    return os.environ.get("EMBED_PROVIDER", "local").strip().lower()


def local_model_name() -> str:
    return os.environ.get("LOCAL_EMBED_MODEL", DEFAULT_LOCAL_MODEL)


def _fastembed_installed() -> bool:
    try:
        import fastembed  # noqa: F401
    except ImportError:
        return False
    return True


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else v


class LocalEmbedder:
    """Runs an ONNX sentence-embedding model on the CPU. The model loads on first use, once per process."""

    def __init__(self, model: str | None = None) -> None:
        self.name = model or local_model_name()
        self.embed_model = f"local:{self.name}"
        self._model: Any = None
        self._lock = threading.Lock()

    @property
    def can_embed(self) -> bool:
        return True

    def _load(self):
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding

                log.info("loading local embedding model %s", self.name)
                self._model = TextEmbedding(model_name=self.name, cache_dir=os.environ.get("FASTEMBED_CACHE_PATH"))
        return self._model

    def _prefix(self, task: str) -> str:
        # E5 models were trained with these prefixes; without them retrieval quality drops noticeably
        if "e5" in self.name.lower():
            return "query: " if task == "query" else "passage: "
        return ""

    def embed(self, texts: list[str], task: str = "document", operation: str = "embed") -> list[list[float]]:
        if not texts:
            return []
        try:
            model = self._load()
            pre = self._prefix(task)
            with self._lock:  # one inference at a time per process: ONNX sessions are fast but not worth racing
                vectors = [v.tolist() for v in model.embed([pre + t for t in texts], batch_size=LOCAL_BATCH)]
        except Exception as exc:
            log.warning("local embed failed op=%s error=%s", operation, type(exc).__name__)
            raise LLMUnavailable(f"Falha ao gerar embeddings locais ({type(exc).__name__}).") from exc
        return [_normalize(v) for v in vectors]


_local: LocalEmbedder | None = None
_local_key: str | None = None


def resolve(client: Any = None) -> Any | None:
    """The object that embeds for the active provider (has `can_embed`, `embed_model`, `embed`), or None."""
    global _local, _local_key
    p = provider()
    if p == "gemini":
        if client is None:
            return None
        flag = getattr(client, "can_embed", None)  # LLMGateway reports it (and honours its circuit breaker)
        ok = bool(flag) if flag is not None else callable(getattr(client, "embed", None))
        return client if ok else None
    if p == "local" and _fastembed_installed():
        if _local is None or _local_key != local_model_name():
            _local, _local_key = LocalEmbedder(), local_model_name()
        return _local
    return None


def describe(client: Any = None) -> dict:
    """What the UI/capabilities report about semantic search."""
    emb = resolve(client)
    return {"provider": provider(), "model": getattr(emb, "embed_model", None), "available": emb is not None}
