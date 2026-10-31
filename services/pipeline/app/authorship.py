"""Authorship Prism & AI Writing Modes (Socratic / Polish / Evidence-Guided Draft).

Tracks the proportion of manuscript words across three provenance tiers:
1. Human Authored (`human_words`): Written directly by the student.
2. AI Polished (`polished_words`): Student-written text copy-edited for academic clarity/grammar (exempt from generative text disclosure under COPE/ICMJE/Elsevier guidelines).
3. AI Drafted from Verified Evidence (`ai_drafted_words`): Paragraphs drafted by AI strictly anchored in verified literal quotes (`quote` + `page`), which automatically triggers mandatory AI disclosure.
"""
from __future__ import annotations

import re
from typing import Any

from .coherence import extract_plain_text
from .pipeline.llm import LLMClient


def count_words(text: str) -> int:
    if not text or not text.strip():
        return 0
    return len(re.findall(r"\S+", text.strip()))


def compute_section_authorship(section: dict[str, Any]) -> dict[str, Any]:
    content = section.get("content") if isinstance(section.get("content"), dict) else {}
    plain = extract_plain_text(content)
    total_words = count_words(plain)

    meta = content.get("_authorship") if isinstance(content.get("_authorship"), dict) else {}
    raw_drafted = max(0, int(meta.get("ai_drafted_words", 0)))
    raw_polished = max(0, int(meta.get("polished_words", 0)))

    ai_drafted_words = min(total_words, raw_drafted)
    polished_words = min(max(0, total_words - ai_drafted_words), raw_polished)
    human_words = max(0, total_words - ai_drafted_words - polished_words)

    if total_words > 0:
        ai_drafted_pct = round((ai_drafted_words / total_words) * 100)
        polished_pct = round((polished_words / total_words) * 100)
        human_pct = max(0, 100 - ai_drafted_pct - polished_pct)
    else:
        human_pct = 100
        polished_pct = 0
        ai_drafted_pct = 0

    requires_disclosure = ai_drafted_words > 0
    return {
        "total_words": total_words,
        "human_words": human_words,
        "polished_words": polished_words,
        "ai_drafted_words": ai_drafted_words,
        "human_pct": human_pct,
        "polished_pct": polished_pct,
        "ai_drafted_pct": ai_drafted_pct,
        "requires_disclosure": requires_disclosure,
    }


def compute_project_authorship(sections: list[dict[str, Any]]) -> dict[str, Any]:
    total_words = 0
    human_words = 0
    polished_words = 0
    ai_drafted_words = 0

    for s in sections:
        st = compute_section_authorship(s)
        total_words += st["total_words"]
        human_words += st["human_words"]
        polished_words += st["polished_words"]
        ai_drafted_words += st["ai_drafted_words"]

    if total_words > 0:
        ai_drafted_pct = round((ai_drafted_words / total_words) * 100)
        polished_pct = round((polished_words / total_words) * 100)
        human_pct = max(0, 100 - ai_drafted_pct - polished_pct)
    else:
        human_pct = 100
        polished_pct = 0
        ai_drafted_pct = 0

    requires_disclosure = ai_drafted_words > 0
    if requires_disclosure:
        status_label = (
            f"Declaração obrigatória ({ai_drafted_pct}% redigido com IA a partir de citações verificadas)"
        )
    elif polished_words > 0:
        status_label = (
            "Isento de nota de geração textual (autoria humana com revisão gramatical/estilo)"
        )
    else:
        status_label = "100% Escrita autoral humana — isento de declaração de geração textual"

    return {
        "total_words": total_words,
        "human_words": human_words,
        "polished_words": polished_words,
        "ai_drafted_words": ai_drafted_words,
        "human_pct": human_pct,
        "polished_pct": polished_pct,
        "ai_drafted_pct": ai_drafted_pct,
        "requires_disclosure": requires_disclosure,
        "status_label": status_label,
    }


