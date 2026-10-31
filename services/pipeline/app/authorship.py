"""Authorship Prism, Continuous Autonomy Gradient (0-100%) & Forensic AI Text Validator.

Combines two complementary verification layers:
1. Provenance Telemetry (`human_words`, `polished_words`, `ai_drafted_words`) across a continuous 0-100% autonomy gradient:
   - 0-15%: Socratic Advisor only (0% text intervention)
   - 16-35%: Strict Orthographic/Grammar Check (exempt under COPE/ICMJE)
   - 36-60%: Academic Style & Cohesion Polish (exempt under COPE/ICMJE)
   - 61-80%: Hybrid Co-Writing / Topic-Sentence Expansion with Verified Quote
   - 81-100%: Full Paragraph Synthesis Strictly Anchored in Verified Quotes (`quote` + `page`)
2. Deterministic Stylometric & Forensic Validator (`validate_section_authenticity`):
   - Evaluates the actual manuscript text sentence-by-sentence using syntactic burstiness (coefficient of variation of sentence lengths), lexical entropy (Type-Token Ratio), canonical LLM transition clichés in Portuguese, and verified citation anchoring.
   - Detects unlogged external AI paste (e.g., ChatGPT copy-paste) or human rewriting of prior AI drafts.
"""
from __future__ import annotations

import math
import re
from typing import Any

from .coherence import extract_plain_text
from .pipeline.llm import LLMClient

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


