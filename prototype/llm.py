"""Provider-agnostic LLM interface. Implement one concrete client (TODO) behind this."""
from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, schema: dict, temperature: float = 0.1) -> dict:
        """Return a dict that validates against `schema`. Implementations must not repair JSON with regex."""
        ...
