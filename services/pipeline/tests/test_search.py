"""Phase 2: passage index, hybrid search, embeddings, summaries, reindex.

API tests run on InMemoryRepo and, when TEST_DATABASE_URL points at a *test* database, on real Postgres too.
"""
import os
import sys
import urllib.error
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import jobs, repo as repo_mod  # noqa: E402
from app.jobs import InlineQueue  # noqa: E402
from app.llm_gateway import LLMGateway, LLMUnavailable  # noqa: E402
from app.main import create_app  # noqa: E402
from app.pipeline.llm_client import GeminiClient, LLMError  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402
from app.search import bm25_rank, chunk_pages, fold, rrf, snippet, tokens, tsquery  # noqa: E402

DSN = os.environ.get("TEST_DATABASE_URL")
PG_OK = bool(DSN) and "test" in (DSN or "").rsplit("/", 1)[-1].split("?")[0].lower()

GROUPS = [{"evasao", "abandono", "desistencia"}, {"entrevistas", "entrevista", "qualitativa", "metodologia"},
          {"inflacao", "precos"}]


def fake_vector(text: str) -> list[float]:
    v = [0.0] * (len(GROUPS) + 8)
    for t in tokens(text):
        hit = False
        for i, g in enumerate(GROUPS):
            if t in g:
                v[i] += 1.0
                hit = True
        if not hit:
            v[len(GROUPS) + (sum(map(ord, t)) % 8)] += 0.05
    v[-1] += 0.01
    n = sum(x * x for x in v) ** 0.5
    return [x / n for x in v]


class FakeLLM:
    """Extraction returns no claims (these tests are about search); summaries and embeddings are deterministic."""
    model = "fake-llm"
    embed_model = "fake-embed"

    def __init__(self, embed_ok=True, summary_ok=True):
        self.embed_ok, self.summary_ok = embed_ok, summary_ok
        self.embed_calls = 0
        self.summary_calls = 0

    def complete_json(self, system, user, schema, temperature=0.1):
        if "summary" in schema.get("properties", {}):
            self.summary_calls += 1
            if not self.summary_ok:
                raise RuntimeError("down")
            return {"summary": f"Resumo #{self.summary_calls}."}
        return {"claims": []}

    def embed(self, texts, task="document"):
        self.embed_calls += 1
        if not self.embed_ok:
            raise RuntimeError("embedding provider down")
        return [fake_vector(t) for t in texts]


class NoEmbedLLM:
    model = "no-embed"

    def complete_json(self, system, user, schema, temperature=0.1):
        return {"claims": []}


PAGES = [
    "A evasão escolar no ensino médio é um problema persistente. Estudos mostram que a evasão cresce quando "
    "a renda familiar cai, e as políticas públicas ainda tratam o tema de forma fragmentada em muitas redes.",
    "A metodologia adotada é qualitativa, baseada em entrevistas semiestruturadas com professores e gestores. "
    "As entrevistas foram gravadas, transcritas e codificadas segundo categorias definidas previamente.",
    "A inflação de preços afeta o poder de compra das famílias e altera o consumo de bens duráveis ao longo "
    "do ciclo econômico, conforme discutido no capítulo anterior sobre política monetária e juros.",
]


def make_pdf(path: Path, pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 790), text, fontsize=11)
    doc.save(path)
    return path.read_bytes()


