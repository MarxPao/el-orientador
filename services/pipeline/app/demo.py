"""Optional demo data (DEMO_SEED=1): lets you click through the map and evidence panel without a LLM or real PDFs.

Creates demo@exemplo.com / demo-senha-1 with one project, two generated PDFs, verified claims and two links.
Text is invented for the demo only. Never enabled by default.
"""
from __future__ import annotations

import os
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


def seed_demo(repo: Repo, storage_dir: Path, with_cohort: bool = False) -> None:
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

    if with_cohort or os.environ.get("DEMO_COHORT") == "1":
        _seed_beta_cohort(repo)


def _seed_beta_cohort(repo: Repo) -> None:
    cohort = [
        ("mariana.silva@beta.br", "Mariana Silva (TCC CC)", "tcc", 6, "passe_projeto", 5, 5, 5, 5, "Foco acadêmico sério, sem enrolação."),
        ("lucas.mendes@beta.br", "Lucas Mendes (Mestrado Educ)", "pre_projeto_mestrado", 8, "passe_projeto", 5, 4, 5, 4, "A verificação de citação literal passa muita segurança."),
        ("beatriz.costa@beta.br", "Beatriz Costa (TCC Eng)", "tcc", 5, "mensal", 4, 4, 5, 4, "A árvore de progresso tirou a paralisia inicial."),
        ("rodrigo.alves@beta.br", "Rodrigo Alves (Doutorado Saúde)", "tese", 12, "passe_projeto", 5, 5, 5, 5, "O relatório para o orientador facilitou muito nossas reuniões quinzenais."),
        ("camila.rocha@beta.br", "Camila Rocha (TCC Direito)", "tcc", 7, "passe_projeto", 4, 4, 4, 5, "Gostei da postura sóbria de caderno de laboratório."),
        ("felipe.santos@beta.br", "Felipe Santos (Mestrado Comp)", "dissertacao", 9, "passe_projeto", 5, 5, 5, 5, "Melhor do que chats que inventam DOIs inexistentes."),
        ("aline.oliveira@beta.br", "Aline Oliveira (TCC Admin)", "tcc", 5, "mensal", 4, 3, 5, 4, "O gate socrático me fez ajustar a pergunta de pesquisa."),
        ("gustavo.lima@beta.br", "Gustavo Lima (TCC Bio)", "tcc", 6, "passe_projeto", 5, 5, 5, 4, "O mapa conceitual economizou semanas de leitura desordenada."),
        ("juliana.martins@beta.br", "Juliana Martins (Mestrado Letras)", "pre_projeto_mestrado", 6, "passe_projeto", 5, 4, 5, 5, "Passe por projeto faz muito mais sentido que pagar o ano todo."),
        ("tiago.ribeiro@beta.br", "Tiago Ribeiro (TCC Economia)", "tcc", 4, "outro", 3, 3, 4, 3, "Preciso de mais modelos institucionais específicos."),
        ("amanda.ferreira@beta.br", "Amanda Ferreira (TCC Psicologia)", "tcc", 3, "passe_projeto", 4, 4, 4, 4, "Muito bom para estruturar os objetivos."),
        ("gabriel.souza@beta.br", "Gabriel Souza (Artigo)", "artigo", 7, "passe_projeto", 5, 4, 5, 4, "Caderno de laboratório impecável."),
    ]
    for email, name, work, doc_count, pricing, overall, gate, trust, relief, comm in cohort:
        if repo.get_user_by_email(email):
            continue
        u = repo.create_user(email, name, hash_password("beta-senha-123"))
        p = repo.create_project(u["id"], {
            "title": f"Projeto de Pesquisa - {name.split()[0]}",
            "work": work,
            "institution": "Universidade Pública",
            "citation_style": "abnt",
            "deadline": "2026-12-15",
            "weekly_hours": 10,
            "research_problem": "Investigação experimental com evidências verificadas.",
        })
        repo.invite_advisor(p["id"], DEMO_EMAIL, True)
        from .tree import initial_nodes, load_template
        tmpl = load_template(work)
        repo.save_progress_nodes(p["id"], initial_nodes(tmpl))
        if doc_count >= 6:
            repo.update_progress_node(p["id"], "tema_delimitacao", status="done")
            repo.update_progress_node(p["id"], "problema_pesquisa", status="done")
        elif doc_count == 5:
            repo.update_progress_node(p["id"], "tema_delimitacao", status="done")
            repo.update_progress_node(p["id"], "problema_pesquisa", status="skipped", skipped_reason="Problema alinhado com edital PIBIC prévio")
        for i in range(doc_count):
            repo.create_document(p["id"], {
                "doi": f"10.1000/beta-{u['id'][:4]}-{i}",
                "title": f"Estudo empírico referenciado {i+1}",
                "authors": ["Autor Teste"],
                "year": 2020 + (i % 5),
                "venue": "Revista Científica",
                "metadata_source": "crossref",
                "retracted": False,
                "storage_path": f"{p['id']}/doc-{i}.pdf",
                "analysis": "full_text",
                "status": "extracted",
            })
        repo.add_beta_feedback(u["id"], {
            "project_id": p["id"],
            "overall_rating": overall,
            "socratic_gate_helpful": gate,
            "evidence_trust": trust,
            "relief_level": relief,
            "pricing_preference": pricing,
            "brand_impression": "Sóbrio, confiável, focado em evidências",
            "comments": comm,
        })

seed_beta_cohort = _seed_beta_cohort