def analyze_text_forensics(
    plain_text: str,
    verified_quotes: list[str] | None = None,
) -> dict[str, Any]:
    """Deterministic stylometric & forensic validator to verify whether text is genuinely human or AI-written."""
    sentences = split_sentences(plain_text)
    total_words = count_words(plain_text)
    verified_quotes_norm = [
        q.strip().lower()[:40] for q in (verified_quotes or []) if q and len(q.strip()) >= 12
    ]

    if not sentences or total_words == 0:
        return {
            "measured_ai_score": 0,
            "measured_human_pct": 100,
            "measured_hybrid_pct": 0,
            "measured_ai_pct": 0,
            "burstiness_score": 100,
            "burstiness_cv": 0.0,
            "lexical_diversity_score": 100,
            "llm_markers_found": [],
            "verdict_code": "empty",
            "verdict_label": "Sem texto suficiente para validação forense",
            "sentences": [],
        }

    lengths = [count_words(s) for s in sentences]
    mean_len = sum(lengths) / len(lengths)
    if len(lengths) >= 2 and mean_len > 0:
        variance = sum((x - mean_len) ** 2 for x in lengths) / len(lengths)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean_len
        # Also measure adjacent sentence length jumps (human burstiness)
        adj_diffs = [abs(lengths[i] - lengths[i - 1]) for i in range(1, len(lengths))]
        mean_jump = (sum(adj_diffs) / len(adj_diffs)) / max(1.0, mean_len)
        effective_cv = (cv * 0.65) + (mean_jump * 0.35)
    else:
        # Single sentence: evaluate whether it sits right in the synthetic 18-28 word sweet spot
        single_len = lengths[0]
        effective_cv = 0.22 if 17 <= single_len <= 30 else 0.42

    # Convert effective_cv into a 0..100 human burstiness score (CV >= 0.42 => ~90+, CV <= 0.16 => ~20)
    burstiness_score = int(max(10, min(98, round((effective_cv / 0.45) * 85 + 10))))

    # Lexical diversity (content words >= 4 chars)
    words_clean = [
        w.lower()
        for w in re.findall(r"[a-zà-úç]+", plain_text.lower())
        if len(w) >= 4
    ]
    if words_clean:
        # Windowed TTR so long texts aren't unfairly penalized
        window = 60
        if len(words_clean) <= window:
            ttr = len(set(words_clean)) / len(words_clean)
        else:
            ratios = [
                len(set(words_clean[i : i + window])) / window
                for i in range(0, len(words_clean) - window + 1, 20)
            ]
            ttr = sum(ratios) / len(ratios)
        lexical_diversity_score = int(max(15, min(99, round(ttr * 115))))
    else:
        lexical_diversity_score = 80

    all_markers_found: list[str] = []
    sentence_reports: list[dict[str, Any]] = []

    human_s_words = 0
    hybrid_s_words = 0
    ai_s_words = 0
    weighted_prob_sum = 0.0

    for idx, sent in enumerate(sentences):
        s_lower = sent.lower()
        s_words = lengths[idx]
        reasons: list[str] = []
        sent_ai_prob = 18  # baseline low probability

        # 1. Check canonical LLM markers in this sentence
        matched_markers = [m for m in PT_LLM_MARKERS if m in s_lower]
        for m in matched_markers:
            if m not in all_markers_found:
                all_markers_found.append(m)
        if matched_markers:
            sent_ai_prob += 34 + 14 * (len(matched_markers) - 1)
            reasons.append(
                f"Fórmula de transição típica de IA: “{matched_markers[0]}”"
            )

        # 2. Check sentence length uniformity (LLM sweet spot: 17-27 words with low jump from neighbors)
        neighbor_diff = (
            abs(s_words - lengths[idx - 1]) if idx > 0 else (abs(s_words - lengths[1]) if len(lengths) > 1 else 0)
        )
        if 17 <= s_words <= 29 and (len(lengths) == 1 or neighbor_diff <= 4):
            sent_ai_prob += 18
            reasons.append(f"Cadência sintática uniforme ({s_words} palavras)")
        elif s_words <= 11 or s_words >= 36 or neighbor_diff >= 10:
            sent_ai_prob -= 12
            reasons.append(f"Variação sintática natural (burstiness alta: {s_words} palavras)")

        # 3. Check passive/impersonal synthetic openers
        if re.match(
            r"^(observa-se que|evidencia-se que|constata-se que|verifica-se que|destaca-se que|nota-se que)\b",
            s_lower,
        ):
            sent_ai_prob += 16
            reasons.append("Abertura impessoal padronizada")

        # 4. Check if sentence contains a literal quote with page citation
        has_page_ref = bool(re.search(r"\([^)]*\d{4}[^)]*p\.\s*\d+\)", sent))
        has_verified_sub = any(vq in s_lower for vq in verified_quotes_norm)
        if has_page_ref or has_verified_sub:
            reasons.append("Contém ancoragem em citação verificada (Autor, Ano, p. X)")

        # 5. Global burstiness adjustment
        if burstiness_score < 42:
            sent_ai_prob += 12
        elif burstiness_score >= 70:
            sent_ai_prob -= 8

        sent_ai_prob = int(max(4, min(96, sent_ai_prob)))
        weighted_prob_sum += sent_ai_prob * s_words

        if sent_ai_prob >= 62:
            classification = "ai_pattern"
            ai_s_words += s_words
            if not reasons:
                reasons.append("Baixa entropia sintática e estrutura típica de geração automática")
        elif sent_ai_prob >= 36:
            classification = "hybrid"
            hybrid_s_words += s_words
            if not reasons:
                reasons.append("Estrutura híbrida (autoria humana com polimento formal)")
        else:
            classification = "human"
            human_s_words += s_words
            if not reasons:
                reasons.append("Assinatura estilométrica humana autêntica")

        sentence_reports.append(
            {
                "index": idx,
                "text": sent,
                "word_count": s_words,
                "ai_probability": sent_ai_prob,
                "classification": classification,
                "reasons": reasons,
                "has_verified_citation": has_page_ref or has_verified_sub,
            }
        )

    measured_ai_score = int(round(weighted_prob_sum / max(1, total_words)))
    measured_ai_pct = int(round((ai_s_words / max(1, total_words)) * 100))
    measured_hybrid_pct = int(round((hybrid_s_words / max(1, total_words)) * 100))
    measured_human_pct = max(0, 100 - measured_ai_pct - measured_hybrid_pct)

    if measured_ai_score >= 62 or measured_ai_pct >= 50:
        verdict_code = "ai_dominant"
        verdict_label = f"Predominância de padrão generativo de IA ({measured_ai_score}% índice estilométrico)"
    elif measured_ai_score >= 36 or (measured_ai_pct + measured_hybrid_pct) >= 45:
        verdict_code = "hybrid"
        verdict_label = f"Escrita híbrida / polida com assistência ({measured_ai_score}% índice estilométrico)"
    else:
        verdict_code = "human_dominant"
        verdict_label = f"Escrita humana autêntica ({100 - measured_ai_score}% naturalidade estilométrica)"

    return {
        "measured_ai_score": measured_ai_score,
        "measured_human_pct": measured_human_pct,
        "measured_hybrid_pct": measured_hybrid_pct,
        "measured_ai_pct": measured_ai_pct,
        "burstiness_score": burstiness_score,
        "burstiness_cv": round(effective_cv, 2),
        "lexical_diversity_score": lexical_diversity_score,
        "llm_markers_found": all_markers_found,
        "verdict_code": verdict_code,
        "verdict_label": verdict_label,
        "sentences": sentence_reports,
    }


