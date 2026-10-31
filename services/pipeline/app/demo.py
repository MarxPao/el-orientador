"""Optional demo data (DEMO_SEED=1): lets you click through the map and evidence panel without a LLM or real PDFs.

Creates demo@exemplo.com / demo-senha-1 with one project, two generated PDFs, verified claims and two links.
Text is invented for the demo only. Never enabled by default.
"""
from __future__ import annotations

from pathlib import Path

from .pipeline.verify_quotes import verify_quote
from .repo import Repo
from .security import hash_password

DEMO_EMAIL = "demo@exemplo.com"
DEMO_PASSWORD = "demo-senha-1"

_DOCS = [
    ("Aprendizagem e conhecimentos prévios (demo)", 2019, [
        "Introdução. Este texto de demonstração discute como os estudantes aprendem. "
        "A aprendizagem significativa depende de conhecimentos prévios do aluno em sala de aula. "
        "Os resultados descritos aqui são fictícios e servem apenas para testar a interface do sistema.",
    ], [("Aprendizagem significativa",
         "A aprendizagem significativa depende de conhecimentos prévios do aluno em sala de aula.")]),
    ("Motivação no ensino médio (demo)", 2021, [
        "Resumo. Conhecimentos prévios do aluno influenciam a aprendizagem em sala de aula, segundo este texto fictício. "
        "A motivação intrínseca amplia o engajamento dos estudantes nas atividades propostas pelo professor.",
    ], [("Conhecimento prévio",
         "Conhecimentos prévios do aluno influenciam a aprendizagem em sala de aula"),
        ("Motivação",
         "A motivação intrínseca amplia o engajamento dos estudantes nas atividades propostas pelo professor.")]),
]


def _make_pdf(path: Path, pages: list[str]) -> None:
    import pymupdf

    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_textbox(pymupdf.Rect(50, 60, 545, 780), text, fontsize=11)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


def seed_demo(repo: Repo, storage_dir: Path) -> None:
    if repo.get_user_by_email(DEMO_EMAIL):
        return
    user = repo.create_user(DEMO_EMAIL, "Usuária de demonstração", hash_password(DEMO_PASSWORD))
    project = repo.create_project(user["id"], {
        "title": "Projeto de demonstração", "work": "tcc", "institution": None, "citation_style": "abnt",
        "deadline": None, "weekly_hours": None, "research_problem": None})
    for title, year, pages, claims in _DOCS:
        key = f"{project['id']}/demo-{year}.pdf"
        _make_pdf(storage_dir / key, pages)
        doc = repo.create_document(project["id"], {
            "doi": None, "title": title, "authors": [], "year": year, "venue": None, "metadata_source": "manual",
            "retracted": False, "storage_path": key, "analysis": "full_text", "status": "extracted"})
        repo.save_pages(doc["id"], pages)
        verified = []
        for concept, quote in claims:
            r = verify_quote(quote, pages)
            assert r.found, "demo quote must exist in the generated page"
            verified.append({"concept": concept, "statement": quote, "quote": quote, "page_verified": r.page,
                             "char_start": r.start, "char_end": r.end, "verify_method": r.method,
                             "quote_verified": True, "certainty": "sugere", "scope": {}})
        repo.add_claims(doc["id"], verified, "demo", "demo")

    by_concept = {c["concept"]: c for c in repo.list_project_claims(project["id"])}

    def edge(a: str, b: str, relation: str, status: str, rationale: str, confidence: float) -> dict:
        return {"source_concept": by_concept[a]["concept_id"], "target_concept": by_concept[b]["concept_id"],
                "relation": relation, "status": status, "rationale": rationale, "confidence": confidence,
                "display_by_default": True,
                "evidence": [{"claim_id": by_concept[a]["id"], "side": "source"},
                             {"claim_id": by_concept[b]["id"], "side": "target"}]}

    repo.add_edges(project["id"], [
        edge("Aprendizagem significativa", "Conhecimento prévio", "apoia", "suggested",
             "Ambos os trechos tratam dos conhecimentos prévios do aluno na aprendizagem.", 0.82),
        edge("Conhecimento prévio", "Motivação", "estende", "confirmed",
             "Exemplo de ligação confirmada pela usuária (demonstração).", 0.7),
    ])

    repo.add_gaps(project["id"], [{
        "concept_a": by_concept["Aprendizagem significativa"]["concept_id"],
        "concept_b": by_concept["Motivação"]["concept_id"],
        "searches": [
            {"source": "openalex", "query": '"Aprendizagem significativa" AND "Motivação"', "total": 0, "results": [], "status": "ok"},
            {"source": "semantic_scholar", "query": "Aprendizagem significativa Motivação", "total": 0, "results": [], "status": "ok"}
        ],
        "found_links": [],
        "note": 'Não encontrei estudos nas buscas feitas: openalex ("Aprendizagem significativa" AND "Motivação"), semantic_scholar (Aprendizagem significativa Motivação).',
        "status": "open",
    }])