def build(request, tmp_path, monkeypatch, llm):
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
    storage = tmp_path / "st"
    holder = {"llm": llm}
    factory = lambda: holder["llm"]  # noqa: E731
    app = create_app(repo=repo, storage_dir=storage, llm_factory=factory, client=llm,
                     job_queue=InlineQueue(repo, storage, factory))
    c = TestClient(app)
    tok = c.post("/auth/register", json={"email": "a@usp.br", "password": "password123", "name": "Ana Moran"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = c.post("/projects", json={"title": "Projeto Busca", "work": "tcc", "citation_style": "abnt"}, headers=h).json()["id"]
    return c, repo, h, pid, storage, holder, app


@pytest.fixture(params=["memory", "postgres"])
def env(request, tmp_path, monkeypatch):
    return build(request, tmp_path, monkeypatch, FakeLLM())


def upload(c, h, pid, tmp_path, pages=PAGES, title="Estudo sobre evasão", name="d.pdf"):
    pdf = make_pdf(tmp_path / name, pages)
    r = c.post(f"/projects/{pid}/documents/upload", headers=h, data={"title": title},
               files={"file": (name, pdf, "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ----------------------------------------------------------------------------- pure functions
def test_chunking_is_page_bounded_overlapping_and_skips_noise():
    long_page = " ".join(f"Frase número {i} do capítulo, com conteúdo suficiente para contar." for i in range(80))
    chunks = chunk_pages(["x", long_page, "Texto curto de uma página qualquer, mas com mais de quarenta caracteres."])
    assert all(c["page_no"] in (2, 3) for c in chunks)  # page 1 ("x") is below the minimum
    long_chunks = [c for c in chunks if c["page_no"] == 2]
    assert len(long_chunks) >= 3 and all(len(c["text"]) <= 1400 for c in long_chunks)
    assert [c["chunk_no"] for c in chunks] == list(range(len(chunks)))
    a, b = long_chunks[0]["text"], long_chunks[1]["text"]
    assert a[-60:].split()[-1] in b  # overlap carries the tail of one chunk into the next
    assert chunks[-1]["search_text"] == fold(chunks[-1]["text"])


def test_tsquery_cannot_be_injected_and_prefixes_long_terms():
    assert tsquery("evasão escolar") == "evasao:* | escolar:*"
    q = tsquery("a'; DROP TABLE x; -- (foo | bar) !baz & qux:*")
    assert set(q) <= set("abcdefghijklmnopqrstuvwxyz0123456789 |:*")
    assert tsquery("de a o") is None


def test_bm25_is_accent_insensitive_and_prefix_matching():
    cs = [{"id": "1", "search_text": fold("A evasão escolar cresce"), "x": 1},
          {"id": "2", "search_text": fold("Inflação e juros"), "x": 2}]
    ranked = bm25_rank("evasao", cs)
    assert [c["id"] for c, _ in ranked] == ["1"]
    assert [c["id"] for c, _ in bm25_rank("evas", cs)] == ["1"]  # 4+ chars match as a prefix
    assert bm25_rank("eva", cs) == []  # shorter terms match whole words only
    assert [c["id"] for c, _ in bm25_rank("evasoes escolares", cs)] == []  # no stemming promised
    assert [c["id"] for c, _ in bm25_rank("escolar", cs)] == ["1"]


def test_rrf_and_snippet():
    fused = rrf({"keyword": ["a", "b", "c"], "semantic": ["c", "a", "d"]})
    assert [i for i, _, _ in fused][:2] == ["a", "c"]
    assert dict((i, m) for i, _, m in fused)["a"] == ["keyword", "semantic"]
    text = ("palavra " * 100) + "EVASÃO aqui no meio " + ("outra " * 100)
    s = snippet(text, "evasão")
    assert "EVASÃO" in s and s.startswith("…") and s.endswith("…") and len(s) < 400


# ----------------------------------------------------------------------------- clients
def test_gemini_embed_batches_normalises_retries_and_checks_shape():
    calls = []

    def transport(url, headers, body):
        import json

        req = json.loads(body)["requests"]
        calls.append((url, req[0]["taskType"], len(req)))
        if len(calls) == 2:  # first retry-able failure
            raise urllib.error.HTTPError(url, 503, "busy", {}, None)
        return json.dumps({"embeddings": [{"values": [3.0, 4.0] + [0.0] * 6} for _ in req]})

    g = GeminiClient(api_key="k", transport=transport, sleep=lambda s: None)
    g.embed_dim = 8
    out = g.embed([f"t{i}" for i in range(120)], task="query")
    assert len(out) == 120 and out[0][:2] == [0.6, 0.8]  # unit length
    assert [c[2] for c in calls] == [50, 50, 50, 20] and all(c[1] == "RETRIEVAL_QUERY" for c in calls)
    assert "batchEmbedContents" in calls[0][0]

    bad = GeminiClient(api_key="k", transport=lambda u, h, b: '{"embeddings": [{"values": [1.0]}]}', sleep=lambda s: None)
    with pytest.raises(LLMError):
        bad.embed(["x"])


def test_gateway_embed_uses_circuit_breaker_and_reports_capability():
    gw = LLMGateway(NoEmbedLLM())
    assert gw.can_embed is False
    with pytest.raises(LLMUnavailable):
        gw.embed(["x"])
    down = FakeLLM(embed_ok=False)
    gw = LLMGateway(down, failure_threshold=2, cooldown_seconds=60)
    assert gw.can_embed and gw.embed_model == "fake-embed"
    for _ in range(2):
        with pytest.raises(LLMUnavailable):
            gw.embed(["x"])
    before = down.embed_calls
    with pytest.raises(LLMUnavailable):
        gw.embed(["x"])
    assert down.embed_calls == before and gw.can_embed is False  # circuit open: no provider call


# ----------------------------------------------------------------------------- pipeline + API
def test_upload_indexes_embeds_and_hybrid_search_finds_synonyms(env, tmp_path):
    c, repo, h, pid, *_ = env
    did = upload(c, h, pid, tmp_path)
    doc = repo.get_document(did)
    assert doc["status"] == "extracted" and doc["stage"] is None
    stats = c.get(f"/projects/{pid}/search?q=evasao", headers=h).json()["coverage"]
    assert stats["chunks"] == 3 and stats["embedded"] == 3

    # exact words -> both rankers agree
    r = c.get(f"/projects/{pid}/search?q=entrevistas qualitativas", headers=h).json()
    assert r["mode"] == "hybrid" and r["notice"] is None
    top = r["results"][0]
    assert top["page_no"] == 2 and top["document_id"] == did and top["matched_by"] == ["keyword", "semantic"]
    assert top["cite"] == "(Estudo, s.d., p. 2)"  # manual upload: no authors/year, same fallback the drafts use
    assert "entrevistas" in top["snippet"] and top["document_title"] == "Estudo sobre evasão"

    # a synonym that appears nowhere in the text: only the semantic ranker can find it
    r = c.get(f"/projects/{pid}/search?q=abandono", headers=h).json()
    assert r["mode"] == "hybrid"
    assert r["results"][0]["page_no"] == 1 and r["results"][0]["matched_by"] == ["semantic"]

    # accent-insensitive keyword
    r = c.get(f"/projects/{pid}/search?q=inflacao", headers=h).json()
    assert r["results"][0]["page_no"] == 3 and "keyword" in r["results"][0]["matched_by"]


def test_search_validation_and_scoping(env, tmp_path):
    c, repo, h, pid, *_ = env
    upload(c, h, pid, tmp_path)
    assert c.get(f"/projects/{pid}/search?q=a", headers=h).status_code == 422
    assert c.get(f"/projects/{pid}/search?q=de a o", headers=h).status_code == 422
    assert c.get(f"/projects/{pid}/search?q=evasao").status_code in (401, 403)
    t2 = c.post("/auth/register", json={"email": "b@usp.br", "password": "password123", "name": "B"}).json()["token"]
    h2 = {"Authorization": f"Bearer {t2}"}
    assert c.get(f"/projects/{pid}/search?q=evasao", headers=h2).status_code == 404
    pid2 = c.post("/projects", json={"title": "Outro projeto", "work": "tcc", "citation_style": "abnt"}, headers=h2).json()["id"]
    assert c.get(f"/projects/{pid2}/search?q=evasao", headers=h2).json()["results"] == []  # nothing leaks across projects
    assert len(c.get(f"/projects/{pid}/search?q=evasao&limit=1", headers=h).json()["results"]) == 1


def test_embed_failure_is_not_fatal_and_reindex_finishes_the_job(env, tmp_path):
    c, repo, h, pid, storage, holder, app = env
    holder["llm"].embed_ok = False
    did = upload(c, h, pid, tmp_path)
    assert repo.get_document(did)["status"] == "extracted"  # extraction still ran
    r = c.get(f"/projects/{pid}/search?q=evasao", headers=h).json()
    assert r["mode"] == "keyword" and r["notice"] and r["results"][0]["page_no"] == 1
    assert r["coverage"] == {"chunks": 3, "embedded": 0}

    holder["llm"].embed_ok = True
    assert c.post(f"/projects/{pid}/library/reindex", headers=h).json() == {"queued": 1}
    r = c.get(f"/projects/{pid}/search?q=abandono", headers=h).json()
    assert r["mode"] == "hybrid" and r["coverage"]["embedded"] == 3 and r["results"][0]["page_no"] == 1
    n = holder["llm"].embed_calls
    c.post(f"/projects/{pid}/library/reindex", headers=h)  # idempotent: no duplicate chunks
    assert c.get(f"/projects/{pid}/search?q=evasao", headers=h).json()["coverage"]["chunks"] == 3
    assert holder["llm"].embed_calls >= n


def test_query_embedding_outage_degrades_to_keyword(env, tmp_path):
    c, repo, h, pid, storage, holder, app = env
    upload(c, h, pid, tmp_path)
    holder["llm"].embed_ok = False
    r = c.get(f"/projects/{pid}/search?q=evasao", headers=h).json()
    assert r["mode"] == "keyword" and "indisponível" in r["notice"] and r["results"]


def test_keyword_search_works_without_any_llm(request, tmp_path, monkeypatch):
    for kind in ("memory", "postgres"):
        request.param = kind
        if kind == "postgres" and not PG_OK:
            continue
        c, repo, h, pid, storage, holder, app = build(request, tmp_path / kind, monkeypatch, None)
        did = upload(c, h, pid, tmp_path)
        assert repo.get_document(did)["status"] == "parsed" and repo.get_document(did)["stage"] is None
        r = c.get(f"/projects/{pid}/search?q=entrevistas", headers=h).json()
        assert r["mode"] == "keyword" and "embeddings" in r["notice"] and r["results"][0]["page_no"] == 2
        caps = c.get("/capabilities").json()["features"]
        assert caps["search"] == "keyword" and caps["summaries"] == "unavailable"


def test_llm_without_embeddings_keeps_keyword_mode(request, tmp_path, monkeypatch):
    request.param = "memory"
    c, repo, h, pid, *_ = build(request, tmp_path, monkeypatch, NoEmbedLLM())
    upload(c, h, pid, tmp_path)
    r = c.get(f"/projects/{pid}/search?q=evasao", headers=h).json()
    assert r["mode"] == "keyword" and r["results"][0]["page_no"] == 1
    assert c.get("/capabilities").json()["features"]["search"] == "keyword"


def test_deleting_a_document_removes_it_from_search(env, tmp_path):
    c, repo, h, pid, *_ = env
    did = upload(c, h, pid, tmp_path)
    assert c.get(f"/projects/{pid}/search?q=evasao", headers=h).json()["results"]
    c.delete(f"/projects/{pid}/documents/{did}", headers=h)
    r = c.get(f"/projects/{pid}/search?q=evasao", headers=h).json()
    assert r["results"] == [] and r["coverage"]["chunks"] == 0


def test_reindex_is_owner_only(env, tmp_path):
    c, repo, h, pid, *_ = env
    t2 = c.post("/auth/register", json={"email": "b@usp.br", "password": "password123", "name": "B"}).json()["token"]
    assert c.post(f"/projects/{pid}/library/reindex", headers={"Authorization": f"Bearer {t2}"}).status_code == 404


# ----------------------------------------------------------------------------- summaries
def test_summary_by_blocks_is_labelled_and_idempotent(env, tmp_path, monkeypatch):
    c, repo, h, pid, storage, holder, app = env
    monkeypatch.setattr(jobs, "SUMMARIZE_ENABLED", True)
    pages = [f"Conteúdo da página {i} sobre a evasão escolar e suas causas sociais, com texto suficiente." for i in range(1, 31)]
    did = upload(c, h, pid, tmp_path, pages=pages)
    s = repo.get_document(did)["summary"]
    assert s["ai_generated"] is True and s["model"] == "fake-llm"
    assert [(x["page_start"], x["page_end"]) for x in s["sections"]] == [(1, 12), (13, 24), (25, 30)]
    assert holder["llm"].summary_calls == 4 and s["overview"].startswith("Resumo #4")  # 3 blocks + overview
    assert c.get(f"/projects/{pid}/documents", headers=h).json()[0]["summary"]["overview"] == s["overview"]
    c.post(f"/projects/{pid}/library/reindex", headers=h)
    assert holder["llm"].summary_calls == 4  # already summarised: no new cost
    assert any(u["action"] == "summarize" for u in repo.list_ai_usage(pid))


def test_summary_failure_is_not_fatal(env, tmp_path, monkeypatch):
    c, repo, h, pid, storage, holder, app = env
    monkeypatch.setattr(jobs, "SUMMARIZE_ENABLED", True)
    holder["llm"].summary_ok = False
    did = upload(c, h, pid, tmp_path)
    d = repo.get_document(did)
    assert d["status"] == "extracted" and not d.get("summary") and d["stage"] is None


# ----------------------------------------------------------------------------- text cleaning before indexing
def _book(n=12):
    topics = ["economia", "geologia", "música", "navegação", "teologia", "agricultura", "retórica", "medicina", "astronomia",
              "arquitetura", "culinária", "cartografia"]
    return [f"h i st ó r i a da l i t erat u ra | autor {i}\nCorpo da página {i}: um trecho sobre {topics[i - 1]} e as suas "
            f"controvérsias, escrito com palavras próprias para esta página específica número {i}.\n4 • Livro - sol.indd   {i}\n"
            f"02/10/14   17:10" for i in range(1, n + 1)]


def test_running_headers_and_footers_are_removed_from_the_index():
    from app.search import clean_pages

    out = clean_pages(_book())
    assert all("h i st" not in p and "sol.indd" not in p and "02/10/14" not in p for p in out)
    assert "Corpo da página 3" in out[2]


def test_small_documents_keep_their_first_and_last_lines():
    from app.search import clean_pages

    pages = ["Título repetido\ncorpo um\nfim", "Título repetido\ncorpo dois\nfim"]
    assert clean_pages(pages) == pages  # too few pages to call anything boilerplate


def test_soft_hyphens_and_line_hyphens_rejoin_words():
    from app.search import clean_pages

    out = clean_pages(["A mentali­\ndade da ­ época e o desen-\nvolvimento do país."])[0]
    assert "mentalidade" in out and "desenvolvimento" in out and "época" in out
    assert "­" not in out


def test_real_hyphen_before_a_capital_or_digit_is_kept():
    from app.search import clean_pages

    assert clean_pages(["Rio-\nSão Paulo e covid-\n19"])[0] == "Rio-\nSão Paulo e covid-\n19"


def test_broken_words_are_now_searchable():
    pages = _book() + ["A mentali­\ndade romântica do século influenciou a produção literária inteira daquele período histórico."]
    chunks = chunk_pages(pages)
    hit = [c for c, _ in bm25_rank("mentalidade romântica", chunks)]
    assert hit and hit[0]["page_no"] == 13


def test_default_chunks_fit_the_small_embedding_window():
    page = " ".join(f"Frase número {i} sobre capital humano e crescimento econômico no Brasil." for i in range(80))
    from app import search

    chunks = search.chunk_pages([page])
    assert len(chunks) > 5
    assert max(len(c["text"]) for c in chunks) <= search.CHUNK_MAX_CHARS + search.CHUNK_OVERLAP_CHARS
    assert search.CHUNK_MAX_CHARS <= 700  # ~128 tokens: anything longer is truncated by the default model
