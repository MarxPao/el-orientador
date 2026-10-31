import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from verify_quotes import verify_quote
from schemas import ExtractionOutput
from pipeline import verify_extraction

PAGES = [
    "Introdução\nA autorregulação da aprendizagem é um processo ativo em que os\nestudantes definem metas e monitoram seu progresso.",
    "O feedback formativo melhora a ava-\nliação em estudantes de pós-\ngraduação, segundo os resultados deste estudo.",
    "Resultados com ﬁnalidade pedagógica foram observados em “três turmas” distintas.",
]


def test_exact_match_with_line_break_spacing():
    r = verify_quote("os estudantes definem metas e monitoram seu progresso", PAGES)
    assert r.found and r.method == "exact" and r.page == 1


def test_hyphenation_across_lines_exact():
    r = verify_quote("melhora a avaliação em estudantes de", PAGES)
    assert r.found and r.method == "exact" and r.page == 2


def test_real_hyphen_at_line_break_matches_loose():
    r = verify_quote("estudantes de pós-graduação, segundo os resultados", PAGES)
    assert r.found and r.method == "loose" and r.page == 2


def test_ligature_and_typographic_quotes():
    r = verify_quote('Resultados com finalidade pedagógica foram observados em "três turmas" distintas', PAGES)
    assert r.found and r.page == 3


def test_hallucinated_quote_rejected():
    r = verify_quote("o feedback automático elimina totalmente a necessidade de orientação humana", PAGES)
    assert not r.found and r.method == "none"


def test_too_short_rejected():
    assert verify_quote("feedback formativo", PAGES).method == "too_short"


def test_wrong_page_is_corrected():
    r = verify_quote("os estudantes definem metas e monitoram seu progresso", PAGES, expected_page=3)
    assert r.found and r.page == 1


def test_offsets_point_to_original_text():
    q = "definem metas e monitoram seu progresso"
    r = verify_quote(q, PAGES)
    assert PAGES[0][r.start:r.end].replace("\n", " ") == q


def test_pipeline_filters_hallucinations():
    out = ExtractionOutput.model_validate({"claims": [
        {"concept": "Autorregulação", "statement": "Estudantes definem metas.",
         "quote": "os estudantes definem metas e monitoram seu progresso", "page": 1},
        {"concept": "Feedback", "statement": "Elimina a orientação humana.",
         "quote": "o feedback automático elimina totalmente a necessidade de orientação humana", "page": 2},
    ]})
    ok, bad = verify_extraction(out, PAGES)
    assert len(ok) == 1 and len(bad) == 1
    assert ok[0].concept == "Autorregulação" and bad[0].verify_method == "none"
