"""Local embeddings: the default provider, with a fake ONNX model (no download, no network)."""
import os
import sys
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import embeddings  # noqa: E402
from app.jobs import InlineQueue  # noqa: E402
from app.llm_gateway import LLMUnavailable  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402
from app.search import tokens  # noqa: E402

GROUPS = [{"evasao", "abandono", "desistencia"}, {"inflacao", "precos"}]


class _Vec(list):
    def tolist(self):
        return list(self)


class FakeOnnxModel:
    """Stands in for fastembed.TextEmbedding: synonyms land on the same axis, unnormalised like a raw model."""

    def __init__(self):
        self.seen: list[str] = []

    def embed(self, texts, batch_size=16):
        for t in texts:
            self.seen.append(t)
            v = [0.0] * (len(GROUPS) + 4)
            for tok in tokens(t.split(": ", 1)[-1]):
                hit = next((i for i, g in enumerate(GROUPS) if tok in g), None)
                if hit is not None:
                    v[hit] += 3.0
                else:
                    v[len(GROUPS) + sum(map(ord, tok)) % 4] += 0.1
            yield _Vec(v)


@pytest.fixture
def local(monkeypatch):
    monkeypatch.setenv("EMBED_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_EMBED_MODEL", "intfloat/multilingual-e5-test")
    monkeypatch.setattr(embeddings, "_fastembed_installed", lambda: True)
    monkeypatch.setattr(embeddings, "_local", None)
    emb = embeddings.resolve(None)
    emb._model = FakeOnnxModel()
    return emb


def test_default_provider_is_local(monkeypatch):
    monkeypatch.delenv("EMBED_PROVIDER", raising=False)
    assert embeddings.provider() == "local"


def test_resolve_by_provider(monkeypatch):
    class Client:
        can_embed = True
        embed_model = "gemini-embedding-001"

    monkeypatch.setattr(embeddings, "_fastembed_installed", lambda: True)
    monkeypatch.setenv("EMBED_PROVIDER", "gemini")
    assert embeddings.resolve(Client()).embed_model == "gemini-embedding-001"
    assert embeddings.resolve(None) is None
    monkeypatch.setenv("EMBED_PROVIDER", "none")
    assert embeddings.resolve(Client()) is None
    monkeypatch.setenv("EMBED_PROVIDER", "local")
    assert embeddings.resolve(Client()).embed_model.startswith("local:")  # the client is ignored in local mode
    monkeypatch.setattr(embeddings, "_fastembed_installed", lambda: False)
    assert embeddings.resolve(Client()) is None  # honest: no package, no semantic search


def test_vectors_are_unit_length_and_e5_prefixes_are_applied(local):
    docs = local.embed(["evasão escolar"], task="document")
    query = local.embed(["abandono"], task="query")
    assert local._model.seen == ["passage: evasão escolar", "query: abandono"]
    for v in docs + query:
        assert abs(sum(x * x for x in v) ** 0.5 - 1.0) < 1e-9
    assert sum(a * b for a, b in zip(docs[0], query[0])) > 0.9  # synonyms are close


