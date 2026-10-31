import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from llm_client import LLMError  # noqa: E402
from relate import find_candidates, pair_key, suggest_edges  # noqa: E402

Q1 = "A aprendizagem significativa depende de conhecimentos prévios do aluno."
Q2 = "Estudos mostram que conhecimentos prévios do aluno influenciam a aprendizagem."


def claim(doc, concept, statement, quote, verified=True):
    return {"doc_id": doc, "concept": concept, "statement": statement, "quote": quote,
            "quote_verified": verified, "page_verified": 1}


A = claim("d1", "aprendizagem significativa", "aprendizagem significativa depende de conhecimentos prévios", Q1)
B = claim("d2", "aprendizagem significativa", "conhecimentos prévios influenciam aprendizagem do aluno", Q2)
SAME_DOC = claim("d1", "aprendizagem significativa", "aprendizagem significativa depende de conhecimentos prévios", Q1)
UNRELATED = claim("d3", "fotossíntese", "plantas convertem luz em energia química", "As plantas convertem luz solar em energia química por fotossíntese.")


class FakeLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def complete_json(self, system, user, schema, temperature=0.1):
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


CLS = {"relation": "apoia", "rationale": "ambos citam conhecimentos prévios", "confidence": 0.8}
IMPLICA = {"verdict": "implica", "reason": "ok"}
NAO = {"verdict": "nao_implica", "reason": "inferido"}


def test_candidates_skip_same_doc_and_unrelated():
    c = find_candidates([A, SAME_DOC, B, UNRELATED])
    pairs = {(x["doc_id"], y["doc_id"]) for _, x, y in c}
    assert ("d1", "d1") not in pairs and all("d3" not in p for p in pairs)
    assert len(c) >= 1


def test_rejected_pair_is_not_suggested_again():
    assert find_candidates([A, B], rejected={pair_key(A, B)}) == []


def test_edge_with_two_sided_evidence_is_displayed():
    edges = suggest_edges([A, B], FakeLLM(CLS, IMPLICA))
    assert len(edges) == 1
    e = edges[0]
    assert e["status"] == "suggested" and e["display_by_default"] is True
    assert e["evidence_a"]["quote"] == Q1 and e["evidence_b"]["quote"] == Q2


def test_failed_second_check_lowers_confidence_and_hides():
    e = suggest_edges([A, B], FakeLLM(CLS, NAO))[0]
    assert e["display_by_default"] is False and e["confidence"] < 0.8


def test_nenhuma_relation_is_dropped():
    llm = FakeLLM({"relation": "nenhuma", "rationale": "x", "confidence": 0.1})
    assert suggest_edges([A, B], llm) == [] and llm.calls == 1


def test_unverified_claim_is_never_used():
    llm = FakeLLM()
    bad = claim("d2", "aprendizagem significativa", B["statement"], Q2, verified=False)
    assert suggest_edges([A, bad], llm) == [] and llm.calls == 0


def test_quote_missing_from_pages_is_excluded():
    pages = {"d1": [Q1], "d2": ["Texto sem a citação esperada em lugar nenhum desta página."]}
    llm = FakeLLM()
    assert suggest_edges([A, B], llm, pages_by_doc=pages) == [] and llm.calls == 0


def test_llm_error_skips_pair():
    assert suggest_edges([A, B], FakeLLM(LLMError("falhou"))) == []


def test_max_five_suggestions():
    claims = [claim(f"d{i}", "aprendizagem significativa", "aprendizagem significativa depende de conhecimentos prévios", Q1) for i in range(6)]
    llm = FakeLLM(*([CLS, IMPLICA] * 20))
    assert len(suggest_edges(claims, llm)) == 5