def compute_section_authorship(
    section: dict[str, Any],
    verified_quotes: list[str] | None = None,
) -> dict[str, Any]:
    content = section.get("content") if isinstance(section.get("content"), dict) else {}
    plain = extract_plain_text(content)
    total_words = count_words(plain)

    meta = content.get("_authorship") if isinstance(content.get("_authorship"), dict) else {}
    raw_drafted = max(0, int(meta.get("ai_drafted_words", 0)))
    raw_polished = max(0, int(meta.get("polished_words", 0)))
    last_intensity = int(meta.get("last_intensity", 0))

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

    forensics = analyze_text_forensics(plain, verified_quotes=verified_quotes)

    # Detect discrepancy between logged internal usage and real forensic stylometry
    telemetry_discrepancy = False
    discrepancy_message = None
    if total_words >= 12:
        if forensics["measured_ai_pct"] >= 40 and ai_drafted_pct < 15:
            telemetry_discrepancy = True
            discrepancy_message = (
                f"Validador detectou {forensics['measured_ai_pct']}% de sentenças com padrão sintático de IA "
                f"(score {forensics['measured_ai_score']}%), mas apenas {ai_drafted_pct}% foi registrado no editor interno "
                "(possível colagem de IA externa ou uso intenso de clichês generativos)."
            )
        elif forensics["measured_ai_pct"] <= 10 and ai_drafted_pct >= 50:
            telemetry_discrepancy = True
            discrepancy_message = (
                "O texto registrado como rascunho de IA apresenta hoje alta naturalidade humana "
                f"(burstiness {forensics['burstiness_score']}/100). Você pode sincronizar o Prisma para refletir sua reescrita autoral."
            )

    requires_disclosure = ai_drafted_words > 0 or forensics["measured_ai_pct"] >= 50
    return {
        "total_words": total_words,
        "human_words": human_words,
        "polished_words": polished_words,
        "ai_drafted_words": ai_drafted_words,
        "human_pct": human_pct,
        "polished_pct": polished_pct,
        "ai_drafted_pct": ai_drafted_pct,
        "last_intensity": last_intensity,
        "requires_disclosure": requires_disclosure,
        "forensics": forensics,
        "telemetry_discrepancy": telemetry_discrepancy,
        "discrepancy_message": discrepancy_message,
    }


def compute_project_authorship(
    sections: list[dict[str, Any]],
    verified_quotes: list[str] | None = None,
) -> dict[str, Any]:
    total_words = 0
    human_words = 0
    polished_words = 0
    ai_drafted_words = 0
    weighted_forensic_ai = 0.0
    weighted_burstiness = 0.0
    all_markers: list[str] = []
    any_discrepancy = False

    for s in sections:
        st = compute_section_authorship(s, verified_quotes=verified_quotes)
        w = st["total_words"]
        total_words += w
        human_words += st["human_words"]
        polished_words += st["polished_words"]
        ai_drafted_words += st["ai_drafted_words"]
        f = st["forensics"]
        weighted_forensic_ai += f["measured_ai_score"] * w
        weighted_burstiness += f["burstiness_score"] * w
        for m in f["llm_markers_found"]:
            if m not in all_markers:
                all_markers.append(m)
        if st["telemetry_discrepancy"]:
            any_discrepancy = True

    if total_words > 0:
        ai_drafted_pct = round((ai_drafted_words / total_words) * 100)
        polished_pct = round((polished_words / total_words) * 100)
        human_pct = max(0, 100 - ai_drafted_pct - polished_pct)
        measured_ai_score = int(round(weighted_forensic_ai / total_words))
        burstiness_score = int(round(weighted_burstiness / total_words))
    else:
        human_pct = 100
        polished_pct = 0
        ai_drafted_pct = 0
        measured_ai_score = 0
        burstiness_score = 100

    requires_disclosure = ai_drafted_words > 0 or measured_ai_score >= 60
    if requires_disclosure:
        status_label = (
            f"Declaração obrigatória ({ai_drafted_pct}% redigido com IA · {measured_ai_score}% índice forense)"
        )
    elif polished_words > 0:
        status_label = (
            f"Isento de nota de geração textual (revisão leve · {100 - measured_ai_score}% naturalidade humana)"
        )
    else:
        status_label = (
            f"100% Escrita autoral humana ({100 - measured_ai_score}% naturalidade estilométrica)"
        )

    return {
        "total_words": total_words,
        "human_words": human_words,
        "polished_words": polished_words,
        "ai_drafted_words": ai_drafted_words,
        "human_pct": human_pct,
        "polished_pct": polished_pct,
        "ai_drafted_pct": ai_drafted_pct,
        "measured_ai_score": measured_ai_score,
        "burstiness_score": burstiness_score,
        "llm_markers_found": all_markers,
        "telemetry_discrepancy": any_discrepancy,
        "requires_disclosure": requires_disclosure,
        "status_label": status_label,
    }


