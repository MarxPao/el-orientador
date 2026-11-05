"""Phase 0 contract: the product never fakes AI and its own output never contains the stock formulas it tells the model to avoid.

- With an LLM, every writing assistant really calls it with (system, user, schema).
- Without an LLM (or during an outage), assistants return honest non-generative output and say so.
- Nothing the system writes on its own contains the LLM clichés the validator flags.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.authorship import (  # noqa: E402
    cliche_markers,
    coauthor_with_evidence,
    draft_evidence_paragraph,
    mechanical_cleanup,
    polish_academic_text,
)
from app.llm_gateway import LLMGateway, LLMUnavailable  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402
from app.text_analysis import compare_and_connect_passages  # noqa: E402

DOC = {"id": "d1", "title": "Metodologias ativas na escola", "authors": ["José Moran"], "year": 2015}
DOC2 = {"id": "d2", "title": "Formação docente", "authors": ["Maria Silva"], "year": 2019}
CLAIMS = [
    {"id": "c1", "document_id": "d1", "page_no": 14, "concept": "Metodologias ativas",
     "statement": "Metodologias ativas aumentam retenção.",
     "quote": "A adoção de metodologias ativas eleva a retenção escolar em 28%."},
    {"id": "c2", "document_id": "d2", "page_no": 19, "concept": "Formação docente",
     "statement": "Sem formação, o método falha.",
     "quote": "Sem formação continuada, o método ativo enfrenta limitações severas."},
]
DOCS = {"d1": DOC, "d2": DOC2}


class RecordingLLM:
    model = "mock-llm"

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[tuple[str, str, dict]] = []

    def complete_json(self, system, user, schema):
        self.calls.append((system, user, schema))
        return self.payload


class FailingLLM:
    model = "failing"

    def complete_json(self, system, user, schema):
        raise RuntimeError("provider down")


# ---------------------------------------------------------------- contract: no self-accusation
def _system_outputs() -> list[str]:
    outs = [
        mechanical_cleanup("a gente acha  que isso , importa muito hoje em dia"),
        coauthor_with_evidence("A permanência depende do engajamento", CLAIMS, DOCS, "Introdução"),
        coauthor_with_evidence("", CLAIMS, DOCS, "Introdução"),
        draft_evidence_paragraph(CLAIMS, DOCS, "Referencial Teórico", instruction="o problema da evasão"),
        draft_evidence_paragraph(CLAIMS, DOCS, "Referencial Teórico"),
    ]
    for rel in ("contraponto", "corroboracao", "complementaridade", "lacuna"):
        for note in ("O efeito depende da capacitação docente", None):
            for intensity in (35, 90):  # 90 without client must degrade to the scaffold
                outs.append(
                    compare_and_connect_passages(
                        {**CLAIMS[0]}, {**CLAIMS[1]}, DOC, DOC2, rel, note, "Referencial", intensity
                    )["synthesis_text"]
                )
    return outs


@pytest.mark.parametrize("text", _system_outputs())
def test_system_generated_text_has_no_llm_markers(text):
    found = cliche_markers(text)
    assert found == [], (found, text)


def test_mechanical_cleanup_never_rewrites_words():
    out = mechanical_cleanup("a gente acha  que isso , importa muito hoje em dia")
    assert out == "A gente acha que isso, importa muito hoje em dia"
    assert polish_academic_text("hoje em dia pra gente", "Intro") == "Hoje em dia pra gente"


def test_scaffolds_keep_verified_quotes_and_explicit_gaps():
    draft = draft_evidence_paragraph(CLAIMS, DOCS, "Referencial")
    assert CLAIMS[0]["quote"].rstrip(".") in draft and "(Moran, 2015, p. 14)" in draft
    assert "[" in draft and "]" in draft


# ---------------------------------------------------------------- regression: LLM really called
def test_generators_call_llm_with_system_user_schema():
    llm = RecordingLLM({"polished_text": "Texto revisado.", "coauthored_paragraph": "P.", "draft_paragraph": "D."})
    assert polish_academic_text("texto", "Intro", client=llm) == "Texto revisado."
    assert coauthor_with_evidence("Premissa", CLAIMS, DOCS, "Intro", client=llm) == "P."
    assert draft_evidence_paragraph(CLAIMS, DOCS, "Intro", client=llm) == "D."
    assert len(llm.calls) == 3
    for system, user, schema in llm.calls:
        assert system and user and schema["type"] == "object"
    assert CLAIMS[0]["quote"] in llm.calls[2][1]  # evidence goes to the model


def test_compare_synthesis_uses_llm_above_55_and_degrades_honestly():
    llm = RecordingLLM({"synthesis": "Síntese dialética."})
    ok = compare_and_connect_passages(CLAIMS[0], CLAIMS[1], DOC, DOC2, "contraponto", "nota", "Ref", 80, client=llm)
    assert ok["mode_used"] == "sintese_assistida" and ok["llm_used"] is True and ok["notice"] is None
    down = compare_and_connect_passages(
        CLAIMS[0], CLAIMS[1], DOC, DOC2, "contraponto", "nota", "Ref", 80, client=LLMGateway(FailingLLM())
    )
    assert down["mode_used"] == "scaffold_socratico" and down["llm_used"] is False and down["notice"]


# ---------------------------------------------------------------- gateway
def test_gateway_circuit_breaker_fails_fast_then_recovers():
    now = [0.0]
    gw = LLMGateway(FailingLLM(), failure_threshold=2, cooldown_seconds=30, clock=lambda: now[0])
    for _ in range(2):
        with pytest.raises(LLMUnavailable):
            gw.complete_json("s", "u", {})
    assert gw.circuit_open and not gw.available
    now[0] = 31.0
    assert gw.available


# ---------------------------------------------------------------- API end to end
def _setup(llm=None):
    repo = InMemoryRepo()
    c = TestClient(create_app(repo=repo, client=llm))
    r = c.post("/auth/register", json={"email": "a@b.br", "password": "senha-segura-1", "name": "A"})
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    pid = c.post("/projects", json={"title": "TCC Evasão", "work": "tcc"}, headers=h).json()["id"]
    doc = repo.create_document(pid, {"title": DOC["title"], "authors": DOC["authors"], "year": 2015, "status": "extracted"})
    repo.add_claims(doc["id"], [{
        "concept": "Metodologias ativas", "statement": CLAIMS[0]["statement"], "quote": CLAIMS[0]["quote"],
        "page_verified": 14, "quote_verified": True, "verify_method": "exact",
    }], model="test", prompt_version="t")
    sec = c.get(f"/projects/{pid}/sections", headers=h).json()[0]
    return c, h, pid, sec["id"]


def test_ai_assist_with_llm_reports_llm_used():
    llm = RecordingLLM({"draft_paragraph": "Parágrafo com “A adoção de metodologias ativas eleva a retenção escolar em 28%” (Moran, 2015, p. 14)."})
    c, h, pid, sid = _setup(llm)
    r = c.post(f"/projects/{pid}/sections/{sid}/ai-assist", json={"mode": "draft"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["llm_used"] is True and body["notice"] is None
    assert len(llm.calls) == 1


def test_ai_assist_outage_returns_scaffold_with_notice():
    c, h, pid, sid = _setup(FailingLLM())
    r = c.post(f"/projects/{pid}/sections/{sid}/ai-assist", json={"mode": "draft"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["llm_used"] is False and "falhou" in body["notice"]
    assert CLAIMS[0]["quote"].rstrip(".") in body["generated_text"]


def test_mechanical_polish_keeps_structure_and_marks():
    c, h, pid, sid = _setup()
    content = {"type": "doc", "content": [
        {"type": "paragraph", "content": [
            {"type": "text", "text": "este  trabalho investiga "},
            {"type": "text", "text": "evasão", "marks": [{"type": "bold"}]},
            {"type": "text", "text": " escolar ."},
        ]},
        {"type": "paragraph", "content": [{"type": "text", "text": "segundo parágrafo."}]},
    ]}
    c.patch(f"/projects/{pid}/sections/{sid}", json={"content": content}, headers=h)
    r = c.post(f"/projects/{pid}/sections/{sid}/ai-assist", json={"mode": "polish"}, headers=h)
    assert r.status_code == 200
    paras = r.json()["section"]["content"]["content"]
    assert len(paras) == 2
    nodes = paras[0]["content"]
    assert nodes[0]["text"] == "Este trabalho investiga "
    assert nodes[1] == {"type": "text", "text": "evasão", "marks": [{"type": "bold"}]}
    assert nodes[2]["text"] == " escolar."
    assert paras[1]["content"][0]["text"] == "Segundo parágrafo."


def test_capabilities_without_llm():
    c, *_ = _setup()
    caps = c.get("/capabilities").json()
    assert caps["llm_configured"] is False
    assert caps["features"]["gate_dialogue"] == "unavailable"
    assert caps["features"]["draft"] == "scaffold"
