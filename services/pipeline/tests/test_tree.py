import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import create_app  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402
from app.tree import (  # noqa: E402
    initial_nodes,
    load_template,
    merge_template_with_nodes,
    resolve_node_states,
)


def test_load_templates():
    tcc = load_template("tcc")
    assert tcc["key"] == "tcc"
    assert len(tcc["phases"]) == 7
    assert len(tcc["nodes"]) >= 10

    pos = load_template("pre_projeto_mestrado")
    assert pos["key"] == "pre_projeto_mestrado"
    assert len(pos["phases"]) == 7

    fallback = load_template("desconhecido")
    assert fallback["key"] == "tcc"


def test_initial_nodes_and_unlock_progression():
    tpl = {
        "key": "mini",
        "nodes": [
            {"key": "a", "prerequisites": []},
            {"key": "b", "prerequisites": ["a"]},
            {"key": "c", "prerequisites": ["b"]},
        ],
    }
    nodes = initial_nodes(tpl)
    by_key = {n["node_key"]: n["status"] for n in nodes}
    assert by_key["a"] == "available"
    assert by_key["b"] == "locked"
    assert by_key["c"] == "locked"

    # When 'a' is marked done, 'b' unlocks to available, but 'c' stays locked
    nodes[0]["status"] = "done"
    resolved = resolve_node_states(tpl, nodes)
    r_key = {n["node_key"]: n["status"] for n in resolved}
    assert r_key["a"] == "done"
    assert r_key["b"] == "available"
    assert r_key["c"] == "locked"

    # When 'b' is skipped, 'c' unlocks to available
    resolved[1]["status"] = "skipped"
    resolved2 = resolve_node_states(tpl, resolved)
    r_key2 = {n["node_key"]: n["status"] for n in resolved2}
    assert r_key2["b"] == "skipped"
    assert r_key2["c"] == "available"


def setup_client():
    repo = InMemoryRepo()
    client = TestClient(create_app(repo))
    token = client.post("/auth/register", json={"email": "aluno@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    pid = client.post("/projects", json={"title": "Meu TCC de Computação", "work": "tcc"}, headers=h).json()["id"]
    return client, h, pid


def test_tree_api_initialization_and_node_completion():
    client, h, pid = setup_client()

    # GET tree initializes nodes from template
    r = client.get(f"/projects/{pid}/tree", headers=h)
    assert r.status_code == 200
    tree = r.json()
    assert tree["template_key"] == "tcc"
    assert len(tree["phases"]) == 7

    nodes = {n["key"]: n for n in tree["nodes"]}
    assert nodes["tema_delimitacao"]["status"] == "available"
    assert nodes["problema_pesquisa"]["status"] == "locked"

    # Complete first node -> cascades to unlock next node
    patch_r = client.patch(
        f"/projects/{pid}/tree/nodes/tema_delimitacao",
        json={"status": "done"},
        headers=h,
    )
    assert patch_r.status_code == 200

    r2 = client.get(f"/projects/{pid}/tree", headers=h)
    nodes2 = {n["key"]: n for n in r2.json()["nodes"]}
    assert nodes2["tema_delimitacao"]["status"] == "done"
    assert nodes2["problema_pesquisa"]["status"] == "available"


def test_tree_api_queuing_and_isolation():
    client, h, pid = setup_client()

    # Queue node into research queue
    patch_r = client.patch(
        f"/projects/{pid}/tree/nodes/tema_delimitacao",
        json={"queued": True},
        headers=h,
    )
    assert patch_r.status_code == 200
    assert patch_r.json()["queued"] is True

    # Other user cannot access tree
    token_other = client.post("/auth/register", json={"email": "outro@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    ho = {"Authorization": f"Bearer {token_other}"}
    assert client.get(f"/projects/{pid}/tree", headers=ho).status_code == 404
    assert client.patch(f"/projects/{pid}/tree/nodes/tema_delimitacao", json={"status": "done"}, headers=ho).status_code == 404
