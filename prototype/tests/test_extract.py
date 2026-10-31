import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from extract import build_user_prompt, chunk_ranges, extract_document, load_prompt  # noqa: E402
from llm_client import LLMError  # noqa: E402

REAL = "A aprendizagem significativa ocorre quando o novo conteúdo se ancora em conhecimentos prévios."
FAKE = "Esta frase inventada nunca aparece em nenhuma página do documento analisado."


def claim(quote: str, page: int = 1) -> dict:
    return {
        "concept": "aprendizagem significativa",
        "statement": "A aprendizagem depende de conhecimentos prévios.",
        "quote": quote,
        "page": page,
    }


class FakeLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def complete_json(self, system, user, schema, temperature=0.1):
        self.prompts.append(user)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def doc(n_pages=2):
    pages = [f"Texto da página {i}. " + (REAL if i == 1 else "Conteúdo neutro sem relação.") for i in range(1, n_pages + 1)]
    return {"doc_id": "d1", "title": "Teste", "year": 2020, "pages": pages}


def test_load_prompt_sections():
    system, user = load_prompt()
    assert "assistente de leitura" in system
    assert "{pages_text_with_page_markers}" in user and "{page_start}" in user


def test_chunk_ranges():
    assert chunk_ranges(12, 5) == [(1, 5), (6, 10), (11, 12)]
    assert chunk_ranges(0) == []


def test_prompt_has_page_markers_and_no_leftover_placeholders():
    _, template = load_prompt()
    p = build_user_prompt(template, "T", "2020", ["a", "b"], 1, 2)
    assert "[Página 1]" in p and "[Página 2]" in p and not any(f"{{{k}}}" in p for k in ("title", "year", "page_start", "page_end", "pages_text_with_page_markers"))


def test_accepts_real_and_rejects_invented_claim():
    llm = FakeLLM({"claims": [claim(REAL), claim(FAKE)]})
    r = extract_document(doc(), llm)
    assert len(r["accepted"]) == 1 and len(r["rejected"]) == 1
    assert r["accepted"][0]["quote_verified"] is True
    assert r["rejected"][0]["verify_method"] == "none"
    assert r["approval_rate"] == 0.5


def test_corrects_wrong_page_number():
    llm = FakeLLM({"claims": [claim(REAL, page=2)]})
    r = extract_document(doc(), llm)
    assert r["accepted"][0]["page_verified"] == 1


def test_chunks_and_continues_after_failed_chunk():
    llm = FakeLLM(LLMError("falhou"), {"claims": [claim(REAL)]})
    r = extract_document(doc(4), llm, pages_per_chunk=2)
    assert r["n_chunks"] == 2 and len(r["errors"]) == 1 and r["errors"][0]["pages"] == [1, 2]
    assert len(r["accepted"]) == 1


def test_invalid_schema_output_is_recorded_as_error():
    llm = FakeLLM({"claims": [{"concept": "x"}]})
    r = extract_document(doc(), llm)
    assert r["errors"] and not r["accepted"] and r["approval_rate"] is None
