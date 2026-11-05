"""The evaluation tool itself: it must measure correctly, or its numbers are worse than none."""
import json
import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import eval_search as ev  # noqa: E402
from app.search import tokens  # noqa: E402

GROUPS = [{"evasao", "abandono", "desistencia"}, {"inflacao", "precos", "carestia"}]


def vec(text):
    v = [0.0] * (len(GROUPS) + 5)
    for t in tokens(text):
        hit = next((i for i, g in enumerate(GROUPS) if t in g), None)
        if hit is None:
            v[len(GROUPS) + sum(map(ord, t)) % 5] += 0.1
        else:
            v[hit] += 1.0
    return v


embed = lambda texts, task: [vec(t) for t in texts]  # noqa: E731

BOOKS = {
    "a.pdf": ["Capítulo sobre metodologia qualitativa com entrevistas semiestruturadas e análise de conteúdo temática.",
              "A evasão escolar cresce quando a renda familiar diminui e o transporte se torna caro para os alunos.",
              "Considerações finais sobre limitações do estudo e agenda de pesquisas futuras para o campo."],
    "b.pdf": ["A inflação de preços corrói o salário real e reduz o consumo das famílias de menor renda no país.",
              "Política monetária e taxa de juros: o banco central ajusta a Selic para conter a demanda agregada."],
}


def test_keyword_finds_literal_and_semantic_finds_synonym():
    qs = [{"pdf": "a.pdf", "question": "entrevistas semiestruturadas", "pages": [1]},
          {"pdf": "a.pdf", "question": "abandono dos estudos", "pages": [2]},      # synonym of evasão: no shared word
          {"pdf": "b.pdf", "question": "carestia", "pages": [1]}]                  # synonym of inflação
    r = ev.evaluate(BOOKS, qs, embed)
    m = r["methods"]
    assert m["keyword"]["recall@5"] == pytest.approx(1 / 3, abs=0.01)
    assert m["semantic"]["recall@5"] == 1.0
    assert m["hybrid"]["recall@5"] == 1.0 and m["hybrid"]["mrr"] >= m["keyword"]["mrr"]
    assert r["not_found_by_any_method"] == []


def test_wrong_pdf_or_page_is_not_a_hit():
    qs = [{"pdf": "b.pdf", "question": "entrevistas semiestruturadas", "pages": [1]},   # text is in a.pdf
          {"pdf": "a.pdf", "question": "entrevistas semiestruturadas", "pages": [3]}]   # text is on page 1
    r = ev.evaluate(BOOKS, qs, None)  # keyword only: with 5 chunks in total, semantic ranking returns every chunk
    assert r["methods"]["keyword"]["recall@10"] == 0.0
    assert len(r["not_found_by_any_method"]) == 2


def test_without_embeddings_only_keyword_is_reported():
    r = ev.evaluate(BOOKS, [{"pdf": "a.pdf", "question": "evasão escolar", "pages": [2]}], None)
    assert list(r["methods"]) == ["keyword", "hybrid"] and r["semantic_available"] is False
    assert "não avaliada" in ev.format_report(r)


def test_mrr_uses_the_rank_of_the_first_right_page():
    pages = {"a.pdf": ["entrevistas entrevistas entrevistas entrevistas sobre o método de pesquisa adotado no estudo.",
                       "As entrevistas semiestruturadas foram realizadas com professores da rede pública estadual."]}
    r = ev.evaluate(pages, [{"pdf": "a.pdf", "question": "entrevistas", "pages": [2]}], None)
    assert r["methods"]["keyword"]["recall@1"] == 0.0 and r["methods"]["keyword"]["recall@5"] == 1.0
    assert r["methods"]["keyword"]["mrr"] == 0.5


def test_question_file_validation(tmp_path):
    f = tmp_path / "q.json"
    f.write_text(json.dumps([{"pdf": "x.pdf", "question": "?", "pages": [1]}]))
    with pytest.raises(SystemExit):
        ev.load_questions(f, {"outro.pdf"})
    f.write_text(json.dumps([{"pdf": "x.pdf", "question": "?", "pages": [0]}]))
    with pytest.raises(SystemExit):
        ev.load_questions(f, {"x.pdf"})
    f.write_text(json.dumps([{"pdf": "x.pdf", "question": "?"}]))
    with pytest.raises(SystemExit):
        ev.load_questions(f, {"x.pdf"})
    f.write_text(json.dumps([{"pdf": "x.pdf", "question": "?", "pages": 3}]), encoding="utf-8-sig")
    assert ev.load_questions(f, {"x.pdf"})[0]["pages"] == [3]


def test_cli_end_to_end_with_real_pdfs(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("EMBED_PROVIDER", "none")
    d = tmp_path / "livros"
    d.mkdir()
    for name, pages in BOOKS.items():
        doc = pymupdf.open()
        for t in pages:
            doc.new_page().insert_textbox(pymupdf.Rect(50, 50, 545, 790), t, fontsize=11)
        doc.save(d / name)
    q = tmp_path / "q.json"
    q.write_text(json.dumps([{"pdf": "a.pdf", "question": "entrevistas semiestruturadas", "pages": [1]}]))
    out = tmp_path / "r.json"
    assert ev.main(["--pdfs", str(d), "--questions", str(q), "--out", str(out)]) == 0
    assert "keyword" in capsys.readouterr().out
    assert json.loads(out.read_text())["methods"]["keyword"]["recall@1"] == 1.0
