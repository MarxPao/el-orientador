"""Contract and Signature Verification for compute_project_authorship.

Guarantees that compute_project_authorship strictly adheres to the signature expected
across the application and immediately catches incompatible caller attempts (e.g. passing repo, project_id).
"""
import inspect
from typing import Any
import pytest

from services.pipeline.app.authorship import compute_project_authorship


def test_compute_project_authorship_signature_contract():
    sig = inspect.signature(compute_project_authorship)
    params = list(sig.parameters.keys())
    assert params == ["sections", "verified_quotes", "events_by_section"], (
        f"Incompatible signature detected: {params}"
    )

    p0 = sig.parameters["sections"]
    assert p0.default == inspect.Parameter.empty, "sections must be a required first argument"

    p1 = sig.parameters["verified_quotes"]
    assert p1.default is None, "verified_quotes must default to None"

    p2 = sig.parameters["events_by_section"]
    assert p2.default is None, "events_by_section must default to None"


def test_compute_project_authorship_caller_compatibility():
    # Calling with empty sections returns honest 100% human base state
    res = compute_project_authorship([])
    assert res["human_pct"] == 100
    assert res["ai_drafted_pct"] == 0
    assert res["requires_disclosure"] is False
    assert res["basis"] == "ledger"

    # Calling with invalid arguments (e.g. passing an object or string instead of a list of sections)
    with pytest.raises((TypeError, AttributeError)):
        compute_project_authorship("not_a_list")  # type: ignore[arg-type]
