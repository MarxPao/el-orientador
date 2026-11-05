"""LLM Gateway: the single entry point for every LLM call in the API.

Responsibilities:
- Wrap any `LLMClient` (GeminiClient already retries transient HTTP/JSON errors internally).
- Circuit breaker: after `failure_threshold` consecutive failures, stop calling the provider for
  `cooldown_seconds` and fail fast with `LLMUnavailable` (no hanging requests during an outage).
- Typed errors: callers never see raw transport exceptions, and never swallow them silently.
- Privacy: logs carry only the operation name, error type and latency, never prompt or response text.

Callers decide what an honest degraded mode looks like (scaffold, mechanical cleanup, or HTTP 503).
"""
from __future__ import annotations

import inspect
import logging
import threading
import time
from typing import Any, Callable

from .pipeline.llm import LLMClient

log = logging.getLogger("orientador.llm")


class LLMUnavailable(RuntimeError):
    """No LLM configured, provider failing, or circuit open. Subclass of RuntimeError so the
    extraction pipeline (which catches RuntimeError per chunk) keeps working unchanged."""


class LLMGateway:
    def __init__(
        self,
        inner: LLMClient,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._open_until = 0.0
        self.model = getattr(inner, "model", "unknown")
        try:
            params = inspect.signature(inner.complete_json).parameters
            self._accepts_temperature = "temperature" in params or any(
                p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
            )
        except (TypeError, ValueError):
            self._accepts_temperature = True

    @property
    def circuit_open(self) -> bool:
        with self._lock:
            return self._clock() < self._open_until

    @property
    def available(self) -> bool:
        return not self.circuit_open

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict,
        temperature: float = 0.1,
        operation: str = "unspecified",
    ) -> dict:
        if self.circuit_open:
            raise LLMUnavailable("Serviço de IA temporariamente indisponível (circuito aberto).")
        started = self._clock()
        try:
            if self._accepts_temperature:
                result = self._inner.complete_json(system, user, schema, temperature=temperature)
            else:  # test doubles may implement the narrower (system, user, schema) signature
                result = self._inner.complete_json(system, user, schema)
        except Exception as exc:
            self._record_failure()
            log.warning(
                "llm call failed op=%s error=%s latency_ms=%d",
                operation,
                type(exc).__name__,
                int((self._clock() - started) * 1000),
            )
            raise LLMUnavailable(f"Falha na chamada de IA ({type(exc).__name__}).") from exc
        self._record_success()
        log.info("llm call ok op=%s latency_ms=%d", operation, int((self._clock() - started) * 1000))
        return result

    @property
    def can_embed(self) -> bool:
        return callable(getattr(self._inner, "embed", None)) and self.available

    @property
    def embed_model(self) -> str | None:
        return getattr(self._inner, "embed_model", None) if callable(getattr(self._inner, "embed", None)) else None

    def embed(self, texts: list[str], task: str = "document", operation: str = "embed") -> list[list[float]]:
        """Embeddings through the same circuit breaker. Raises LLMUnavailable when the provider has no embedding
        model, is failing, or the circuit is open."""
        fn = getattr(self._inner, "embed", None)
        if not callable(fn):
            raise LLMUnavailable("O provedor de IA configurado não oferece embeddings.")
        if self.circuit_open:
            raise LLMUnavailable("Serviço de IA temporariamente indisponível (circuito aberto).")
        started = self._clock()
        try:
            out = fn(texts, task=task)
        except Exception as exc:
            self._record_failure()
            log.warning("embed failed op=%s error=%s latency_ms=%d", operation, type(exc).__name__,
                        int((self._clock() - started) * 1000))
            raise LLMUnavailable(f"Falha ao gerar embeddings ({type(exc).__name__}).") from exc
        self._record_success()
        log.info("embed ok op=%s n=%d latency_ms=%d", operation, len(texts), int((self._clock() - started) * 1000))
        return out

    def _record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._threshold:
                self._open_until = self._clock() + self._cooldown
                self._consecutive_failures = 0
                log.error("llm circuit opened for %.0fs", self._cooldown)

    def _record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0


def wrap(client: LLMClient | None) -> LLMGateway | None:
    if client is None or isinstance(client, LLMGateway):
        return client
    return LLMGateway(client)


def call_json(
    client: Any,
    system: str,
    user: str,
    schema: dict,
    operation: str,
    temperature: float = 0.2,
) -> dict:
    """Call through the gateway when available; raise LLMUnavailable when there is no client."""
    if client is None:
        raise LLMUnavailable("Nenhum provedor de IA configurado.")
    if isinstance(client, LLMGateway):
        return client.complete_json(system, user, schema, temperature, operation=operation)
    try:
        return client.complete_json(system, user, schema)
    except Exception as exc:
        raise LLMUnavailable(f"Falha na chamada de IA ({type(exc).__name__}).") from exc


def text_schema(field: str) -> dict:
    return {
        "type": "object",
        "required": [field],
        "properties": {field: {"type": "string", "minLength": 1}},
    }
