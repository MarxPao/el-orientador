import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import create_app
from app.repo import InMemoryRepo


class MockGateClient:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.model = "mock-gate-model"
        self.calls: list[dict] = []

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        self.calls.append({"system": system, "user": user})
        if self.responses:
            return self.responses.pop(0)
        return {
            "message_to_student": "Explique mais detalhadamente a relevância teórica.",
            "done": False,
        }


def make_client(llm_client=None):
    repo = InMemoryRepo()
    app = create_app(repo=repo, client=llm_client)
    return TestClient(app), repo


def register_and_create_project(c):
    r = c.post("/auth/register", json={"email": "aluno@usp.br", "password": "senha-segura-1", "name": "Aluno USP"})
    assert r.status_code == 201
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    p = c.post("/projects", json={"title": "TCC IA", "work": "tcc"}, headers=headers).json()
    return headers, p["id"]


def test_gate_without_llm_refuses_instead_of_faking_approval():
    c, repo = make_client()
    headers, pid = register_and_create_project(c)

    long_answer = (
        "Vou investigar a aplicação de redes neurais convolucionais na detecção precoce de pragas em "
        "plantações de soja no Centro-Oeste, visando reduzir perdas de produtividade."
    )
    r = c.post(
        f"/projects/{pid}/tree/nodes/tema_delimitacao/gate",
        json={"user_input": long_answer, "history": [{"role": "user", "content": "oi"}]},
        headers=headers,
    )
    assert r.status_code == 503
    assert "aviso consciente" in r.json()["detail"]

    tree = c.get(f"/projects/{pid}/tree", headers=headers).json()
    tema_node = next(n for n in tree["nodes"] if n["key"] == "tema_delimitacao")
    assert tema_node["status"] != "done"  # never approved without a real evaluation

    # the honest escape hatch keeps working without an LLM
    r_skip = c.post(
        f"/projects/{pid}/tree/nodes/tema_delimitacao/gate",
        json={"skip": True, "skip_reason": "Combinado com o orientador."},
        headers=headers,
    )
    assert r_skip.status_code == 200
    assert r_skip.json()["outcome"] == "pular"


def test_gate_llm_outage_returns_503_and_opens_circuit():
    class FailingLLM:
        model = "failing"
        calls = 0

        def complete_json(self, system, user, schema):
            FailingLLM.calls += 1
            raise RuntimeError("provider down")

    c, repo = make_client(FailingLLM())
    headers, pid = register_and_create_project(c)
    for _ in range(4):
        r = c.post(
            f"/projects/{pid}/tree/nodes/tema_delimitacao/gate",
            json={"user_input": "Resposta qualquer", "history": []},
            headers=headers,
        )
        assert r.status_code == 503
    assert FailingLLM.calls == 3  # 4th request failed fast: circuit open
    caps = c.get("/capabilities").json()
    assert caps["llm_configured"] is True and caps["llm_available"] is False


def test_gate_turn_skip_with_conscious_warning():
    c, repo = make_client()
    headers, pid = register_and_create_project(c)

    # User opts to skip socratic gate with warning
    r = c.post(
        f"/projects/{pid}/tree/nodes/tema_delimitacao/gate",
        json={"skip": True, "skip_reason": "Conversei com meu orientador presencialmente ontem e já alinhamos."},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["done"] is True
    assert data["outcome"] == "pular"
    assert "Etapa pulada" in data["message_to_student"]

    # Verify node status is 'skipped' and skipped_reason is recorded
    tree = c.get(f"/projects/{pid}/tree", headers=headers).json()
    tema_node = next(n for n in tree["nodes"] if n["key"] == "tema_delimitacao")
    assert tema_node["status"] == "skipped"
    assert "orientador presencialmente" in (tema_node["skipped_reason"] or "")

    # Prerequisite met: dependent node unlocks
    problema_node = next(n for n in tree["nodes"] if n["key"] == "problema_pesquisa")
    assert problema_node["status"] == "available"

    # Verify attempt recorded in repo
    node_id = tema_node["node_id"]
    attempts = repo.list_gate_attempts(node_id)
    assert len(attempts) == 1
    assert attempts[0]["outcome"] == "pular"

    # Verify ai_usage_log
    assert any(log["action"] == "gate" and log["target_ref"] == node_id for log in repo.ai_usage)


def test_gate_turn_with_mock_llm():
    mock_responses = [
        {
            "message_to_student": "Qual é a pergunta de pesquisa específica que orientará o trabalho?",
            "done": False,
        },
        {
            "message_to_student": "Excelente formulação. O problema é relevante e bem delimitado.",
            "done": True,
            "outcome": "liberar",
            "rubric_scores": {"clareza": 2, "justificativa": 2, "coerencia": 2},
            "guidance": "Defina os objetivos gerais e específicos.",
        },
    ]
    mock_client = MockGateClient(mock_responses)
    c, repo = make_client(llm_client=mock_client)
    headers, pid = register_and_create_project(c)

    # Turn 1
    r1 = c.post(
        f"/projects/{pid}/tree/nodes/problema_pesquisa/gate",
        json={"user_input": "Quero entender como IA ajuda pequenos produtores.", "history": []},
        headers=headers,
    )
    assert r1.status_code == 200
    assert r1.json()["done"] is False
    assert "pergunta de pesquisa" in r1.json()["message_to_student"]

    # Turn 2
    r2 = c.post(
        f"/projects/{pid}/tree/nodes/problema_pesquisa/gate",
        json={
            "user_input": "Como o uso de modelos leves de visão computacional pode reduzir perdas em até 15% na safra familiar?",
            "history": [
                {"role": "user", "content": "Quero entender como IA ajuda pequenos produtores."},
                {"role": "assistant", "content": r1.json()["message_to_student"]},
            ],
        },
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["done"] is True
    assert r2.json()["outcome"] == "liberar"
    assert r2.json()["rubric_scores"]["coerencia"] == 2

    # Check history endpoint
    r_hist = c.get(f"/projects/{pid}/tree/nodes/problema_pesquisa/gate", headers=headers)
    assert r_hist.status_code == 200
    hist_data = r_hist.json()
    assert len(hist_data["attempts"]) == 2
