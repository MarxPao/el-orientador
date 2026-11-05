"""Paraphrase suggestions: by meaning, only against AI text in the ledger, counted only after the author confirms."""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import embeddings, paraphrase, repo as repo_mod  # noqa: E402
from app.main import create_app  # noqa: E402
from app.provenance import attribute  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402
from app.search import tokens  # noqa: E402

DSN = os.environ.get("TEST_DATABASE_URL")
PG_OK = bool(DSN) and "test" in (DSN or "").rsplit("/", 1)[-1].split("?")[0].lower()

AI_DRAFT = (
    "A permanência dos estudantes na escola depende do vínculo afetivo que eles constroem com professores e colegas, "
    "e as pesquisas disponíveis mostram que esse vínculo reduz de maneira consistente as taxas de abandono escolar "
    "no ensino médio regular das redes públicas brasileiras."
)
# same idea, different words (no 5-gram in common with the draft)
PARAPHRASE = (
    "Quando o aluno cria laços de afeto com os docentes e com a turma, ele tende a ficar na escola, e diversos "
    "estudos recentes indicam que justamente esse laço diminui o abandono no ensino médio das redes públicas do país "
    "de forma persistente ao longo dos anos analisados."
)
# same topic, written independently, about something else about schools
INDEPENDENT = (
    "O financiamento da merenda escolar sofreu cortes sucessivos na última década, o que afetou principalmente as "
    "escolas rurais, onde a refeição servida no colégio representa a principal alimentação diária de muitos alunos "
    "e de suas famílias em situação de vulnerabilidade."
)

GROUPS = [{"vinculo", "afeto", "afetivo", "lacos", "laco", "professores", "docentes", "colegas", "turma"},
          {"abandono", "evasao", "ficar", "permanencia", "reduz", "diminui"},
          {"merenda", "refeicao", "alimentacao", "financiamento", "cortes"}]


def vec(text: str) -> list[float]:
    v = [0.0] * (len(GROUPS) + 6)
    for t in tokens(text):
        hit = next((i for i, g in enumerate(GROUPS) if t in g), None)
        if hit is None:
            v[len(GROUPS) + sum(map(ord, t)) % 6] += 0.12
        else:
            v[hit] += 1.0
    return v


class FakeEmbedder:
    embed_model = "fake:embed"
    can_embed = True

    def embed(self, texts, task="document", operation="embed"):
        return [vec(t) for t in texts]


def doc(*paras):
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paras]}


def ev(kind, text, eid="e1"):
    return {"id": eid, "kind": kind, "text": text, "words": len(text.split()), "meta": {}, "declared": None}


# ----------------------------------------------------------------------------- pure
def test_paraphrase_is_found_independent_text_is_not():
    events = [ev("ai_draft", AI_DRAFT)]
    found = paraphrase.find(doc(PARAPHRASE, INDEPENDENT), events, lambda t, task: [vec(x) for x in t])
    assert [f["text"] for f in found] == [PARAPHRASE]
    assert found[0]["event_id"] == "e1" and found[0]["similarity"] >= paraphrase.min_similarity()


def test_ngram_attribution_alone_misses_the_paraphrase():
    """This is the gap the suggestion fills: no 5-gram is shared, so the ledger reads it as the author's."""
    w = attribute(doc(PARAPHRASE), [ev("ai_draft", AI_DRAFT)])
    assert w["human_words"] == w["total_words"]


def test_nothing_is_suggested_without_ai_text_in_the_ledger():
    assert paraphrase.find(doc(PARAPHRASE), [], lambda t, task: [vec(x) for x in t]) == []
    assert paraphrase.find(doc(PARAPHRASE), [ev("paste", AI_DRAFT)], lambda t, task: [vec(x) for x in t]) == []


def test_paragraphs_already_attributed_or_short_are_skipped():
    embed = lambda t, task: [vec(x) for x in t]  # noqa: E731
    assert paraphrase.find(doc(AI_DRAFT), [ev("ai_draft", AI_DRAFT)], embed) == []  # verbatim: already ai_drafted
    assert paraphrase.find(doc("Os laços de afeto reduzem o abandono escolar."), [ev("ai_draft", AI_DRAFT)], embed) == []