def test_non_e5_models_get_no_prefix(monkeypatch):
    emb = embeddings.LocalEmbedder("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    emb._model = FakeOnnxModel()
    emb.embed(["texto"], task="query")
    assert emb._model.seen == ["texto"]


def test_model_failure_becomes_llm_unavailable(monkeypatch):
    emb = embeddings.LocalEmbedder("x/e5")

    class Broken:
        def embed(self, *a, **k):
            raise RuntimeError("onnx exploded")

    emb._model = Broken()
    with pytest.raises(LLMUnavailable):
        emb.embed(["a"])
    assert emb.embed([]) == []


def test_model_name_identifies_the_vector_space(local):
    assert local.embed_model == "local:intfloat/multilingual-e5-test"


# ----------------------------------------------------------------------------- end to end, no LLM at all
def _pdf(path: Path, pages: list[str]) -> bytes:
    d = pymupdf.open()
    for t in pages:
        d.new_page().insert_textbox(pymupdf.Rect(50, 50, 545, 790), t, fontsize=11)
    d.save(path)
    return path.read_bytes()


PAGES = [
    "A desistência dos estudantes no ensino médio cresce quando a renda familiar cai, segundo diversos estudos "
    "recentes sobre trajetórias escolares em regiões metropolitanas do país.",
    "O poder de compra das famílias depende do nível geral de preços e do crédito disponível para o consumo "
    "de bens duráveis ao longo do ciclo econômico.",
]


def _app(tmp_path):
    repo, st = InMemoryRepo(), tmp_path / "st"
    fac = lambda: None  # noqa: E731  - no LLM configured at all
    app = create_app(repo=repo, storage_dir=st, llm_factory=fac, client=None, job_queue=InlineQueue(repo, st, fac))
    c = TestClient(app)
    tok = c.post("/auth/register", json={"email": "a@usp.br", "password": "password123", "name": "Ana"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = c.post("/projects", json={"title": "Projeto Local", "work": "tcc", "citation_style": "abnt"}, headers=h).json()["id"]
    return c, repo, h, pid


def test_semantic_search_works_with_no_llm_and_no_internet(local, tmp_path):
    c, repo, h, pid = _app(tmp_path)
    pdf = _pdf(tmp_path / "d.pdf", PAGES)
    r = c.post(f"/projects/{pid}/documents/upload", headers=h, data={"title": "Estudo"},
               files={"file": ("d.pdf", pdf, "application/pdf")})
    assert r.status_code in (200, 201), r.text
    assert c.get("/capabilities").json()["features"]["search"] == "hybrid"
    res = c.get(f"/projects/{pid}/search", params={"q": "abandono"}, headers=h).json()
    assert res["mode"] == "hybrid" and res["notice"] is None
    top = res["results"][0]
    assert top["page_no"] == 1 and "semantic" in top["matched_by"]  # "abandono" never appears in the text
    assert res["coverage"]["embedded"] == res["coverage"]["chunks"] > 0


def test_switching_model_does_not_mix_vector_spaces(local, tmp_path, monkeypatch):
    c, repo, h, pid = _app(tmp_path)
    pdf = _pdf(tmp_path / "d.pdf", PAGES)
    c.post(f"/projects/{pid}/documents/upload", headers=h, data={"title": "Estudo"},
           files={"file": ("d.pdf", pdf, "application/pdf")})
    monkeypatch.setenv("LOCAL_EMBED_MODEL", "intfloat/multilingual-e5-other")
    embeddings.resolve(None)._model = FakeOnnxModel()
    res = c.get(f"/projects/{pid}/search", params={"q": "abandono"}, headers=h).json()
    assert res["mode"] == "keyword" and res["results"] == []  # nothing embedded with the new model yet
    assert "indexados" in res["notice"]
    assert c.post(f"/projects/{pid}/library/reindex", headers=h).status_code == 202
    res = c.get(f"/projects/{pid}/search", params={"q": "abandono"}, headers=h).json()
    assert res["mode"] == "hybrid" and res["results"][0]["page_no"] == 1


def test_provider_none_is_keyword_only(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBED_PROVIDER", "none")
    c, repo, h, pid = _app(tmp_path)
    assert c.get("/capabilities").json()["features"]["search"] == "keyword"


@pytest.mark.skipif(os.environ.get("RUN_REAL_EMBED_TEST") != "1", reason="loads the real model (~2 GB download once)")
def test_real_model_smoke():
    """Run on your computer: RUN_REAL_EMBED_TEST=1 EMBED_PROVIDER=local pytest tests/test_local_embeddings.py -k real"""
    os.environ["EMBED_PROVIDER"] = "local"
    emb = embeddings.resolve(None)
    d = emb.embed(["A evasão escolar aumenta quando a renda familiar diminui.",
                   "O banco central ajustou a taxa de juros para conter a inflação."], task="document")
    q = emb.embed(["abandono dos estudos por falta de dinheiro"], task="query")[0]
    sim = [sum(a * b for a, b in zip(v, q)) for v in d]
    assert sim[0] > sim[1], sim


@pytest.mark.skipif(os.environ.get("RUN_REAL_EMBED_TEST") != "1", reason="loads the real model (~2 GB download once)")
def test_real_model_paraphrase_calibration(capsys):
    """Prints the similarities your model gives, to calibrate PARAPHRASE_MIN_SIMILARITY on this computer."""
    from tests.test_paraphrase import AI_DRAFT, INDEPENDENT, PARAPHRASE

    os.environ["EMBED_PROVIDER"] = "local"
    emb = embeddings.resolve(None)
    d, p, i = emb.embed([AI_DRAFT, PARAPHRASE, INDEPENDENT], task="document")
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))  # noqa: E731
    with capsys.disabled():
        print(f"\nparáfrase~rascunho={dot(d, p):.3f}  independente~rascunho={dot(d, i):.3f}  (limite atual {os.environ.get('PARAPHRASE_MIN_SIMILARITY', '0.62')})")
    assert dot(d, p) > dot(d, i) + 0.03
