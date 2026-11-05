"""Authorship Prism, Continuous Autonomy Gradient (0-100%) and the writing-assistance generators.

Authorship is reported from a provenance ledger (app/provenance.py): what the assistant inserted and what the
editor saw pasted, matched against the current text. There is no style-based "AI detector": it cannot tell a
student from a model, and a verdict built on it would be a guess presented as a measurement.

Gradient of assistance:
   - 0-15%: Socratic Advisor only (0% text intervention)
   - 16-35%: Strict Orthographic/Grammar Check (exempt under COPE/ICMJE)
   - 36-60%: Academic Style & Cohesion Polish (exempt under COPE/ICMJE)
   - 61-80%: Hybrid Co-Writing / Topic-Sentence Expansion with Verified Quote
   - 81-100%: Full Paragraph Synthesis Strictly Anchored in Verified Quotes (`quote` + `page`)
"""
from __future__ import annotations

import math
import re
from typing import Any

from .coherence import extract_plain_text
from .llm_gateway import call_json, text_schema
from .pipeline.llm import LLMClient
from .provenance import LIMITS, attribute, percentages

# Canonical Portuguese LLM transition formulas and synthetic academic clichés
PT_LLM_MARKERS: list[str] = [
    "vale ressaltar que",
    "cabe destacar que",
    "nesse sentido",
    "sob essa ótica",
    "diante do exposto",
    "em suma",
    "outrossim",
    "é fundamental compreender",
    "desempenha um papel crucial",
    "desempenha papel fundamental",
    "no que tange a",
    "em última análise",
    "sob a perspectiva teórico-metodológica",
    "no contexto contemporâneo",
    "a literatura demonstra a centralidade de",
    "de modo complementar",
    "em consonância com o recorte de",
    "ademais, a articulação com",
    "é imperativo considerar",
    "à luz dessas considerações",
    "torna-se evidente que",
    "por conseguinte",
    "nessa perspectiva",
    "de relevância central",
]


def count_words(text: str) -> int:
    if not text or not text.strip():
        return 0
    return len(re.findall(r"\S+", text.strip()))


def split_sentences(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    raw = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [s.strip() for s in raw if s and count_words(s) >= 2]


def cliche_markers(text: str) -> list[str]:
    """Stock transition formulas found in `text`. Used ONLY to check the system's own generated output (and to
    steer prompts away from them): it says nothing about who wrote a student's text."""
    low = (text or "").lower()
    return [m for m in PT_LLM_MARKERS if m in low]


def _legacy_counters(content: dict[str, Any]) -> dict[str, int]:
    meta = content.get("_authorship") if isinstance(content.get("_authorship"), dict) else {}
    return {
        "ai_drafted_words": max(0, int(meta.get("ai_drafted_words", 0) or 0)),
        "polished_words": max(0, int(meta.get("polished_words", 0) or 0)),
        "last_intensity": int(meta.get("last_intensity", 0) or 0),
    }


def _event_summary(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"id": e.get("id"), "kind": e["kind"], "words": e.get("words", 0), "source": e.get("source"),
         "declared": e.get("declared"), "created_at": e.get("created_at")}
        for e in events if e["kind"] != "legacy_counters"
    ]