def test_lexical_anchor_blocks_pure_topic_matches(monkeypatch):
    # an embedder that says "identical" for everything must not be enough on its own
    same = lambda t, task: [[1.0, 0.0] for _ in t]  # noqa: E731
    assert paraphrase.find(doc(INDEPENDENT), [ev("ai_draft", AI_DRAFT)], same) == []


def test_threshold_is_configurable(monkeypatch):
    monkeypatch.setenv("PARAPHRASE_MIN_SIMILARITY", "0.9999")
    assert paraphrase.find(doc(PARAPHRASE), [ev("ai_draft", AI_DRAFT)], lambda t, task: [vec(x) for x in t]) == []


def test_confirmed_paraphrase_counts_as_ai_revised():
    events = [ev("ai_draft", AI_DRAFT), ev("ai_paraphrase", PARAPHRASE, "e2")]
    w = attribute(doc(PARAPHRASE, INDEPENDENT), events)
    assert w["ai_revised_words"] == len(PARAPHRASE.split())
    assert w["human_words"] == len(INDEPENDENT.split())


# ----------------------------------------------------------------------------- API
@pytest.fixture(params=["memory", "postgres"])
def env(request, tmp_path, monkeypatch):
    if request.param == "postgres":
        if not PG_OK:
            pytest.skip("TEST_DATABASE_URL not set to a *test* database")
        import psycopg

        with psycopg.connect(DSN) as c:
            c.execute("TRUNCATE users CASCADE")
        repo = repo_mod.PostgresRepo(DSN)
    else:
        repo = InMemoryRepo()
    monkeypatch.setenv("JOB_WORKER", "external")  # no embedded worker thread: it would outlive the test and steal jobs from test_pg_queue
    monkeypatch.setattr(embeddings, "resolve", lambda client=None: FakeEmbedder())
    app = create_app(repo=repo, storage_dir=tmp_path / "st", client=None, llm_factory=lambda: None)
    c = TestClient(app)
    tok = c.post("/auth/register", json={"email": "a@usp.br", "password": "password123", "name": "Ana"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = c.post("/projects", json={"title": "Projeto Paráfrase", "work": "tcc", "citation_style": "abnt"}, headers=h).json()["id"]
    sec = c.get(f"/projects/{pid}/sections", headers=h).json()[0]
    return c, repo, h, pid, sec["id"]


def put(c, h, pid, sid, *paras):
    r = c.patch(f"/projects/{pid}/sections/{sid}", json={"content": doc(*paras)}, headers=h)
    assert r.status_code == 200, r.text


def test_suggest_then_confirm_flow(env):
    c, repo, h, pid, sid = env
    repo.add_provenance_event(pid, sid, "ai_draft", "server", len(AI_DRAFT.split()), AI_DRAFT, {}, "a@usp.br")
    put(c, h, pid, sid, PARAPHRASE, INDEPENDENT)
    base = f"/projects/{pid}/sections/{sid}/provenance"
    before = c.get(base, headers=h).json()["authorship"]
    r = c.post(f"{base}/paraphrases", headers=h).json()
    assert r["available"] and [s["text"] for s in r["suggestions"]] == [PARAPHRASE]
    # a suggestion alone changes nothing
    assert c.get(base, headers=h).json()["authorship"]["ai_revised_words"] == before["ai_revised_words"] == 0
    ok = c.post(f"{base}/paraphrases/confirm", json={"text": PARAPHRASE, "event_id": r["suggestions"][0]["event_id"]}, headers=h)
    assert ok.status_code == 200 and ok.json()["recorded"]
    after = ok.json()["authorship"]
    assert after["ai_revised_words"] == len(PARAPHRASE.split()) and after["requires_disclosure"] is True
    assert c.post(f"{base}/paraphrases", headers=h).json()["suggestions"] == []  # confirmed ones are not suggested again


def test_confirm_rejects_text_not_in_the_section_and_short_text(env):
    c, repo, h, pid, sid = env
    put(c, h, pid, sid, INDEPENDENT)
    base = f"/projects/{pid}/sections/{sid}/provenance/paraphrases/confirm"
    assert c.post(base, json={"text": PARAPHRASE}, headers=h).status_code == 422
    assert c.post(base, json={"text": "curto demais"}, headers=h).status_code == 422


def test_only_the_owner_can_search_or_confirm(env):
    c, repo, h, pid, sid = env
    put(c, h, pid, sid, PARAPHRASE)
    other = c.post("/auth/register", json={"email": "b@usp.br", "password": "password123", "name": "B"}).json()["token"]
    ho = {"Authorization": f"Bearer {other}"}
    base = f"/projects/{pid}/sections/{sid}/provenance/paraphrases"
    assert c.post(base, headers=ho).status_code in (403, 404)
    assert c.post(f"{base}/confirm", json={"text": PARAPHRASE}, headers=ho).status_code in (403, 404)


def test_without_an_embedder_it_says_so(env, monkeypatch):
    c, repo, h, pid, sid = env
    monkeypatch.setattr(embeddings, "resolve", lambda client=None: None)
    r = c.post(f"/projects/{pid}/sections/{sid}/provenance/paraphrases", headers=h).json()
    assert r["available"] is False and r["suggestions"] == [] and "embeddings" in r["notice"]


def test_dismissed_suggestion_is_recorded_does_not_come_back_and_never_touches_the_prism(env):
    c, repo, h, pid, sid = env
    repo.add_provenance_event(pid, sid, "ai_draft", "server", len(AI_DRAFT.split()), AI_DRAFT, {}, "a@usp.br")
    put(c, h, pid, sid, PARAPHRASE, INDEPENDENT)
    base = f"/projects/{pid}/sections/{sid}/provenance"
    prism = c.get(base, headers=h).json()["authorship"]
    assert c.post(f"{base}/paraphrases/dismiss", json={"text": PARAPHRASE}, headers=h).json()["recorded"]
    assert c.post(f"{base}/paraphrases", headers=h).json()["suggestions"] == []
    after = c.get(base, headers=h).json()
    strip = lambda d: {k: v for k, v in d.items() if k != "events"}  # noqa: E731
    assert strip(after["authorship"]) == strip(prism)  # not an authorship event: no number moves
    assert any(e["kind"] == "paraphrase_dismissed" for e in after["events"])  # but the answer is on the record


def test_pending_counts_only_unanswered_suggestions_and_the_docx_says_so(env):
    import io

    import docx

    c, repo, h, pid, sid = env
    repo.add_provenance_event(pid, sid, "ai_draft", "server", len(AI_DRAFT.split()), AI_DRAFT, {}, "a@usp.br")
    put(c, h, pid, sid, PARAPHRASE, INDEPENDENT)
    pend = c.get(f"/projects/{pid}/provenance/pending", headers=h).json()
    assert pend["available"] and pend["total"] == 1 and pend["sections"][0]["section_id"] == sid

    def declaration():
        r = c.get(f"/projects/{pid}/export/docx", headers=h)
        assert r.status_code == 200
        return "\n".join(p.text for p in docx.Document(io.BytesIO(r.content)).paragraphs)

    text = declaration()
    assert "Limites deste registro" in text and "1 trecho(s) pareciam reescrita" in text
    c.post(f"/projects/{pid}/sections/{sid}/provenance/paraphrases/dismiss", json={"text": PARAPHRASE}, headers=h)
    assert c.get(f"/projects/{pid}/provenance/pending", headers=h).json()["total"] == 0
    assert "pareciam reescrita" not in declaration()  # answered: nothing left to warn about
    other = c.post("/auth/register", json={"email": "b@usp.br", "password": "password123", "name": "B"}).json()["token"]
    assert c.get(f"/projects/{pid}/provenance/pending", headers={"Authorization": f"Bearer {other}"}).status_code in (403, 404)
