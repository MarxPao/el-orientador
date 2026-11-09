"""Unit and integration tests for the Academic Defense Simulator (T7.2)."""
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.banca import (
    compile_defense_context,
    evaluate_turn_and_reply,
    generate_opening_question,
    synthesize_final_report,
)
from app.main import create_app
from app.repo import InMemoryRepo


class MockBancaLLM:
    def __init__(self):
        self.model = "mock-banca-model"
        self.calls = []

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        self.calls.append({"system": system, "user": user, "schema": schema})
        props = schema.get("properties", {})
        # Conclude report response
        if "verdict" in props:
            return {
                "verdict": "apto_com_louvor",
                "verdict_title": "Apto com Louvor — Excelente Sustentação Oral",
                "overall_score": 9.2,
                "strengths": ["Firmeza argumentativa", "Articulação de evidências"],
                "vulnerabilities": ["Delimitação temporal restrita"],
                "recommendations": ["Aprofundar contraexemplos teóricos", "Revisar notas de rodapé", "Praticar síntese temporal"],
            }
        # Turn evaluation response
        if "rubric_scores" in props:
            return {
                "rubric_scores": {
                    "dominio_conteudo": 3,
                    "fundamentacao_evidencias": 2,
                    "coerencia_metodologica": 3,
                    "postura_argumentativa": 2,
                },
                "turn_feedback": "Argumentação consistente e segura diante das objeções da banca.",
                "next_question": "Como você contra-argumenta frente à teoria divergente de Silva (2019)?",
                "focus_area": "fundamentacao",
            }
        # Opening question response
        return {
            "question": "Qual é a principal limitação metodológica do seu corpus analítico?",
            "focus_area": "metodologia",
            "examiner_tone": "estrito",
        }


def make_test_client(client=None):
    repo = InMemoryRepo()
    app = create_app(repo=repo, client=client)
    return TestClient(app), repo


def _setup_project_with_manuscript(repo, title="Evasão no Ensino Superior"):
    u = repo.create_user("estudante@ufmg.br", "Estudante", "hash")
    p = repo.create_project(u["id"], {
        "title": title,
        "work": "dissertacao",
        "institution": "UFMG",
        "research_problem": "Fatores associados ao abandono no ciclo básico de exatas.",
    })
    pid = p["id"]

    # Document & claim
    doc = repo.create_document(pid, {"title": "Permanência na Universidade", "authors": ["Santos, M."], "year": 2021})
    repo.add_claims(
        doc["id"],
        [{
            "concept": "Monitoria",
            "statement": "Monitorias ativas reduzem a evasão em 15%.",
            "quote": "A oferta de monitorias ativas correlacionou-se com queda de 15% na evasão.",
            "page_no": 42,
            "page_verified": 42,
            "quote_verified": True,
            "verify_method": "exact",
        }],
        model="test",
        prompt_version="v1",
    )

    # Manuscript section
    sec = repo.create_section(pid, "Metodologia", None, 1)
    repo.update_section(pid, sec["id"], content={
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Adotamos uma abordagem mista com aplicação de questionários a 120 estudantes de primeiro ano."}]}
        ]
    })

    return u, p


def test_banca_context_compilation():
    repo = InMemoryRepo()
    _, p = _setup_project_with_manuscript(repo)
    ctx = compile_defense_context(repo, p["id"])

    assert ctx["title"] == "Evasão no Ensino Superior"
    assert ctx["work_type"] == "dissertacao"
    assert ctx["sections_count"] >= 1
    assert any("questionários a 120 estudantes" in s for s in ctx["sections"])
    assert ctx["claims_count"] >= 1
    assert any("Monitorias ativas" in c for c in ctx["claims"])


def test_banca_deterministic_scaffold_without_llm():
    repo = InMemoryRepo()
    _, p = _setup_project_with_manuscript(repo)
    ctx = compile_defense_context(repo, p["id"])

    # Strict opening question
    op_strict = generate_opening_question(ctx, "estrito", client=None)
    assert "fragilidade metodológica" in op_strict["question"] or "validade" in op_strict["question"]
    assert op_strict["focus_area"] == "validade_metodologica"
    assert op_strict["prompt_version"] is None

    # Constructive opening question
    op_const = generate_opening_question(ctx, "construtivo", client=None)
    assert "avança o estado da arte" in op_const["question"] or "impacto" in op_const["question"]

    # Turn evaluation without LLM
    answer = "Segundo Santos (2021), a limitação da nossa amostra de 120 alunos é reconhecida no método, mas o estudo demonstra relevância estatística."
    eval_res = evaluate_turn_and_reply(ctx, "estrito", [{"speaker": "examiner", "content": op_strict["question"]}], answer, client=None)
    assert "rubric_scores" in eval_res
    assert eval_res["rubric_scores"]["dominio_conteudo"] >= 2
    assert "next_question" in eval_res

    # Final report without LLM
    turns = [
        {"speaker": "examiner", "content": op_strict["question"]},
        {"speaker": "student", "content": answer, "rubric_scores": eval_res["rubric_scores"]},
    ]
    rep = synthesize_final_report(ctx, "estrito", turns, client=None)
    assert rep["verdict"] in ("apto_com_louvor", "apto_com_ressalvas")
    assert len(rep["strengths"]) >= 2
    assert len(rep["vulnerabilities"]) >= 2
    assert len(rep["recommendations"]) == 3


