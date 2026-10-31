"""Stage 2 glue: filter LLM claims through deterministic quote verification."""
from __future__ import annotations

from .schemas import ExtractionOutput, VerifiedClaim
from .verify_quotes import verify_quote


def verify_extraction(output: ExtractionOutput, pages: list[str]) -> tuple[list[VerifiedClaim], list[VerifiedClaim]]:
    """Return (accepted, rejected). Only accepted claims may be persisted."""
    accepted: list[VerifiedClaim] = []
    rejected: list[VerifiedClaim] = []
    for c in output.claims:
        r = verify_quote(c.quote, pages, expected_page=c.page)
        vc = VerifiedClaim(
            **c.model_dump(),
            quote_verified=r.found,
            verify_method=r.method,
            page_verified=r.page,
            char_start=r.start,
            char_end=r.end,
        )
        (accepted if r.found else rejected).append(vc)
    return accepted, rejected