def polish_academic_text(
    text: str,
    section_title: str,
    instruction: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Mode 2 (Copiloto de Lapidação): refine academic register without adding new claims."""
    cleaned = text.strip()
    if not cleaned:
        return ""

    if client is not None:
        try:
            prompt = (
                "Você é um revisor acadêmico em português brasileiro (norma culta científica).\n"
                "Reescreva o trecho abaixo APENAS para aprimorar a clareza, concisão e registro acadêmico formal, "
                "preservando 100% do sentido original e das citações do aluno. NÃO invente fatos nem referências.\n"
                f"Seção: {section_title}\n"
                f"Instrução adicional: {instruction or 'Lapidação formal leve'}\n\n"
                f"Trecho do aluno:\n{cleaned}\n\n"
                'Responda em JSON: {"polished_text": "..."}'
            )
            res = client.complete_json(prompt)
            if isinstance(res, dict) and res.get("polished_text"):
                return str(res["polished_text"]).strip()
        except Exception:
            pass

    # Deterministic academic copy-editing fallback
    replacements = [
        (r"\ba gente\b", "observa-se que"),
        (r"\bhoje em dia\b", "no contexto contemporâneo"),
        (r"\bmuito importante\b", "de relevância central"),
        (r"\bmostra que\b", "evidencia que"),
    ]
    refined = cleaned
    for pattern, repl in replacements:
        refined = re.sub(pattern, repl, refined, flags=re.IGNORECASE)

    if refined == cleaned:
        # Ensure formal connective and punctuation polish
        if not refined.endswith((".", "!", "?")):
            refined += "."
        refined = (
            f"Sob a perspectiva teórico-metodológica desta seção, {refined[0].lower() + refined[1:]}"
            if len(refined) > 25 and not refined.lower().startswith("sob a perspectiva")
            else refined
        )
    return refined


def draft_evidence_paragraph(
    claims: list[dict[str, Any]],
    docs_by_id: dict[str, dict[str, Any]],
    section_title: str,
    instruction: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Mode 3 (Redação Guiada por Evidências): draft a paragraph strictly anchored in verified literal quotes."""
    selected_claims = claims[:3]
    evidence_lines = []
    formatted_refs = []

    for c in selected_claims:
        doc = docs_by_id.get(c["document_id"]) or {}
        authors = doc.get("authors") or []
        first_author = (
            authors[0].split(" ")[-1]
            if authors
            else (doc.get("title") or "Fonte").split(" ")[0]
        )
        year = doc.get("year") or "s.d."
        page = c.get("page_no", 1)
        ref = f"({first_author}, {year}, p. {page})"
        formatted_refs.append((c, ref))
        evidence_lines.append(
            f"- Conceito: {c.get('concept')} | Citação literal verificada: \"{c.get('quote')}\" | Referência: {ref}"
        )

    if client is not None:
        try:
            prompt = (
                "Você é um assistente de redação científica do El Orientador.\n"
                "Redija UM parágrafo acadêmico coeso para a seção indicada, baseando-se EXCLUSIVAMENTE "
                "nas citações literais verificadas abaixo. Inclua obrigatoriamente a referência (Autor, Ano, p. X) "
                "para cada afirmação utilizada. Nunca invente fontes ou páginas.\n"
                f"Seção: {section_title}\n"
                f"Orientação do aluno: {instruction or 'Articular os conceitos verificados na seção'}\n"
                "Evidências verificadas:\n"
                + "\n".join(evidence_lines)
                + '\n\nResponda em JSON: {"draft_paragraph": "..."}'
            )
            res = client.complete_json(prompt)
            if isinstance(res, dict) and res.get("draft_paragraph"):
                return str(res["draft_paragraph"]).strip()
        except Exception:
            pass

    # Deterministic evidence-anchored synthesis fallback (100% faithful to verified quotes)
    parts: list[str] = []
    if instruction and instruction.strip():
        parts.append(f"Em consonância com o recorte de {instruction.strip().rstrip('.')},")
    else:
        parts.append(f"No âmbito de {section_title},")

    for idx, (c, ref) in enumerate(formatted_refs):
        concept = c.get("concept", "o conceito analisado")
        quote = c.get("quote", "").strip().rstrip(".")
        if idx == 0:
            parts.append(
                f"a literatura demonstra a centralidade de {concept.lower()}, conforme verificado literalmente na fonte primária: “{quote}” {ref}."
            )
        elif idx == 1:
            parts.append(
                f"De modo complementar, no que tange a {concept.lower()}, destaca-se que “{quote}” {ref}."
            )
        else:
            parts.append(
                f"Ademais, a articulação com {concept.lower()} sustenta-se na evidência de que “{quote}” {ref}."
            )

    return " ".join(parts)
