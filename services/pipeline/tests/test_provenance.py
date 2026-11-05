"""Phase 3: authorship comes from a provenance ledger, not from how the text sounds.

Pure-function tests, then API tests on InMemoryRepo and (when TEST_DATABASE_URL names a *test* database)
on real Postgres too.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import repo as repo_mod  # noqa: E402
from app.authorship import compute_project_authorship, compute_section_authorship  # noqa: E402
from app.main import create_app  # noqa: E402
from app.provenance import attribute, percentages  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402

DSN = os.environ.get("TEST_DATABASE_URL")
PG_OK = bool(DSN) and "test" in (DSN or "").rsplit("/", 1)[-1].split("?")[0].lower()


def doc(*paragraphs: str) -> dict:
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paragraphs]}


AI_PARAGRAPH = (
    "A retenção escolar depende de múltiplos fatores articulados entre si, e os estudos disponíveis indicam que "
    "o vínculo afetivo com a escola reduz de forma consistente as taxas de abandono no ensino médio regular."
)
STUDENT_PARAGRAPH = "Na minha experiência como monitora, vi colegas largarem o curso quando o transporte ficou caro demais."
PASTED = (
    "O orçamento federal destinado à assistência estudantil cresceu de maneira desigual entre as regiões do país "
    "durante a última década, concentrando-se nas capitais e deixando os campi do interior com recursos escassos."
)


def ev(kind, text=None, **kw):
    return {"id": kw.pop("id", f"e-{kind}-{abs(hash(text or '')) % 1000}"), "kind": kind, "text": text,
            "words": len((text or "").split()), "source": "server", "meta": kw.pop("meta", {}), **kw}


# ----------------------------------------------------------------------------- pure
def test_text_with_no_events_is_all_human_whatever_it_sounds_like():
    cliche_heavy = (
        "Vale ressaltar que, nesse sentido, o tema desempenha um papel crucial. Em suma, torna-se evidente que "
        "por conseguinte a questão é de relevância central. Outrossim, cabe destacar que diante do exposto "
        "é imperativo considerar a perspectiva. Todas as frases têm o mesmo tamanho aproximado de palavras aqui."
    )
    w = attribute(doc(cliche_heavy), [])
    assert w["human_words"] == w["total_words"] and w["ai_drafted_words"] == 0
    sec = {"id": "s", "content": doc(cliche_heavy)}
    a = compute_section_authorship(sec, events=[])
    assert a["requires_disclosure"] is False and a["human_pct"] == 100 and a["basis"] == "ledger"
    assert not any(k in a for k in ("forensics", "measured_ai_score", "burstiness_score", "llm_markers_found"))


def test_recorded_ai_text_is_attributed_and_leaves_the_ledger_when_rewritten():
    events = [ev("ai_draft", AI_PARAGRAPH)]
    untouched = attribute(doc(STUDENT_PARAGRAPH, AI_PARAGRAPH), events)
    assert untouched["ai_drafted_words"] == len(AI_PARAGRAPH.split())
    assert untouched["human_words"] == len(STUDENT_PARAGRAPH.split())

    rewritten = "Para mim, a escola segura o aluno quando ele se sente parte dela, e isso pesa mais que qualquer programa."
    gone = attribute(doc(STUDENT_PARAGRAPH, rewritten), events)
    assert gone["ai_drafted_words"] == 0 and gone["ai_revised_words"] == 0  # the student's own words now


def test_edited_ai_draft_is_reported_as_revised_not_laundered():
    edited = AI_PARAGRAPH.replace("múltiplos fatores articulados entre si", "vários fatores")\
                         .replace("de forma consistente", "bastante").replace("regular", "público")
    w = attribute(doc(edited), [ev("ai_draft", AI_PARAGRAPH)])
    assert w["ai_drafted_words"] > 0 and w["ai_revised_words"] > 0
    assert w["human_words"] == 0
    assert w["ai_drafted_words"] + w["ai_revised_words"] == w["total_words"]
    sec = {"id": "s", "content": doc(edited)}
    a = compute_section_authorship(sec, events=[ev("ai_draft", AI_PARAGRAPH)])
    assert a["requires_disclosure"] is True and any("rascunho da IA" in n for n in a["notes"])


def test_paste_declared_own_and_quote_handling():
    p = ev("paste", PASTED, id="p1")
    assert attribute(doc(PASTED), [p])["pasted_words"] == len(PASTED.split())
    declared = attribute(doc(PASTED), [{**p, "declared": "own_text"}])
    assert declared["pasted_words"] == 0 and declared["declared_own_words"] == len(PASTED.split())
    quoted = attribute(doc(PASTED), [p], verified_quotes=[PASTED])  # pasted from a verified source quote
    assert quoted["pasted_words"] == 0 and quoted["quoted_words"] == len(PASTED.split())
    a = compute_section_authorship({"id": "s", "content": doc(PASTED)}, events=[p])
    assert a["requires_disclosure"] is True and a["pending_paste_events"] == ["p1"]


def test_ai_text_that_is_also_a_quote_still_counts_as_ai_inserted():
    w = attribute(doc(AI_PARAGRAPH), [ev("ai_draft", AI_PARAGRAPH)], verified_quotes=[AI_PARAGRAPH])
    assert w["ai_drafted_words"] == w["total_words"] and w["quoted_words"] == 0


def test_coauthor_splits_student_premise_from_ai_expansion():
    text = "A permanência depende do engajamento ativo em sala. " + AI_PARAGRAPH
    n = len(text.split())
    premise = len("A permanência depende do engajamento ativo em sala.".split())
    e = ev("ai_coauthor", text, meta={"ai_words": n - premise, "student_words": premise})
    w = attribute(doc(text), [e])
    assert w["polished_words"] == premise and w["ai_drafted_words"] == n - premise


def test_legacy_counters_are_kept_but_never_exceed_the_words_present():
    legacy = ev("legacy_counters", None, meta={"ai_words": 10, "polished_words": 5})
    w = attribute(doc(STUDENT_PARAGRAPH), [legacy])
    assert w["ai_drafted_words"] == 10 and w["polished_words"] == 5
    assert w["human_words"] == len(STUDENT_PARAGRAPH.split()) - 15
    tiny = attribute(doc("duas palavras"), [legacy])
    assert tiny["total_words"] == 2 and tiny["ai_drafted_words"] == 2 and tiny["human_words"] == 0


def test_percentages_always_add_up_to_100():
    for words in ({"ai_drafted_words": 1, "ai_revised_words": 1, "human_words": 1},
                  {"ai_drafted_words": 33, "pasted_words": 33, "human_words": 34, "quoted_words": 7},
                  {}):
        total = sum(words.values())
        pct = percentages(words, total)
        assert sum(pct.values()) == 100, (words, pct)


def test_without_a_ledger_old_counters_still_work_and_say_so():
    sec = {"id": "s", "content": {**doc("um dois três quatro cinco seis sete oito nove dez"),
                                  "_authorship": {"ai_drafted_words": 4, "polished_words": 2}}}
    a = compute_section_authorship(sec)
    assert a["basis"] == "counters" and a["ai_drafted_words"] == 4 and a["polished_words"] == 2
    p = compute_project_authorship([sec])
    assert p["basis"] == "counters" and p["requires_disclosure"] is True


# ----------------------------------------------------------------------------- API
class WriterLLM:
    model = "writer"

    def __init__(self):
        self.polished = AI_PARAGRAPH.replace("depende de", "decorre de")
        self.coauthored = "A permanência depende do engajamento. " + AI_PARAGRAPH
        self.drafted = AI_PARAGRAPH

    def complete_json(self, system, user, schema, temperature=0.1):
        props = schema.get("properties", {})
        if "polished_text" in props:
            return {"polished_text": self.polished}
        if "coauthored_paragraph" in props:
            return {"coauthored_paragraph": self.coauthored}
        if "draft_paragraph" in props:
            return {"draft_paragraph": self.drafted}
        return {"claims": []}


@pytest.fixture(params=["memory", "postgres"])
def env(request, tmp_path, monkeypatch):
    if request.param == "postgres":
        if not PG_OK:
            pytest.skip("TEST_DATABASE_URL not set to a *test* database")
        import psycopg

        monkeypatch.setenv("JOB_WORKER", "external")
        with psycopg.connect(DSN) as c:
            c.execute("TRUNCATE users CASCADE")
        repo = repo_mod.PostgresRepo(DSN)
    else:
        repo = InMemoryRepo()
    llm = WriterLLM()
    c = TestClient(create_app(repo=repo, storage_dir=tmp_path / "st", client=llm, llm_factory=lambda: llm))
    tok = c.post("/auth/register", json={"email": "a@usp.br", "password": "password123", "name": "Ana"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = c.post("/projects", json={"title": "Projeto Prov", "work": "tcc", "citation_style": "abnt"}, headers=h).json()["id"]
    sec = c.get(f"/projects/{pid}/sections", headers=h).json()[0]
    d = repo.create_document(pid, {"title": "Fonte", "authors": ["Ana Moran"], "year": 2020, "doi": None,
                                   "storage_path": None, "analysis": "full_text", "status": "extracted"})
    repo.add_claims(d["id"], [{"concept": "vínculo", "statement": "O vínculo reduz o abandono.",
                               "quote": "O vínculo afetivo reduz o abandono escolar.", "page_verified": 3,
                               "quote_verified": True, "verify_method": "exact"}], "m", "v")
    return c, repo, h, pid, sec["id"], llm


def put(c, h, pid, sid, *paragraphs):
    r = c.patch(f"/projects/{pid}/sections/{sid}", headers=h, json={"content": doc(*paragraphs)})
    assert r.status_code == 200, r.text
    return r.json()


def authorship(c, h, pid, sid):
    return c.get(f"/projects/{pid}/authorship", headers=h).json()["sections"][sid]


def test_draft_is_recorded_and_follows_the_text_when_the_student_rewrites_it(env):
    c, repo, h, pid, sid, llm = env
    put(c, h, pid, sid, STUDENT_PARAGRAPH)
    r = c.post(f"/projects/{pid}/sections/{sid}/ai-assist", headers=h, json={"mode": "draft", "intensity": 90})
    assert r.status_code == 200 and r.json()["llm_used"] is True
    a = r.json()["section_authorship"]
    assert a["basis"] == "ledger" and a["ai_drafted_words"] == len(AI_PARAGRAPH.split())
    assert a["human_words"] == len(STUDENT_PARAGRAPH.split()) and a["requires_disclosure"] is True
    events = c.get(f"/projects/{pid}/sections/{sid}/provenance", headers=h).json()["events"]
    assert [e["kind"] for e in events] == ["ai_draft"] and events[0]["excerpt"].startswith("A retenção")

    put(c, h, pid, sid, STUDENT_PARAGRAPH, "Reescrevi tudo isso com as minhas palavras depois de ler os três artigos.")
    a = authorship(c, h, pid, sid)
    assert a["ai_drafted_words"] == 0 and a["requires_disclosure"] is False  # the ledger follows the text


def test_polishing_an_ai_draft_with_ai_does_not_turn_it_into_student_text(env):
    c, repo, h, pid, sid, llm = env
    c.post(f"/projects/{pid}/sections/{sid}/ai-assist", headers=h, json={"mode": "draft", "intensity": 90})
    r = c.post(f"/projects/{pid}/sections/{sid}/ai-assist", headers=h, json={"mode": "polish", "intensity": 45})
    assert r.status_code == 200 and r.json()["llm_used"] is True
    a = r.json()["section_authorship"]
    assert a["ai_drafted_words"] >= 0.9 * a["total_words"] and a["polished_words"] <= 0.1 * a["total_words"]
    assert a["requires_disclosure"] is True


def test_polishing_student_text_stays_polish_and_exempt(env):
    c, repo, h, pid, sid, llm = env
    llm.polished = "Na minha experiência como monitora, observei colegas abandonarem o curso quando o transporte encareceu demais."
    put(c, h, pid, sid, STUDENT_PARAGRAPH)
    a = c.post(f"/projects/{pid}/sections/{sid}/ai-assist", headers=h, json={"mode": "polish", "intensity": 45}).json()["section_authorship"]
    assert a["polished_words"] > 0 and a["ai_drafted_words"] == 0 and a["requires_disclosure"] is False


def test_coauthor_event_splits_premise_and_expansion(env):
    c, repo, h, pid, sid, llm = env
    r = c.post(f"/projects/{pid}/sections/{sid}/ai-assist", headers=h,
               json={"mode": "coauthor", "intensity": 70, "instruction": "A permanência depende do engajamento"})
    a = r.json()["section_authorship"]
    assert a["polished_words"] > 0 and a["ai_drafted_words"] > a["polished_words"]


def test_paste_events_declaration_and_permissions(env):
    c, repo, h, pid, sid, llm = env
    url = f"/projects/{pid}/sections/{sid}/provenance"
    small = c.post(f"{url}/paste", headers=h, json={"text": "só algumas palavras coladas"}).json()
    assert small["recorded"] is False
    big = c.post(f"{url}/paste", headers=h, json={"text": PASTED}).json()
    assert big["recorded"] is True and big["words"] == len(PASTED.split())

    put(c, h, pid, sid, STUDENT_PARAGRAPH, PASTED)
    a = authorship(c, h, pid, sid)
    assert a["pasted_words"] == len(PASTED.split()) and a["requires_disclosure"] is True
    assert a["pending_paste_events"] == [big["event_id"]]

    other = c.post("/auth/register", json={"email": "b@usp.br", "password": "password123", "name": "B"}).json()["token"]
    ho = {"Authorization": f"Bearer {other}"}
    assert c.post(f"{url}/events/{big['event_id']}/declare", headers=ho, json={"declared": "own_text"}).status_code == 404
    assert c.post(f"{url}/events/nao-existe/declare", headers=h, json={"declared": "own_text"}).status_code == 404
    assert c.post(f"{url}/events/{big['event_id']}/declare", headers=h, json={"declared": "outra"}).status_code == 422

    a = c.post(f"{url}/events/{big['event_id']}/declare", headers=h, json={"declared": "own_text"}).json()
    assert a["pasted_words"] == 0 and a["declared_own_words"] == len(PASTED.split()) and a["requires_disclosure"] is False
    a = c.post(f"{url}/events/{big['event_id']}/declare", headers=h, json={"declared": None}).json()
    assert a["pasted_words"] == len(PASTED.split())  # the statement can be withdrawn

    # an advisor can read the ledger but not write to it
    c.post(f"/projects/{pid}/advisors", headers=h, json={"advisor_email": "b@usp.br"})
    assert c.get(f"{url}", headers=ho).status_code == 200
    assert c.post(f"{url}/paste", headers=ho, json={"text": PASTED}).status_code == 404


def test_turning_the_ledger_on_keeps_earlier_counter_based_ai_words(env):
    c, repo, h, pid, sid, llm = env
    old = {**doc("um dois três quatro cinco seis sete oito nove dez onze doze treze quatorze quinze dezesseis"),
           "_authorship": {"ai_drafted_words": 8, "polished_words": 0}}
    repo.update_section(pid, sid, content=old)
    assert authorship(c, h, pid, sid)["basis"] == "ledger"  # events=[] -> ledger with no AI text recorded
    c.post(f"/projects/{pid}/sections/{sid}/provenance/paste", headers=h, json={"text": PASTED})
    legacy = [e for e in repo.list_provenance_events(pid, sid) if e["kind"] == "legacy_counters"]
    assert len(legacy) == 1 and legacy[0]["meta"]["ai_words"] == 8
    put(c, h, pid, sid, "um dois três quatro cinco seis sete oito nove dez onze doze treze quatorze quinze dezesseis")
    assert authorship(c, h, pid, sid)["ai_drafted_words"] == 8


def test_validate_authenticity_is_read_only_and_makes_no_style_claim(env):
    c, repo, h, pid, sid, llm = env
    put(c, h, pid, sid, STUDENT_PARAGRAPH)
    before = repo.get_section(pid, sid)["content"]
    r = c.post(f"/projects/{pid}/sections/{sid}/validate-authenticity", headers=h, json={"sync_prism": True}).json()
    assert r["synced"] is False and "estilo" in r["notice"]
    assert repo.get_section(pid, sid)["content"] == before  # nothing was overwritten
    assert r["section_authorship"]["human_pct"] == 100
    assert "forensics" not in r["section_authorship"] and "measured_ai_score" not in r["project_authorship"]
    assert "burstiness_score" not in r["project_authorship"]


def test_project_totals_report_and_capabilities(env):
    c, repo, h, pid, sid, llm = env
    c.post(f"/projects/{pid}/sections/{sid}/ai-assist", headers=h, json={"mode": "draft", "intensity": 90})
    proj = c.get(f"/projects/{pid}/authorship", headers=h).json()["project"]
    assert proj["ai_drafted_words"] > 0 and proj["requires_disclosure"] is True and proj["basis"] == "ledger"
    assert "redigido com IA" in proj["status_label"] and proj["limits"]
    assert c.get("/capabilities").json()["features"]["authorship"] == "provenance_ledger"
    assert "forensics" not in c.get("/capabilities").json()["features"]
    docx = c.get(f"/projects/{pid}/export/docx", headers=h)
    assert docx.status_code == 200 and len(docx.content) > 1000


def test_deleting_a_section_removes_its_events(env):
    c, repo, h, pid, sid, llm = env
    c.post(f"/projects/{pid}/sections/{sid}/provenance/paste", headers=h, json={"text": PASTED})
    assert repo.list_provenance_events(pid, sid)
    c.delete(f"/projects/{pid}/sections/{sid}", headers=h)
    assert repo.list_provenance_events(pid) == []
