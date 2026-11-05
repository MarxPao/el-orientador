"""Local error log: unexpected exceptions go to the `error_events` table, never to a third-party service.

`record()` never raises (logging an error must not create another one) and scrubs what it stores: connection
strings, bearer tokens and key=value secrets are masked, and long messages and stacks are truncated.
"""
from __future__ import annotations

import logging
import os
import re
import traceback

log = logging.getLogger("orientador.errors")

MAX_MESSAGE = 500
MAX_STACK = 8000
DEFAULT_RETENTION_DAYS = 30

_SCRUBS = [
    (re.compile(r"(\w+://[^:/\s@]+):[^@\s]+@"), r"\1:***@"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1***"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password|authorization)(\s*[=:]\s*)[^\s,;'\"]+"), r"\1\2***"),
]


def scrub(text: str) -> str:
    for pat, rep in _SCRUBS:
        text = pat.sub(rep, text)
    return text


def retention_days() -> int:
    try:
        return max(1, int(os.environ.get("ERROR_RETENTION_DAYS", DEFAULT_RETENTION_DAYS)))
    except ValueError:
        return DEFAULT_RETENTION_DAYS


def record(repo, source: str, exc: BaseException, route: str | None = None, request_id: str | None = None,
           user_id: str | None = None) -> dict | None:
    try:
        stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        return repo.add_error_event(
            source, type(exc).__name__, scrub(str(exc))[:MAX_MESSAGE], scrub(stack)[-MAX_STACK:], route,
            request_id, user_id,
        )
    except Exception as inner:  # the log itself is down: fall back to the process log, never fail the caller
        log.error("could not record error %s: %s", type(exc).__name__, type(inner).__name__)
        return None


def purge_old(repo) -> int:
    try:
        return repo.purge_error_events(retention_days())
    except Exception:
        return 0


def admin_emails() -> set[str]:
    return {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