def test_banca_with_mock_llm():
    mock_llm = MockBancaLLM()
    repo = InMemoryRepo()
    _, p = _setup_project_with_manuscript(repo)
    ctx = compile_defense_context(repo, p["id"])

    opening = generate_opening_question(ctx, "estrito", client=mock_llm)
    assert "limitação metodológica" in opening["question"]
    assert opening["prompt_version"] == "banca_defense_v0.1"

    eval_turn = evaluate_turn_and_reply(
        ctx,
        "estrito",
        [{"speaker": "examiner", "content": opening["question"]}],
        "Minha resposta detalhada sobre o método.",
        client=mock_llm,
    )
    assert eval_turn["rubric_scores"]["dominio_conteudo"] == 3
    assert "divergente de Silva" in eval_turn["next_question"]

    rep = synthesize_final_report(ctx, "estrito", [], client=mock_llm)
    assert rep["verdict"] == "apto_com_louvor"
    assert rep["overall_score"] >= 9.0


def test_banca_api_endpoints_lifecycle():
    client, repo = make_test_client(client=None)

    # 1. Register & create project with manuscript text
    r_auth = client.post("/auth/register", json={"email": "aluno@banca.br", "password": "senha-segura-123", "name": "Aluno Banca"})
    assert r_auth.status_code == 201
    token = r_auth.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    r_proj = client.post("/projects", json={"title": "Inteligência Artificial na Saúde", "work": "tese"}, headers=headers)
    assert r_proj.status_code == 201
    pid = r_proj.json()["id"]

    # Add section
    r_sec = client.post(f"/projects/{pid}/sections", json={"title": "Introdução"}, headers=headers)
    assert r_sec.status_code in (200, 201)

    # 2. POST /projects/{id}/banca/sessions (create session)
    r_sess = client.post(
        f"/projects/{pid}/banca/sessions",
        json={"examiner_profile": "estrito"},
        headers=headers,
    )
    assert r_sess.status_code == 201
    sess_data = r_sess.json()
    assert "session" in sess_data
    session = sess_data["session"]
    sid = session["id"]
    assert session["examiner_profile"] == "estrito"
    assert session["status"] == "in_progress"
    assert len(session["turns"]) == 1
    assert session["turns"][0]["speaker"] == "examiner"

    # 3. GET /projects/{id}/banca/sessions (list sessions)
    r_list = client.get(f"/projects/{pid}/banca/sessions", headers=headers)
    assert r_list.status_code == 200
    assert len(r_list.json()["sessions"]) == 1

    # 4. GET /projects/{id}/banca/sessions/{sid} (get session)
    r_get = client.get(f"/projects/{pid}/banca/sessions/{sid}", headers=headers)
    assert r_get.status_code == 200
    assert r_get.json()["session"]["id"] == sid

    # 5. POST /projects/{id}/banca/sessions/{sid}/turn (student answer)
    r_turn = client.post(
        f"/projects/{pid}/banca/sessions/{sid}/turn",
        json={"answer": "Respondendo à banca: nossa metodologia delimita o estudo em prontuários anonimizados, conforme Santos (2021)."},
        headers=headers,
    )
    assert r_turn.status_code == 200
    turn_res = r_turn.json()
    updated_turns = turn_res["session"]["turns"]
    assert len(updated_turns) == 3  # Q1, A1, Q2
    assert updated_turns[1]["speaker"] == "student"
    assert updated_turns[1]["rubric_scores"] is not None
    assert updated_turns[2]["speaker"] == "examiner"

    # 6. POST /projects/{id}/banca/sessions/{sid}/conclude (conclude session)
    r_conclude = client.post(f"/projects/{pid}/banca/sessions/{sid}/conclude", headers=headers)
    assert r_conclude.status_code == 200
    concluded_sess = r_conclude.json()["session"]
    assert concluded_sess["status"] == "completed"
    assert concluded_sess["final_report"] is not None
    assert "verdict" in concluded_sess["final_report"]
    assert len(concluded_sess["final_report"]["recommendations"]) == 3

    # 7. Submitting turn after concluded returns 400
    r_turn_after = client.post(
        f"/projects/{pid}/banca/sessions/{sid}/turn",
        json={"answer": "Tentando responder após encerramento."},
        headers=headers,
    )
    assert r_turn_after.status_code == 400


def test_banca_ai_usage_logging_with_mock():
    mock_llm = MockBancaLLM()
    client, repo = make_test_client(client=mock_llm)

    r_auth = client.post("/auth/register", json={"email": "doutorando@usp.br", "password": "senha-segura-123", "name": "Doutorando"})
    headers = {"Authorization": f"Bearer {r_auth.json()['token']}"}
    pid = client.post("/projects", json={"title": "Robótica Educacional", "work": "tese"}, headers=headers).json()["id"]

    r_sess = client.post(f"/projects/{pid}/banca/sessions", json={"examiner_profile": "construtivo"}, headers=headers)
    sid = r_sess.json()["session"]["id"]

    # AI usage logged on opening question
    assert any(log["action"] == "banca_defense_question" for log in repo.ai_usage)

    # Submit turn
    client.post(f"/projects/{pid}/banca/sessions/{sid}/turn", json={"answer": "Minha sustentação teórica."}, headers=headers)
    assert any(log["action"] == "banca_defense_turn" for log in repo.ai_usage)

    # Conclude session
    client.post(f"/projects/{pid}/banca/sessions/{sid}/conclude", headers=headers)
    assert any(log["action"] == "banca_defense_conclude" for log in repo.ai_usage)