def polish_academic_text(
    text: str,
    section_title: str,
    instruction: str | None = None,
    intensity: int = 45,
    client: LLMClient | None = None,
) -> str:
    """Mode 2 (16-60% Gradient): refine orthography/grammar (16-35%) or academic register (36-60%)."""
    cleaned = text.strip()
    if not cleaned:
        return ""

    if client is not None:
        try:
            level_desc = (
                "apenas correção ortográfica e gramatical mínima sem alterar vocabulário"
                if intensity <= 35
                else "aprimoramento de clareza, concisão e registro acadêmico formal preservando 100% do sentido"
            )
            prompt = (
                "Você é um revisor acadêmico em português brasileiro (norma culta científica).\n"
                f"Nível de intervenção ({intensity}%): realize {level_desc}. "
                "NÃO invente fatos nem referências.\n"
                f"Seção: {section_title}\n"
                f"Instrução adicional: {instruction or 'Revisão acadêmica'}\n\n"
                f"Trecho do aluno:\n{cleaned}\n\n"
                'Responda em JSON: {"polished_text": "..."}'
            )
            res = client.complete_json(prompt)
            if isinstance(res, dict) and res.get("polished_text"):
                return str(res["polished_text"]).strip()
        except Exception:
            pass

    # Deterministic academic copy-editing fallback scaled by intensity
    light_replacements = [
        (r"\ba gente\b", "observa-se que"),
        (r"\bhoje em dia\b", "atualmente"),
        (r"\bpra\b", "para"),
    ]
    deep_replacements = [
        (r"\ba gente\b", "observa-se que"),
        (r"\bhoje em dia\b", "no contexto contemporâneo"),
        (r"\bmuito importante\b", "de relevância central"),
        (r"\bmostra que\b", "evidencia que"),
    ]
    replacements = light_replacements if intensity <= 35 else deep_replacements
    refined = cleaned
    for pattern, repl in replacements:
        refined = re.sub(pattern, repl, refined, flags=re.IGNORECASE)

    if not refined.endswith((".", "!", "?")):
        refined += "."

    if refined == cleaned and intensity > 35:
        refined = (
            f"Sob a perspectiva teórico-metodológica desta seção, {refined[0].lower() + refined[1:]}"
            if len(refined) > 25 and not refined.lower().startswith("sob a perspectiva")
            else refined
        )
    return refined


def coauthor_with_evidence(
    student_premise: str,
    claims: list[dict[str, Any]],
    docs_by_id: dict[str, dict[str, Any]],
    section_title: str,
    instruction: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Gradient 61-80% (Co-escrita Híbrida): preserves the student's opening premise and weaves 1 verified quote."""
    premise = student_premise.strip()
    if premise and not premise.endswith((".", "!", "?")):
        premise += "."

    c = claims[0]
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
    quote = c.get("quote", "").strip().rstrip(".")
    concept = c.get("concept", "o conceito em análise")

    if client is not None:
        try:
            prompt = (
                "Você é um coautor acadêmico no modo híbrido (61-80% de assistência).\n"
                "Mantenha a premissa original escrita pelo aluno e expanda o argumento conectando-a "
                f"à citação literal verificada abaixo sobre {concept}: \"{quote}\" {ref}.\n"
                f"Premissa do aluno: {premise}\n"
                f"Instrução: {instruction or 'Costurar evidência mantendo a voz do aluno'}\n"
                'Responda em JSON: {"coauthored_paragraph": "..."}'
            )
            res = client.complete_json(prompt)
            if isinstance(res, dict) and res.get("coauthored_paragraph"):
                return str(res["coauthored_paragraph"]).strip()
        except Exception:
            pass

    if premise:
        return (
            f"{premise} Essa proposição encontra respaldo direto na evidência sobre {concept.lower()}, "
            f"segundo a qual “{quote}” {ref}."
        )
    return (
        f"Ao articular {concept.lower()} no âmbito de {section_title}, "
        f"verifica-se na fonte primária que “{quote}” {ref}."
    )


def draft_evidence_paragraph(
    claims: list[dict[str, Any]],
    docs_by_id: dict[str, dict[str, Any]],
    section_title: str,
    instruction: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Gradient 81-100% (Redação Guiada por Evidências): draft a paragraph strictly anchored in verified literal quotes."""
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
