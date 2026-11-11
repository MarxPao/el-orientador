"""Tests for Multi-Advisee Cohort Dashboard and Academic Coordination (T7.4)."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from services.pipeline.app.cohort import (
    compute_cohort_dashboard,
    compute_student_overview,
    export_cohort_summary_csv,
    export_cohort_summary_markdown,
)
from services.pipeline.app.main import create_app
from services.pipeline.app.repo import InMemoryRepo
from services.pipeline.app.security import hash_password, create_token
from services.pipeline.app.tree import initial_nodes, load_template


def _setup_test_cohort(repo: InMemoryRepo):
    advisor = repo.create_user("prof.silva@universidade.br", "Prof. Silva", hash_password("senha123"))

    # Student 1: TCC, comfortable deadline (200 days), 2 done, 0 skipped -> on track
    s1 = repo.create_user("aluno1@universidade.br", "Mariana Silva", hash_password("senha123"))
    p1 = repo.create_project(s1["id"], {
        "title": "TCC sobre Redes Neurais",
        "work": "tcc",
        "institution": "UFMG",
        "deadline": (date.today() + timedelta(days=200)).isoformat(),
        "weekly_hours": 15,
    })
    repo.invite_advisor(p1["id"], advisor["email"], True)
    tmpl1 = load_template("tcc")
    repo.save_progress_nodes(p1["id"], initial_nodes(tmpl1))
    repo.update_progress_node(p1["id"], "tema_delimitacao", status="done")
    repo.update_progress_node(p1["id"], "problema_pesquisa", status="done")

    # Student 2: Dissertação, critical deadline (10 days), 1 done, 1 skipped with conscious warning
    s2 = repo.create_user("aluno2@universidade.br", "Carlos Mendes", hash_password("senha123"))
    p2 = repo.create_project(s2["id"], {
        "title": "Dissertação sobre Ética e IA",
        "work": "tcc",
        "institution": "USP",
        "deadline": (date.today() + timedelta(days=10)).isoformat(),
        "weekly_hours": 8,
    })
    repo.invite_advisor(p2["id"], advisor["email"], True)
    repo.save_progress_nodes(p2["id"], initial_nodes(tmpl1))
    repo.update_progress_node(p2["id"], "tema_delimitacao", status="done")
    repo.update_progress_node(p2["id"], "problema_pesquisa", status="skipped", skipped_reason="Problema previamente validado no edital")

    # Add section with unresolved comment for Student 2
    sec = repo.create_section(p2["id"], "Introdução", None, 1)
    repo.create_section_comment(sec["id"], advisor["email"], advisor["name"], "Ajustar justificativa metodológica.")

    return advisor, [p1, p2]


def test_compute_student_overview():
    repo = InMemoryRepo()
    advisor, projects = _setup_test_cohort(repo)
    p2 = projects[1]

    overview = compute_student_overview(repo, p2)

    assert overview["project_id"] == p2["id"]
    assert overview["student"]["name"] == "Carlos Mendes"
    assert overview["student"]["email"] == "aluno2@universidade.br"
    assert overview["progress"]["done_nodes"] == 1
    assert overview["progress"]["skipped_count"] == 1
    assert overview["progress"]["skipped_steps"][0]["node_key"] == "problema_pesquisa"
    assert "previamente validado" in overview["progress"]["skipped_steps"][0]["reason"]
    assert overview["schedule"]["days_until_deadline"] == 10
    assert overview["schedule"]["risk_level"] == "critical"
    assert overview["governance"]["unresolved_comments_count"] == 1


def test_compute_cohort_dashboard():
    repo = InMemoryRepo()
    advisor, projects = _setup_test_cohort(repo)

    dashboard = compute_cohort_dashboard(repo, advisor["email"])

    assert dashboard["advisor_email"] == advisor["email"]
    metrics = dashboard["metrics"]
    assert metrics["total_advisees"] == 2
    assert metrics["at_risk_count"] == 1
    assert metrics["total_skipped_steps"] == 1
    assert metrics["total_unresolved_comments"] == 1
    assert len(dashboard["students"]) == 2


def test_cohort_export_csv_and_markdown():
    repo = InMemoryRepo()
    advisor, _ = _setup_test_cohort(repo)
    dashboard = compute_cohort_dashboard(repo, advisor["email"])

    csv_out = export_cohort_summary_csv(dashboard)
    assert "Carlos Mendes" in csv_out
    assert "Problema previamente validado no edital" in csv_out
    assert "aluno1@universidade.br" in csv_out

    md_out = export_cohort_summary_markdown(dashboard)
    assert "# Relatório de Acompanhamento de Turma / Multi-orientandos" in md_out
    assert "Total de Orientandos:** 2" in md_out
    assert "Carlos Mendes" in md_out
    assert "Auditoria de Etapas Puladas (Avisos Conscientes)" in md_out


def test_cohort_api_endpoints():
    repo = InMemoryRepo()
    advisor, projects = _setup_test_cohort(repo)
    app = create_app(repo=repo)
    client = TestClient(app)

    token = create_token(advisor["id"])
    auth_header = {"Authorization": f"Bearer {token}"}

    # 1. Unauthenticated gets 401
    res = client.get("/advisor/cohort-summary")
    assert res.status_code == 401

    # 2. Authenticated gets summary
    res = client.get("/advisor/cohort-summary", headers=auth_header)
    assert res.status_code == 200
    data = res.json()
    assert data["metrics"]["total_advisees"] == 2
    assert len(data["students"]) == 2

    # 3. CSV export
    res_csv = client.get("/advisor/cohort-export?format=csv", headers=auth_header)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Carlos Mendes" in res_csv.text

    # 4. Markdown export
    res_md = client.get("/advisor/cohort-export?format=markdown", headers=auth_header)
    assert res_md.status_code == 200
    assert "text/markdown" in res_md.headers["content-type"]
    assert "Relatório de Acompanhamento de Turma" in res_md.text


def test_link_advisee_endpoint():
    repo = InMemoryRepo()
    advisor, projects = _setup_test_cohort(repo)
    app = create_app(repo=repo)
    client = TestClient(app)

    # Another advisor
    adv2 = repo.create_user("prof.costa@universidade.br", "Prof. Costa", hash_password("senha123"))
    token2 = create_token(adv2["id"])
    auth_header = {"Authorization": f"Bearer {token2}"}

    # Initially adv2 has 0 advisees
    res = client.get("/advisor/cohort-summary", headers=auth_header)
    assert res.json()["metrics"]["total_advisees"] == 0

    # Link p1 to adv2
    link_res = client.post("/advisor/link-advisee", json={"project_id": projects[0]["id"]}, headers=auth_header)
    assert link_res.status_code == 200
    assert link_res.json()["ok"] is True

    # Now adv2 has 1 advisee
    res2 = client.get("/advisor/cohort-summary", headers=auth_header)
    assert res2.json()["metrics"]["total_advisees"] == 1


def test_cohort_authorship_with_real_ai_events():
    repo = InMemoryRepo()
    advisor = repo.create_user("prof.orientador@universidade.br", "Prof. Orientador", hash_password("senha123"))
    student = repo.create_user("aluna.pesquisa@universidade.br", "Beatriz Lima", hash_password("senha123"))

    p = repo.create_project(student["id"], {
        "title": "Estudo de Caso com IA",
        "work": "tcc",
        "institution": "UFRJ",
    })
    repo.invite_advisor(p["id"], advisor["email"], True)

    # -------------------------------------------------------------------------
    # MEMÓRIA DE CÁLCULO MANUAL DA FIXTURE:
    # 1. ai_text possui 19 palavras:
    #    ["A", "pesquisa", "qualitativa", "permite", "compreender", "fenomenos",
    #     "sociais", "em", "profundidade", "articulando", "diferentes", "perspectivas",
    #     "dos", "sujeitos", "investigados", "em", "todas", "as", "dimensoes."] = 19
    # 2. human_text possui 16 palavras:
    #    ["Este", "trabalho", "analisa", "o", "impacto", "pedagogico", "das",
    #     "metodologias", "ativas", "no", "ensino", "fundamental", "publico", "da",
    #     "regiao", "metropolitana."] = 16
    # 3. Total de palavras da seção = 19 + 16 = 35 palavras.
    # 4. Proporções brutas:
    #    - IA: 19 / 35 = 54.285714...%
    #    - Humano: 16 / 35 = 45.714285...%
    # 5. Algoritmo de Maior Resto (Hare-Niemeyer / app.provenance.percentages):
    #    - Pisos inteiros: IA = 54%, Humano = 45% (Soma = 99%).
    #    - Restos: Humano = 0.714285... > IA = 0.285714...
    #    - O ponto residual (+1%) vai para o Humano (maior resto).
    #    - Resultado determinístico esperado:
    #      direct_human_pct = 46%
    #      ai_assisted_pct = 54%
    #      pasted_pct = 0%
    #      requires_disclosure = True
    # -------------------------------------------------------------------------
    ai_text = (
        "A pesquisa qualitativa permite compreender fenomenos sociais em profundidade "
        "articulando diferentes perspectivas dos sujeitos investigados em todas as dimensoes."
    )
    human_text = (
        "Este trabalho analisa o impacto pedagogico das metodologias ativas no ensino fundamental "
        "publico da regiao metropolitana."
    )

    content = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": ai_text}]},
            {"type": "paragraph", "content": [{"type": "text", "text": human_text}]},
        ],
    }
    sec = repo.create_section(p["id"], "Metodologia", None, 1, content=content)

    repo.add_provenance_event(
        p["id"], sec["id"], "ai_draft", "server", 19, ai_text, {}, student["email"]
    )

    dashboard = compute_cohort_dashboard(repo, advisor["email"])
    assert len(dashboard["students"]) == 1
    s_data = dashboard["students"][0]

    gov = s_data["governance"]
    assert gov["direct_human_pct"] == 46
    assert gov["ai_assisted_pct"] == 54
    assert gov["pasted_pct"] == 0
    assert gov["requires_disclosure"] is True
    assert gov["authorship_status"] == "ok"

    csv_out = export_cohort_summary_csv(dashboard)
    assert "Beatriz Lima" in csv_out
    assert "46%" in csv_out
    assert "54%" in csv_out
    assert "0%" in csv_out


def test_cohort_authorship_categories_breakdown():
    """Valida como direct_human_pct, ai_assisted_pct, pasted_pct e requires_disclosure tratam:
    1. Revisão gramatical leve (ai_polish): isenta de declaração (COPE/ICMJE), não conta como humano puro.
    2. Texto colado de fora (paste): NUNCA conta como IA nem como humano sem rótulo próprio (pasted_pct).
    3. Rascunho de IA reescrito (ai_paraphrase): conta em ai_assisted_pct (ai_revised_pct) e exige declaração.
    """
    repo = InMemoryRepo()
    advisor = repo.create_user("prof.orientador@universidade.br", "Prof. Orientador", hash_password("senha123"))
    student = repo.create_user("aluno.autoria@universidade.br", "Rodrigo Alves", hash_password("senha123"))

    p = repo.create_project(student["id"], {
        "title": "Projeto com Múltiplas Modalidades de Texto",
        "work": "tcc",
        "institution": "UFPE",
    })
    repo.invite_advisor(p["id"], advisor["email"], True)

    # 1. Seção com texto colado de fora (20 palavras)
    pasted_text = (
        "O principio da dignidade humana constitui o nucleo axiológico fundamental sobre o qual se estruturam "
        "todas as garantias constitucionais vigentes."
    )
    pasted_words_count = len(pasted_text.split()) # 20 palavras
    sec1 = repo.create_section(p["id"], "Fundamentação", None, 1, content={
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": pasted_text}]}]
    })
    # Evento de paste não declarado
    repo.add_provenance_event(
        p["id"], sec1["id"], "paste", "client_paste", pasted_words_count, pasted_text, {}, student["email"]
    )

    # 2. Seção com redação humana direta (20 palavras: exatamente igual à contagem de palavras do texto colado)
    human_text = (
        "Diante desse panorama observamos que a jurisprudencia brasileira recente tem aplicado tal principio "
        "de maneira uniforme nos tribunais superiores atuais."
    )
    repo.create_section(p["id"], "Análise", None, 2, content={
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": human_text}]}]
    })

    dashboard = compute_cohort_dashboard(repo, advisor["email"])
    s_data = dashboard["students"][0]
    gov = s_data["governance"]

    # Total = 40 palavras: 20 coladas (50%), 20 humanas (50%), 0 IA (0%)
    assert gov["direct_human_pct"] == 50
    assert gov["pasted_pct"] == 50
    assert gov["ai_assisted_pct"] == 0
    # Texto colado de fora não declarado EXIGE declaração e tem rótulo próprio!
    assert gov["requires_disclosure"] is True

    # Confirma que o CSV separa claramente humano, IA e colado de fora
    csv_out = export_cohort_summary_csv(dashboard)
    assert "Rodrigo Alves" in csv_out
    assert "50%" in csv_out # Humano
    assert "0%" in csv_out  # IA
    assert "50%" in csv_out # Colado de fora


def test_cohort_banca_failure_returns_indisponivel(monkeypatch):
    """Garante que falha na leitura das sessões de banca não passe em silêncio:
    marca banca_status='indisponivel', grava o erro no error_events e exibe 'Indisponível' no CSV.
    """
    repo = InMemoryRepo()
    advisor = repo.create_user("prof.orientador@universidade.br", "Prof. Orientador", hash_password("senha123"))
    student = repo.create_user("aluno.banca@universidade.br", "Juliana Souza", hash_password("senha123"))

    p = repo.create_project(student["id"], {
        "title": "Projeto com Falha na Banca",
        "work": "tcc",
        "institution": "UFRGS",
    })
    repo.invite_advisor(p["id"], advisor["email"], True)

    def _failing_banca(*args, **kwargs):
        raise ConnectionError("Falha de conexão com a tabela de banca simulada")

    monkeypatch.setattr(repo, "list_banca_sessions", _failing_banca)

    dashboard = compute_cohort_dashboard(repo, advisor["email"])
    s_data = dashboard["students"][0]
    gov = s_data["governance"]

    assert gov["banca_status"] == "indisponivel"
    assert gov["banca_verdict"] is None
    assert gov["banca_score"] is None

    # CSV deve exibir 'Indisponível' na coluna de banca
    csv_out = export_cohort_summary_csv(dashboard)
    assert "Juliana Souza" in csv_out
    assert "Indisponível" in csv_out
    assert "Não realizada" not in csv_out

    # Erro deve estar gravado no error_events
    errs = repo.list_error_events()
    assert any(e["source"] == "cohort" and "ConnectionError" in e["error_type"] for e in errs)



def test_cohort_authorship_failure_returns_indisponivel(monkeypatch):
    repo = InMemoryRepo()
    advisor = repo.create_user("prof.orientador@universidade.br", "Prof. Orientador", hash_password("senha123"))
    student = repo.create_user("aluna.erro@universidade.br", "Larissa Rocha", hash_password("senha123"))

    p = repo.create_project(student["id"], {
        "title": "Projeto com Falha no Calculo",
        "work": "tcc",
        "institution": "UNICAMP",
    })
    repo.invite_advisor(p["id"], advisor["email"], True)

    def _failing_authorship(*args, **kwargs):
        raise RuntimeError("Corrupted provenance database or AST error")

    monkeypatch.setattr("services.pipeline.app.cohort.compute_project_authorship", _failing_authorship)

    dashboard = compute_cohort_dashboard(repo, advisor["email"])
    assert len(dashboard["students"]) == 1
    s_data = dashboard["students"][0]

    gov = s_data["governance"]
    # Never return favorable default (100% human)
    assert gov["direct_human_pct"] is None
    assert gov["ai_assisted_pct"] is None
    assert gov["requires_disclosure"] is None
    assert gov["authorship_status"] == "indisponivel"

    # Verify CSV export displays "Indisponível" instead of a percentage
    csv_out = export_cohort_summary_csv(dashboard)
    assert "Larissa Rocha" in csv_out
    assert "Indisponível" in csv_out
    assert "100%" not in csv_out

    # Verify error was recorded in repo error_events
    error_events = repo.list_error_events()
    assert len(error_events) >= 1
    assert error_events[0]["source"] == "cohort"
    assert "RuntimeError" in error_events[0]["error_type"]
    assert "cohort/compute_student_overview" in error_events[0]["route"]