def compute_section_authorship(
    section: dict[str, Any],
    verified_quotes: list[str] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Who wrote what in one section, from the provenance ledger (`events`) and the section's current text.

    `events=None` means the caller has no ledger: the old word counters kept inside the section are used and
    `basis` says "counters". With a ledger, `basis` is "ledger".
    """
    content = section.get("content") if isinstance(section.get("content"), dict) else {}
    legacy = _legacy_counters(content)
    plain = extract_plain_text(content)

    if events is None:
        total_words = count_words(plain)
        ai = min(total_words, legacy["ai_drafted_words"])
        pol = min(max(0, total_words - ai), legacy["polished_words"])
        words = {"total_words": total_words, "ai_drafted_words": ai, "polished_words": pol,
                 "human_words": max(0, total_words - ai - pol), "ai_revised_words": 0, "pasted_words": 0,
                 "quoted_words": 0, "declared_own_words": 0}
        basis = "counters"
    else:
        words = attribute(content, events, verified_quotes or [])
        basis = "ledger"
    pct = percentages(words, words["total_words"])

    pasted_events = [e for e in events or [] if e["kind"] == "paste" and not e.get("declared")]
    requires_disclosure = bool(words["ai_drafted_words"] or words["ai_revised_words"] or words["pasted_words"])
    notes: list[str] = []
    if words["pasted_words"]:
        notes.append(
            f"{words['pasted_words']} palavras foram coladas de fora do editor. Se o texto é seu, marque-o como "
            "“texto meu”; se é de uma fonte, cite-a."
        )
    if words["ai_revised_words"]:
        notes.append(
            f"{words['ai_revised_words']} palavras estão em parágrafos que partiram de um rascunho da IA e foram "
            "reescritos por você. Isso continua sendo uso de IA e deve constar na declaração."
        )
    return {
        **words,
        **pct,
        "last_intensity": legacy["last_intensity"],
        "requires_disclosure": requires_disclosure,
        "basis": basis,
        "notes": notes,
        "limits": LIMITS,
        "events": _event_summary(events or []),
        "pending_paste_events": [e["id"] for e in pasted_events],
    }


def compute_project_authorship(
    sections: list[dict[str, Any]],
    verified_quotes: list[str] | None = None,
    events_by_section: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    keys = ["total", "human", "polished", "ai_drafted", "ai_revised", "pasted", "quoted", "declared_own"]
    sums = {k: 0 for k in keys}
    any_counters = False
    for s in sections:
        ev = None if events_by_section is None else events_by_section.get(s["id"], [])
        st = compute_section_authorship(s, verified_quotes=verified_quotes, events=ev)
        any_counters = any_counters or st["basis"] == "counters"
        for k in keys:
            sums[k] += st[f"{k}_words"]
    total = sums["total"]
    words = {f"{k}_words": v for k, v in sums.items()}
    pct = percentages(words, total)
    requires_disclosure = bool(sums["ai_drafted"] or sums["ai_revised"] or sums["pasted"])
    if requires_disclosure:
        parts = []
        if sums["ai_drafted"]:
            parts.append(f"{pct['ai_drafted_pct']}% redigido com IA")
        if sums["ai_revised"]:
            parts.append(f"{pct['ai_revised_pct']}% rascunho de IA reescrito")
        if sums["pasted"]:
            parts.append(f"{pct['pasted_pct']}% colado de fora")
        status_label = "Declaração obrigatória (" + " · ".join(parts) + ")"
    elif sums["polished"]:
        status_label = "Isento de nota de geração textual (revisão leve registrada)"
    else:
        status_label = "Nenhum uso de IA generativa registrado no editor"
    return {
        **words,
        **pct,
        "requires_disclosure": requires_disclosure,
        "status_label": status_label,
        "basis": "counters" if any_counters else "ledger",
        "limits": LIMITS,
    }


# ---------------------------------------------------------------------------
# Writing assistance generators
#
# Contract: with an LLM client, these call the model through the gateway and raise
# `LLMUnavailable` on failure (the endpoint decides how to degrade and tells the student).
# With client=None they return an honest, non-generative result:
#   - polish: mechanical cleanup only (spacing, punctuation spacing, capitalization);
#   - coauthor / draft: a scaffold with the verified quote(s) and explicit [lacunas] the
#     student must fill. No filler prose, and none of the PT_LLM_MARKERS clichés, so the
#     product's own output never trips its own forensic validator.
# ---------------------------------------------------------------------------

_STYLE_RULES = (
    "Escreva em português brasileiro, norma culta acadêmica, com frases de tamanho variado. "
    "Nunca invente fatos, autores, anos ou páginas. Evite fórmulas de transição genéricas, como: "
    + "; ".join(f"“{m}”" for m in PT_LLM_MARKERS[:14])
    + "."
)


def _cite(doc: dict[str, Any], page: Any) -> tuple[str, str]:
    """Return (surname, parenthetical_ref), e.g. ('Moran', '(Moran, 2015, p. 12)')."""
    authors = doc.get("authors") or []
    surname = authors[0].split(" ")[-1] if authors else (doc.get("title") or "Fonte").split(" ")[0]
    year = doc.get("year") or "s.d."
    return surname, f"({surname}, {year}, p. {page})"


def mechanical_cleanup(text: str, capitalize_first: bool = True) -> str:
    """Non-generative copy-edit: whitespace, spacing around punctuation and sentence capitalization.
    Never substitutes words. `capitalize_first=False` for text that continues a previous node."""
    lead = text[: len(text) - len(text.lstrip())] if not capitalize_first else ""
    trail = text[len(text.rstrip()):][:1]  # keep one boundary space so adjacent TipTap nodes don't glue
    t = text.strip()
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" +([,.;:!?])", r"\1", t)
    t = re.sub(r"([,;:!?])(?=[A-Za-zÀ-ÿ])", r"\1 ", t)
    t = re.sub(r"([.!?]\s+)([a-zà-ÿ])", lambda m: m.group(1) + m.group(2).upper(), t)
    if capitalize_first and t and t[0].islower():
        t = t[0].upper() + t[1:]
    return lead + t + trail


def polish_academic_text(
    text: str,
    section_title: str,
    instruction: str | None = None,
    intensity: int = 45,
    client: LLMClient | None = None,
) -> str:
    """Gradient 16-60%: orthography/grammar (<=35%) or academic register (36-60%), never new claims."""
    cleaned = text.strip()
    if not cleaned:
        return ""
    if client is None:
        return mechanical_cleanup(cleaned)

    level = (
        "apenas correção ortográfica e gramatical mínima, sem trocar vocabulário"
        if intensity <= 35
        else "clareza, concisão e registro acadêmico, preservando 100% do sentido e a voz do autor"
    )
    system = (
        "Você é um revisor acadêmico. Revise o trecho do aluno sem acrescentar ideias, dados ou referências. "
        + _STYLE_RULES
    )
    user = (
        f"Nível de intervenção ({intensity}%): {level}.\n"
        f"Seção: {section_title}\n"
        f"Instrução do aluno: {instruction or 'Revisão acadêmica'}\n\n"
        f"Trecho do aluno:\n{cleaned}\n\n"
        'Responda em JSON: {"polished_text": "..."}'
    )
    res = call_json(client, system, user, text_schema("polished_text"), operation="polish")
    return str(res["polished_text"]).strip()


def coauthor_with_evidence(
    student_premise: str,
    claims: list[dict[str, Any]],
    docs_by_id: dict[str, dict[str, Any]],
    section_title: str,
    instruction: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Gradient 61-80%: keep the student's premise and connect it to one verified quote."""
    premise = student_premise.strip()
    if premise and not premise.endswith((".", "!", "?")):
        premise += "."
    c = claims[0]
    doc = docs_by_id.get(c["document_id"]) or {}
    surname, ref = _cite(doc, c.get("page_no", 1))
    quote = c.get("quote", "").strip().rstrip(".")
    concept = c.get("concept") or "o conceito em análise"

    if client is None:
        opening = premise or "[Escreva aqui a sua afirmação principal para este parágrafo.]"
        return (
            f"{opening} {surname} afirma que “{quote}” {ref}. "
            f"[Explique com suas palavras por que esse trecho sobre {concept.lower()} sustenta, "
            "ou limita, a sua afirmação.]"
        )

    system = (
        "Você é um coautor acadêmico em modo híbrido. Mantenha a premissa do aluno como abertura e "
        "desenvolva o argumento conectando-a à citação literal fornecida, que deve aparecer entre aspas "
        "com a referência exatamente como dada. Use somente essa evidência. " + _STYLE_RULES
    )
    user = (
        f"Seção: {section_title}\n"
        f"Premissa do aluno: {premise or '(não informada)'}\n"
        f"Instrução: {instruction or 'Costurar a evidência mantendo a voz do aluno'}\n"
        f"Citação verificada sobre {concept}: “{quote}” {ref}\n\n"
        'Responda em JSON: {"coauthored_paragraph": "..."}'
    )
    res = call_json(client, system, user, text_schema("coauthored_paragraph"), operation="coauthor")
    return str(res["coauthored_paragraph"]).strip()


def draft_evidence_paragraph(
    claims: list[dict[str, Any]],
    docs_by_id: dict[str, dict[str, Any]],
    section_title: str,
    instruction: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Gradient 81-100%: paragraph strictly anchored in verified literal quotes (quote + page)."""
    selected = claims[:3]
    items: list[tuple[dict[str, Any], str, str]] = []
    for c in selected:
        doc = docs_by_id.get(c["document_id"]) or {}
        surname, ref = _cite(doc, c.get("page_no", 1))
        items.append((c, surname, ref))

    if client is None:
        lines = [
            "[Abertura: em uma frase, diga o que este parágrafo defende"
            + (f" sobre {instruction.strip().rstrip('.')}" if instruction and instruction.strip() else "")
            + ".]"
        ]
        for c, surname, ref in items:
            quote = c.get("quote", "").strip().rstrip(".")
            lines.append(f"{surname} afirma que “{quote}” {ref}.")
        lines.append(
            "[Fechamento: como essas evidências se relacionam entre si e com o problema da sua pesquisa?]"
        )
        return " ".join(lines)

    evidence = "\n".join(
        f"- Conceito: {c.get('concept')} | Citação literal: “{c.get('quote')}” | Referência: {ref}"
        for c, _, ref in items
    )
    system = (
        "Você é um assistente de redação científica. Redija UM parágrafo acadêmico coeso baseado "
        "EXCLUSIVAMENTE nas citações literais fornecidas, cada uma entre aspas e seguida da referência "
        "exatamente como dada. Não acrescente fontes, dados ou páginas. " + _STYLE_RULES
    )
    user = (
        f"Seção: {section_title}\n"
        f"Orientação do aluno: {instruction or 'Articular os conceitos verificados na seção'}\n"
        f"Evidências verificadas:\n{evidence}\n\n"
        'Responda em JSON: {"draft_paragraph": "..."}'
    )
    res = call_json(client, system, user, text_schema("draft_paragraph"), operation="draft")
    return str(res["draft_paragraph"]).strip()
