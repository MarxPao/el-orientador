import pytest


@pytest.fixture(autouse=True)
def _no_ai_summaries_by_default(monkeypatch):
    """Most tests script the LLM's responses call by call; the summary stage would consume them. Tests that
    exercise summaries turn it back on explicitly (monkeypatch.setattr(jobs, "SUMMARIZE_ENABLED", True))."""
    from app import jobs

    monkeypatch.setattr(jobs, "SUMMARIZE_ENABLED", False)


@pytest.fixture(autouse=True)
def _embeddings_from_the_scripted_client_by_default(monkeypatch):
    """Production default is a local model (EMBED_PROVIDER=local). Tests must never load or download one, so they
    use the scripted client's `embed`; tests of the local path set EMBED_PROVIDER=local with a fake model."""
    monkeypatch.setenv("EMBED_PROVIDER", "gemini")
