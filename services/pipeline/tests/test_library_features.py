"""Library + editor features the UI calls: delete reference, import pasted reference, citation consistency,
bibliography export, comment resolve, section restore points, advisor feedback on tree nodes.

Every API test runs against InMemoryRepo, and against a real Postgres too when TEST_DATABASE_URL is set
(database name must contain "test": the fixture truncates tables).
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import repo as repo_mod  # noqa: E402
from app.bibliography import export_bibliography, parse_citation  # noqa: E402
from app.consistency import find_citations  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402

DSN = os.environ.get("TEST_DATABASE_URL")
_DB_NAME = (DSN or "").rsplit("/", 1)[-1].split("?")[0].lower()
PG_OK = bool(DSN) and "test" in _DB_NAME

CROSSREF = {
    "message": {
        "title": ["Deep learning for crop monitoring"],
        "author": [{"given": "Ana", "family": "Moran"}, {"given": "Bruno", "family": "da Silva"}],
        "issued": {"date-parts": [[2021]]},
        "container-title": ["Revista de Agricultura Digital"],
    }
}


def fake_fetch(url):
    if "crossref" in url and "10.1234/abc" in url:
        return CROSSREF
    from app.metadata import NotFound

    raise NotFound(url)


@pytest.fixture(params=["memory", "postgres"])
def env(request, tmp_path, monkeypatch):
    if request.param == "postgres":
        if not PG_OK:
            pytest.skip("TEST_DATABASE_URL not set to a *test* database")
        import psycopg

        monkeypatch.setenv("JOB_WORKER", "external")  # no embedded worker thread in the API under test
        with psycopg.connect(DSN) as c:
            c.execute("TRUNCATE users CASCADE")
        repo = repo_mod.PostgresRepo(DSN)
    else:
        repo = InMemoryRepo()
    app = create_app(repo=repo, storage_dir=tmp_path / "st", fetch_json=fake_fetch)
    c = TestClient(app)
    token = c.post("/auth/register", json={"email": "aluna@usp.br", "password": "password123", "name": "Aluna"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    p = c.post("/projects", json={"title": "TCC Biblioteca", "work": "tcc", "citation_style": "abnt"}, headers=h).json()
    return c, repo, h, p["id"], tmp_path / "st"


def other_user(c, email="outro@usp.br"):
    t = c.post("/auth/register", json={"email": email, "password": "password123", "name": "Outro"}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


# ----------------------------------------------------------------------------- pure functions
def test_find_citations_both_shapes_and_multi():
    text = "Como mostram (Moran, 2015, p. 12; Silva, 2020) e também Souza e Lima (2018), além de Costa et al. (2019). Veja (MORAN; SILVA, 2021)."
    got = {(w.split()[-1].lower(), y) for w, y in find_citations(text)}
    assert ("moran", 2015) in got and ("silva", 2020) in got and ("lima", 2018) in got
    assert ("al.", 2019) in got or any(y == 2019 for _, y in find_citations(text))
    assert ("silva", 2021) in got


def test_parse_citation_abnt_apa_and_doi():
    abnt = parse_citation("SILVA, Maria J.; SOUZA, Carlos de. Redes neurais na agricultura. Revista Agro, v. 3, n. 2, p. 10-20, 2019.")
    assert abnt["title"] == "Redes neurais na agricultura"
    assert abnt["authors"] == ["Maria J. Silva", "Carlos de Souza"] or abnt["authors"][0] == "Maria J. Silva"
    assert abnt["year"] == 2019 and abnt["venue"] == "Revista Agro"
    assert abnt["metadata_source"] == "manual" and abnt["doi"] is None

    apa = parse_citation("Moran, A. (2015). Soil moisture sensing. Journal of Soil Science. DOI: 10.1000/xyz123")
    assert apa["title"] == "Soil moisture sensing" and apa["year"] == 2015 and apa["doi"] == "10.1000/xyz123"
    assert apa["authors"] and "Moran" in apa["authors"][0]

    with pytest.raises(ValueError):
        parse_citation("2019")


def test_export_formats_cover_all_styles():
    docs = [
        {"id": "1", "title": "Zeta study", "authors": ["Ana Moran", "Bruno da Silva"], "year": 2021, "venue": "Rev X", "doi": "10.1/z"},
        {"id": "2", "title": "Alpha study", "authors": ["Carla Álvares"], "year": 2019, "venue": None, "doi": None},
    ]
    abnt, ext, _ = export_bibliography(docs, "abnt")
    assert ext == "txt"
    assert abnt.index("ÁLVARES") < abnt.index("MORAN")  # alphabetical, accent-insensitive
    assert "MORAN, Ana; SILVA, Bruno da." in abnt and "https://doi.org/10.1/z" in abnt
    apa, _, _ = export_bibliography(docs, "apa")
    assert "Moran, A., & da Silva, B. (2021)." in apa or "Moran, A., & Silva, B. (2021)." in apa
    van, _, _ = export_bibliography(docs, "vancouver")
    assert van.startswith("1. Moran A") and "doi:10.1/z" in van
    for style in ("chicago", "mla"):
        txt, _, _ = export_bibliography(docs, style)
        assert "Zeta study" in txt and "Álvares" in txt
    bib, ext, _ = export_bibliography(docs, "bibtex")
    assert ext == "bib" and "@article{moran2021," in bib and "@misc{alvares2019," in bib
    with pytest.raises(ValueError):
        export_bibliography(docs, "harvard")


# ----------------------------------------------------------------------------- library
def test_import_citation_manual_and_doi_and_duplicates(env):
    c, repo, h, pid, _ = env
    url = f"/projects/{pid}/documents/import-citation"
    r = c.post(url, json={"raw_citation": "SILVA, Maria. Redes neurais na agricultura. Revista Agro, 2019.", "citation_style": "abnt"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["title"] == "Redes neurais na agricultura"
    assert c.post(url, json={"raw_citation": "SILVA, Maria. Redes neurais na agricultura. Revista Agro, 2019."}, headers=h).status_code == 409

    # a DOI is resolved against the (fake) Crossref and wins over the pasted text
    r = c.post(url, json={"raw_citation": "texto qualquer. Algum título errado. doi:10.1234/abc"}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "Deep learning for crop monitoring" and body["metadata_source"] == "crossref"
    assert c.post(url, json={"raw_citation": "doi:10.1234/abc"}, headers=h).status_code in (409, 422)

    # a DOI no base knows still imports what the text says
    r = c.post(url, json={"raw_citation": "Moran, A. (2015). Soil moisture sensing. Journal. 10.9999/nope"}, headers=h)
    assert r.status_code == 201 and r.json()["doi"] == "10.9999/nope"

    assert c.post(url, json={"raw_citation": "2019 2020 2021"}, headers=h).status_code == 422
    assert len(c.get(f"/projects/{pid}/documents", headers=h).json()) == 3
    assert c.post(url, json={"raw_citation": "SILVA, M. Outro título qualquer. 2019."}, headers=other_user(c)).status_code == 404


def test_delete_document_removes_file_and_is_scoped(env):
    c, repo, h, pid, storage = env
    pdf = storage.parent / "x.pdf"
    import pymupdf

    d = pymupdf.open()
    d.new_page().insert_text((72, 72), "Texto de teste. " * 30)
    d.save(pdf)
    r = c.post(f"/projects/{pid}/documents/upload", files={"file": ("x.pdf", pdf.read_bytes(), "application/pdf")},
               data={"title": "Meu PDF"}, headers=h)
    assert r.status_code == 201, r.text
    doc = r.json()
    stored = storage / repo.get_document(doc["id"])["storage_path"]
    assert stored.exists()

    assert c.delete(f"/projects/{pid}/documents/{doc['id']}", headers=other_user(c)).status_code == 404
    assert stored.exists()
    assert c.delete(f"/projects/{pid}/documents/{doc['id']}", headers=h).json() == {"ok": True}
    assert not stored.exists()
    assert repo.get_document(doc["id"]) is None
    assert c.delete(f"/projects/{pid}/documents/{doc['id']}", headers=h).status_code == 404


def test_delete_document_drops_its_claims(env):
    c, repo, h, pid, _ = env
    doc = repo.create_document(pid, {"title": "Fonte", "authors": ["Ana Moran"], "year": 2020, "doi": None,
                                     "storage_path": None, "analysis": "full_text", "status": "extracted"})
    repo.add_claims(doc["id"], [{"concept": "umidade", "statement": "s", "quote": "q", "page_verified": 1,
                                 "quote_verified": True, "verify_method": "exact"}], "m", "v")
    assert repo.list_project_claims(pid)
    assert c.delete(f"/projects/{pid}/documents/{doc['id']}", headers=h).status_code == 200
    assert repo.list_project_claims(pid) == []


def test_consistency_report(env):
    c, repo, h, pid, _ = env
    moran = repo.create_document(pid, {"title": "Soil", "authors": ["Ana Moran"], "year": 2015, "doi": "10.1/a",
                                       "storage_path": None, "analysis": "abstract_only", "status": "pending"})
    unused = repo.create_document(pid, {"title": "Nunca citado", "authors": ["Bia Costa"], "year": 2018, "doi": None,
                                        "storage_path": None, "analysis": "abstract_only", "status": "pending"})
    secs = c.get(f"/projects/{pid}/sections", headers=h).json()
    intro = secs[0]
    text = "Segundo (Moran, 2015, p. 4) o solo retém água. Porém (Fantasma, 2001) nada existe. E Moran (2020) está com o ano errado."
    c.patch(f"/projects/{pid}/sections/{intro['id']}", headers=h,
            json={"content": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}})
    rep = c.get(f"/projects/{pid}/consistency", headers=h).json()
    kinds = [(i["type"], i.get("section_title") or i.get("document_title")) for i in rep["issues"]]
    missing = [i for i in rep["issues"] if i["type"] == "citacao_sem_referencia"]
    assert len(missing) == 2 and all(i["severity"] == "error" and i["section_id"] == intro["id"] for i in missing)
    assert any("Fantasma" in i["message"] for i in missing) and any("2020" in i["message"] for i in missing)
    assert [i["document_id"] for i in rep["issues"] if i["type"] == "referencia_nao_citada"] == [unused["id"]]
    assert rep["cited_document_ids"] == [moran["id"]] and rep["uncited_document_ids"] == [unused["id"]]
    assert rep["total_documents"] == 2 and rep["total_sections"] == len(secs) and rep["ok"] is False, kinds

    # fix: remove the bad citations, cite the other reference -> consistent
    fixed = "Segundo (Moran, 2015, p. 4) o solo retém água, como já dizia Costa (2018)."
    c.patch(f"/projects/{pid}/sections/{intro['id']}", headers=h,
            json={"content": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": fixed}]}]}})
    rep = c.get(f"/projects/{pid}/consistency", headers=h).json()
    assert rep["issues"] == [] and rep["ok"] is True and rep["uncited_document_ids"] == []


def test_consistency_ignores_reference_section_and_flags_duplicate_doi(env):
    c, repo, h, pid, _ = env
    repo.create_document(pid, {"title": "A", "authors": ["Ana Moran"], "year": 2015, "doi": "10.1/dup",
                               "storage_path": None, "analysis": "abstract_only", "status": "pending"})
    repo.create_document(pid, {"title": "B", "authors": ["Ana Moran"], "year": 2016, "doi": None,
                               "storage_path": None, "analysis": "abstract_only", "status": "pending"})
    repo.update_document(next(d for d in repo.list_documents(pid) if d["title"] == "B")["id"], status="pending")
    if isinstance(repo, InMemoryRepo):  # Postgres refuses duplicate DOIs by constraint; memory can be forced via case
        next(d for d in repo.documents.values() if d["title"] == "B")["doi"] = "https://doi.org/10.1/DUP"
        types = [i["type"] for i in c.get(f"/projects/{pid}/consistency", headers=h).json()["issues"]]
        assert "doi_duplicado" in types
    secs = c.get(f"/projects/{pid}/sections", headers=h).json()
    refs = next(s for s in secs if "efer" in s["title"])
    c.patch(f"/projects/{pid}/sections/{refs['id']}", headers=h, json={"content": {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "ZZZ, Fulano. Obra (1999). Algo."}]}]}})
    assert not [i for i in c.get(f"/projects/{pid}/consistency", headers=h).json()["issues"]
                if i["type"] == "citacao_sem_referencia"]


def test_export_bibliography_endpoint(env):
    c, repo, h, pid, _ = env
    c.post(f"/projects/{pid}/documents/doi", json={"doi": "10.1234/abc"}, headers=h)
    r = c.get(f"/projects/{pid}/export/bibliography?format=abnt", headers=h)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert "MORAN, Ana" in r.text and r.headers["content-type"].startswith("text/plain")
    r = c.get(f"/projects/{pid}/export/bibliography?format=bibtex", headers=h)
    assert r.text.startswith("@article{moran2021,") and ".bib" in r.headers["content-disposition"]
    assert c.get(f"/projects/{pid}/export/bibliography?format=nope", headers=h).status_code == 422
    assert c.get(f"/projects/{pid}/export/bibliography", headers=other_user(c)).status_code == 404
    assert c.get(f"/projects/{pid}/export/bibliography").status_code in (401, 403)


# ----------------------------------------------------------------------------- comments
def test_resolve_comment_and_project_scoping(env):
    c, repo, h, pid, _ = env
    sec = c.get(f"/projects/{pid}/sections", headers=h).json()[0]
    com = c.post(f"/projects/{pid}/sections/{sec['id']}/comments", json={"content": "Revise isto"}, headers=h).json()
    assert com["resolved"] is False
    r = c.post(f"/projects/{pid}/sections/{sec['id']}/comments/{com['id']}/resolve", headers=h)
    assert r.status_code == 200 and r.json()["resolved"] is True and r.json()["id"] == com["id"]
    assert c.get(f"/projects/{pid}/sections/{sec['id']}/comments", headers=h).json()[0]["resolved"] is True

    # a stranger with their own project must not touch this project's comment by guessing ids
    ho = other_user(c)
    po = c.post("/projects", json={"title": "Projeto do outro", "work": "tcc", "citation_style": "abnt"}, headers=ho).json()["id"]
    sec_o = c.get(f"/projects/{po}/sections", headers=ho).json()[0]
    for method, suffix in (("post", "/resolve"), ("patch", ""), ("delete", "")):
        r = getattr(c, method)(f"/projects/{po}/sections/{sec_o['id']}/comments/{com['id']}{suffix}", headers=ho,
                               **({"json": {"resolved": False}} if method == "patch" else {}))
        assert r.status_code == 404, (method, r.text)
    assert c.post(f"/projects/{po}/sections/{sec['id']}/comments", json={"content": "x"}, headers=ho).status_code == 404
    assert c.get(f"/projects/{pid}/sections/{sec['id']}/comments", headers=h).json()[0]["resolved"] is True
    assert c.post(f"/projects/{pid}/sections/{sec['id']}/comments/{com['id']}/resolve", headers=ho).status_code == 404


# ----------------------------------------------------------------------------- versions
def doc_with(text):
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


def test_versions_snapshot_restore_and_authorship_kept(env, monkeypatch):
    c, repo, h, pid, _ = env
    monkeypatch.setattr(repo_mod, "VERSION_MIN_INTERVAL_SECONDS", 0)  # every change is a restore point
    sec = c.get(f"/projects/{pid}/sections", headers=h).json()[0]
    sid = sec["id"]
    url = f"/projects/{pid}/sections/{sid}"
    assert c.get(f"{url}/versions", headers=h).json() == []

    c.patch(url, headers=h, json={"content": doc_with("primeira versão do texto")})
    assert c.get(f"{url}/versions", headers=h).json() == []  # nothing existed before: no restore point yet
    c.patch(url, headers=h, json={"content": doc_with("segunda versão do texto aqui")})
    c.patch(url, headers=h, json={"content": doc_with("segunda versão do texto aqui")})  # identical: ignored
    c.patch(url, headers=h, json={"content": doc_with("terceira versão final")})
    versions = c.get(f"{url}/versions", headers=h).json()
    assert [v["word_count"] for v in versions] == [5, 4]  # newest first
    assert versions[0]["content_snapshot"]["content"][0]["content"][0]["text"] == "segunda versão do texto aqui"
    assert versions[0]["created_by"] == "aluna@usp.br" and versions[0]["section_id"] == sid

    oldest = versions[1]
    r = c.post(f"{url}/versions/{oldest['id']}/restore", headers=h)
    assert r.status_code == 200
    assert r.json()["content"]["content"][0]["content"][0]["text"] == "primeira versão do texto"
    after = c.get(f"{url}/versions", headers=h).json()
    assert after[0]["created_by"] == "restore"  # the content that was replaced is itself recoverable
    assert after[0]["content_snapshot"]["content"][0]["content"][0]["text"] == "terceira versão final"

    # the undo works
    c.post(f"{url}/versions/{after[0]['id']}/restore", headers=h)
    assert repo.get_section(pid, sid)["content"]["content"][0]["content"][0]["text"] == "terceira versão final"

    assert c.post(f"{url}/versions/00000000-0000-0000-0000-000000000000/restore", headers=h).status_code == 404
    assert c.post(f"{url}/versions/nao-e-uuid/restore", headers=h).status_code == 404
    ho = other_user(c)
    assert c.get(f"{url}/versions", headers=ho).status_code == 404
    assert c.post(f"{url}/versions/{oldest['id']}/restore", headers=ho).status_code == 404


def test_restore_never_rewinds_authorship(env, monkeypatch):
    c, repo, h, pid, _ = env
    monkeypatch.setattr(repo_mod, "VERSION_MIN_INTERVAL_SECONDS", 0)
    sec = c.get(f"/projects/{pid}/sections", headers=h).json()[0]
    sid, url = sec["id"], f"/projects/{pid}/sections/{sec['id']}"
    old = {**doc_with("texto antigo do aluno"), "_authorship": {"ai_drafted_words": 0}}
    repo.update_section(pid, sid, content=old)
    new = {**doc_with("texto novo com ajuda"), "_authorship": {"ai_drafted_words": 40}}
    repo.update_section(pid, sid, content=new, version_by="ai", force_version=True)
    v = c.get(f"{url}/versions", headers=h).json()[0]
    restored = c.post(f"{url}/versions/{v['id']}/restore", headers=h).json()
    assert restored["content"]["_authorship"]["ai_drafted_words"] == 40


def test_autosaves_inside_interval_share_one_restore_point(env):
    c, repo, h, pid, _ = env  # default interval (5 min): a burst of typing = one restore point
    sec = c.get(f"/projects/{pid}/sections", headers=h).json()[0]
    url = f"/projects/{pid}/sections/{sec['id']}"
    for t in ("a b c", "a b c d", "a b c d e", "a b c d e f"):
        c.patch(url, headers=h, json={"content": doc_with(t)})
    assert len(c.get(f"{url}/versions", headers=h).json()) == 1
    # AI writes force a restore point even inside the window
    repo.update_section(pid, sec["id"], content=doc_with("a b c d e f g"), version_by="ai", force_version=True)
    assert len(c.get(f"{url}/versions", headers=h).json()) == 2


def test_versions_are_capped(env, monkeypatch):
    c, repo, h, pid, _ = env
    monkeypatch.setattr(repo_mod, "VERSION_MIN_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(repo_mod, "VERSION_KEEP", 3)
    sid = c.get(f"/projects/{pid}/sections", headers=h).json()[0]["id"]
    for i in range(8):
        repo.update_section(pid, sid, content=doc_with(f"versão número {i}"))
    vs = repo.list_section_versions(pid, sid)
    assert len(vs) == 3
    assert vs[0]["content_snapshot"]["content"][0]["content"][0]["text"] == "versão número 6"


# ----------------------------------------------------------------------------- tree feedback
def test_node_feedback_owner_advisor_and_shared_link(env):
    c, repo, h, pid, _ = env
    nodes = c.get(f"/projects/{pid}/tree", headers=h).json()
    key = (nodes["nodes"] if isinstance(nodes, dict) else nodes)[0]["key"]
    url = f"/projects/{pid}/tree/{key}/feedback"
    assert c.get(url, headers=h).json() == []
    r = c.post(url, json={"content": "  Delimite melhor o problema.  "}, headers=h)
    assert r.status_code == 201
    fb = r.json()
    assert fb["content"] == "Delimite melhor o problema." and fb["node_key"] == key and fb["project_id"] == pid
    assert fb["advisor_email"] == "aluna@usp.br"
    assert c.post(f"/projects/{pid}/tree/inexistente/feedback", json={"content": "x"}, headers=h).status_code == 404
    assert c.post(url, json={"content": ""}, headers=h).status_code == 422

    share = c.post(f"/projects/{pid}/share-link", headers=h).json()["token"]
    r = c.post(f"/shared/{share}/tree/{key}/feedback",
               json={"advisor_email": "Prof@USP.br", "advisor_name": "Profa. Lima", "content": "Ótimo avanço."})
    assert r.status_code == 201 and r.json()["advisor_email"] == "prof@usp.br"
    assert c.post(f"/shared/token-falso/tree/{key}/feedback",
                  json={"advisor_email": "a@b.co", "advisor_name": "", "content": "x"}).status_code == 404
    assert c.post(f"/shared/{share}/tree/zzz/feedback",
                  json={"advisor_email": "a@b.co", "advisor_name": "", "content": "x"}).status_code == 404

    listed = c.get(url, headers=h).json()
    assert [f["content"] for f in listed] == ["Delimite melhor o problema.", "Ótimo avanço."]

    # the invited advisor can read it; a stranger cannot
    prof = other_user(c, "prof@usp.br")
    assert [f["content"] for f in c.get(url, headers=prof).json()][-1] == "Ótimo avanço."
    assert c.get(url, headers=other_user(c, "intruso@usp.br")).status_code == 404
