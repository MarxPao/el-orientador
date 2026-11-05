"""Guided Text Analysis, Multi-PDF Triangulation & Dialectical Connection Engine.

Helps the student:
1. Dissect an uploaded PDF/article into rhetorical-scientific layers (Conceptual Definition, Empirical Evidence, Method/Scope, Caveat/Limitation) with step-by-step Socratic reading questions.
2. Compare two texts/passages side by side (Convergences, Scope Nuances, Tensions) and guide the student's own critical analysis.
3. Audit the student's manuscript for the "Boxcar Effect" (Efeito Vagão de Trem: isolated single-author paragraphs without analytical synthesis) and weave connected paragraphs anchored in verified quotes (`quote` + `page`).
"""
from __future__ import annotations

import re
from typing import Any

from .coherence import extract_plain_text
from .llm_gateway import LLMUnavailable, call_json, text_schema
from .pipeline.llm import LLMClient
from .pipeline.verify_quotes import verify_quote


def classify_passage_role(statement: str, quote: str) -> dict[str, str]:
    """Classify a verified quote by its rhetorical-scientific role to teach the student how to read the paper."""
    combined = f"{statement} {quote}".lower()
    if any(
        kw in combined
        for kw in [
            " %",
            "%",
            "dados",
            "amostra",
            "resultado",
            "evidencia",
            "eleva",
            "reduz",
            "observou-se",
            "empíric",
            "taxa",
            "pesquisa com",
        ]
    ):
        return {
            "role_code": "evidencia_empirica",
            "role_label": "Evidência Empírica / Achado",
            "reading_tip": "Use este trecho para comprovar com dados concretos um argumento que você abriu no parágrafo.",
        }
    if any(
        kw in combined
        for kw in [
            "entretanto",
            "contudo",
            "todavia",
            "limite",
            "limitação",
            "ressalva",
            "não garante",
            "depende de",
            "apenas quando",
            "desafio",
            "lacuna",
        ]
    ):
        return {
            "role_code": "limite_contraponto",
            "role_label": "Ressalva / Limite Crítico",
            "reading_tip": "Excelente para mostrar maturidade crítica: aponte até onde a teoria funciona e onde começa o seu problema de pesquisa.",
        }
    if any(
        kw in combined
        for kw in [
            "método",
            "metodologia",
            "estudo de caso",
            "revisão",
            "entrevista",
            "questionário",
            "recorte",
            "procedimento",
        ]
    ):
        return {
            "role_code": "metodo_recorte",
            "role_label": "Método / Recorte do Estudo",
            "reading_tip": "Compare o contexto em que o autor coletou os dados com o contexto do seu trabalho antes de generalizar.",
        }
    return {
        "role_code": "definicao_conceitual",
        "role_label": "Definição / Lente Teórica",
        "reading_tip": "Use para definir o conceito-chave antes de confrontá-lo com estudos empíricos de outros autores.",
    }


def format_author_ref(doc: dict[str, Any], page_no: int) -> str:
    authors = doc.get("authors") or []
    first_author = (
        authors[0].split(" ")[-1]
        if authors
        else (doc.get("title") or "Fonte").split(" ")[0]
    )
    year = doc.get("year") or "s.d."
    return f"({first_author}, {year}, p. {page_no})"


def analyze_project_texts(
    project: dict[str, Any],
    documents: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a complete Guided Text Analysis & Comparison workspace for all uploaded PDFs and manuscript sections."""
    docs_by_id = {d["id"]: d for d in documents}
    project_title = project.get("title", "seu projeto")

    # 1. Enrich each claim with rhetorical role, author reference, and analytical prompts
    enriched_claims: list[dict[str, Any]] = []
    claims_by_doc: dict[str, list[dict[str, Any]]] = {d["id"]: [] for d in documents}
    concept_to_docs: dict[str, set[str]] = {}
    concept_labels: dict[str, str] = {}

    for c in claims:
        doc = docs_by_id.get(c["document_id"]) or {}
        role = classify_passage_role(c.get("statement", ""), c.get("quote", ""))
        ref = format_author_ref(doc, c.get("page_no", 1))
        concepts = c.get("concepts") or []
        first_concept = concepts[0]["label"] if concepts else "o conceito central"

        for co in concepts:
            cid = co["id"]
            concept_labels[cid] = co["label"]
            concept_to_docs.setdefault(cid, set()).add(c["document_id"])

        item = {
            "id": c["id"],
            "document_id": c["document_id"],
            "document_title": doc.get("title") or c.get("document_title") or "Documento",
            "authors": doc.get("authors") or c.get("authors") or [],
            "year": doc.get("year") or c.get("year"),
            "page_no": c.get("page_no", 1),
            "citation_ref": ref,
            "statement": c.get("statement", ""),
            "quote": c.get("quote", ""),
            "concepts": concepts,
            "role_code": role["role_code"],
            "role_label": role["role_label"],
            "reading_tip": role["reading_tip"],
            "socratic_prompts": [
                f"Compreensão: Com suas próprias palavras, que mecanismo o autor descreve na p. {c.get('page_no', 1)} sobre {first_concept.lower()}?",
                f"Análise Crítica: Em que contexto essa afirmação {ref} foi observada e qual é o limite dela para {project_title}?",
                f"Conexão: Essa passagem confirma ou tensiona o que você pretendia defender na sua seção atual?",
            ],
        }
        enriched_claims.append(item)
        claims_by_doc.setdefault(c["document_id"], []).append(item)

    # 2. Build Per-Document Guided Dissection Cards ("Raio-X Analítico do PDF")
    document_guides: list[dict[str, Any]] = []
    for doc in documents:
        doc_claims = claims_by_doc.get(doc["id"], [])
        doc_concepts = []
        seen_c: set[str] = set()
        for dc in doc_claims:
            for co in dc["concepts"]:
                if co["id"] not in seen_c:
                    seen_c.add(co["id"])
                    doc_concepts.append(co)

        # Find bridges with other documents in the project
        shared_bridges: list[dict[str, Any]] = []
        for co in doc_concepts:
            other_doc_ids = [
                oid for oid in concept_to_docs.get(co["id"], set()) if oid != doc["id"]
            ]
            for oid in other_doc_ids:
                other_doc = docs_by_id.get(oid)
                if other_doc:
                    shared_bridges.append(
                        {
                            "concept_id": co["id"],
                            "concept_label": co["label"],
                            "other_document_id": oid,
                            "other_document_title": other_doc.get("title") or "Outro documento",
                        }
                    )

        core_thesis = (
            doc_claims[0]["statement"]
            if doc_claims
            else "Documento aguardando extração de trechos verificados."
        )

        document_guides.append(
            {
                "document_id": doc["id"],
                "title": doc.get("title") or "Documento sem título",
                "authors": doc.get("authors") or [],
                "year": doc.get("year"),
                "status": doc.get("status", "ready"),
                "claims_count": len(doc_claims),
                "core_thesis": core_thesis,
                "concepts": doc_concepts,
                "shared_bridges": shared_bridges,
                "study_questions": [
                    f"1. Tese do Autor: Qual é o argumento principal de {doc.get('title') or 'este artigo'} que você não encontraria em um dicionário comum?",
                    "2. Recorte e Evidência: As conclusões do autor vêm de dados empíricos ou de revisão teórica? Isso serve como base teórica ou como comparação de resultados no seu trabalho?",
                    f"3. Posicionamento do Aluno: O que este texto ajuda a responder em “{project_title}” e o que ele deixa em aberto?",
                ],
                "passages": doc_claims,
            }
        )

    # 3. Audit Manuscript Sections for "Boxcar Effect" (Efeito Vagão de Trem) & Analytical Depth
    manuscript_audit = audit_manuscript_structure(sections, enriched_claims)

    return {
        "document_guides": document_guides,
        "enriched_claims": enriched_claims,
        "manuscript_audit": manuscript_audit,
    }


def audit_manuscript_structure(
    sections: list[dict[str, Any]],
    enriched_claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Scan manuscript paragraphs to help the student spot isolated 'boxcar' paragraphs vs. integrated critical analysis."""
    section_audits: list[dict[str, Any]] = []
    total_boxcar_paragraphs = 0
    total_integrated_paragraphs = 0

    analytical_markers = [
        "enquanto",
        "por outro lado",
        "diferentemente",
        "em contrapartida",
        "corroborando",
        "ao passo que",
        "converge",
        "diverge",
        "tensiona",
        "complementa",
        "embora",
        "contudo",
        "entretanto",
        "nessa direção",
        "comparando",
    ]

    for sec in sections:
        content = sec.get("content") if isinstance(sec.get("content"), dict) else {}
        plain = extract_plain_text(content).strip()
        raw_paragraphs = [
            p.strip() for p in re.split(r"\n\s*\n+|\n+", plain) if p and len(p.strip()) > 20
        ]

        para_diagnostics: list[dict[str, Any]] = []
        sec_boxcars = 0
        sec_integrated = 0

        for idx, para in enumerate(raw_paragraphs):
            p_lower = para.lower()
            citations_found = re.findall(r"\([^)]*\d{4}[^)]*\)", para)
            citation_count = len(citations_found)
            has_analytical_connector = any(m in p_lower for m in analytical_markers)

            if citation_count >= 2 or (citation_count == 1 and has_analytical_connector):
                status_code = "analise_integrada"
                status_label = "Síntese Analítica Integrada"
                feedback = (
                    "Ótimo: este parágrafo articula evidência bibliográfica com conectivo analítico ou diálogo entre fontes."
                )
                sec_integrated += 1
                total_integrated_paragraphs += 1
            elif citation_count == 1:
                status_code = "vagao_de_trem"
                status_label = "Alerta Vagão de Trem (1 autor isolado)"
                feedback = (
                    "Você citou apenas 1 fonte isolada neste parágrafo sem contrastá-la com outro autor nem explicitar sua análise crítica. "
                    "Experimente usar a Mesa de Comparação abaixo para cruzar este trecho com outra evidência."
                )
                sec_boxcars += 1
                total_boxcar_paragraphs += 1
            else:
                status_code = "sem_ancoragem"
                status_label = "Afirmação sem Fonte / Transição Autoral"
                feedback = (
                    "Parágrafo sem citação explícita (Autor, Ano, p. X). Se contiver afirmação teórica ou empírica, ancore em um trecho verificado."
                )

            para_diagnostics.append(
                {
                    "index": idx + 1,
                    "excerpt": para[:220] + ("…" if len(para) > 220 else ""),
                    "citation_count": citation_count,
                    "status_code": status_code,
                    "status_label": status_label,
                    "feedback": feedback,
                }
            )

        section_audits.append(
            {
                "section_id": sec["id"],
                "section_title": sec["title"],
                "paragraph_count": len(raw_paragraphs),
                "boxcar_count": sec_boxcars,
                "integrated_count": sec_integrated,
                "paragraphs": para_diagnostics,
            }
        )

    return {
        "total_boxcar_paragraphs": total_boxcar_paragraphs,
        "total_integrated_paragraphs": total_integrated_paragraphs,
        "sections": section_audits,
    }


def compare_and_connect_passages(
    claim_a: dict[str, Any],
    claim_b: dict[str, Any],
    doc_a: dict[str, Any],
    doc_b: dict[str, Any],
    relation_type: str,
    student_analysis: str | None,
    section_title: str,
    intensity: int = 35,
    client: LLMClient | None = None,
) -> dict[str, Any]:
    """Compare two verified passages side by side, help the student analyze their relationship, and generate either a Socratic scaffold or a connected paragraph."""
    ref_a = format_author_ref(doc_a, claim_a.get("page_no", 1))
    ref_b = format_author_ref(doc_b, claim_b.get("page_no", 1))
    role_a = classify_passage_role(claim_a.get("statement", ""), claim_a.get("quote", ""))
    role_b = classify_passage_role(claim_b.get("statement", ""), claim_b.get("quote", ""))

    concept_a = claim_a.get("concept") or "o primeiro conceito"
    concept_b = claim_b.get("concept") or "o segundo conceito"
    quote_a = claim_a.get("quote", "").strip().rstrip(".")
    quote_b = claim_b.get("quote", "").strip().rstrip(".")

    # Shared lexical tokens (>= 5 chars) to highlight concrete semantic overlap
    words_a = set(re.findall(r"[a-zà-úç]{5,}", f"{concept_a} {quote_a}".lower()))
    words_b = set(re.findall(r"[a-zà-úç]{5,}", f"{concept_b} {quote_b}".lower()))
    shared_terms = sorted(list(words_a & words_b))[:6]

    relation_labels = {
        "corroboracao": "Corroboração / Reforço Empírico (A + B)",
        "contraponto": "Contraponto / Tensão Crítica (A vs. B)",
        "complementaridade": "Complementaridade Teoria → Prática (A → B)",
        "lacuna": "Ponte Inédita / Lacuna do Seu Trabalho (A + B = ? )",
    }
    rel_label = relation_labels.get(relation_type, relation_labels["complementaridade"])

    # Build step-by-step analytical comparison for the student
    convergence_point = (
        f"Ambos os trechos dialogam no eixo de {', '.join(shared_terms[:3]) if shared_terms else f'{concept_a.lower()} e {concept_b.lower()}'}, "
        f"permitindo fundamentar a seção “{section_title}” com mais de uma fonte primária."
    )
    difference_point = (
        f"Enquanto {ref_a} atua como {role_a['role_label'].lower()} (foco em {concept_a.lower()}), "
        f"{ref_b} traz {role_b['role_label'].lower()} (foco em {concept_b.lower()})."
    )
    guiding_question = (
        f"Para conectar os dois sem fazer 'fichamento solto': por que a evidência de {ref_b} "
        f"{'confirma na prática' if relation_type == 'corroboracao' else 'impõe um limite importante a' if relation_type == 'contraponto' else 'amplia o alcance de'} "
        f"o que foi proposto por {ref_a}?"
    )

    student_note_clean = (student_analysis or "").strip()

    # Socratic scaffold: both verified quotes + the student's own note, or an explicit [lacuna].
    if relation_type == "contraponto":
        scaffold = (
            f"Embora a literatura aponte que “{quote_a}” {ref_a}, é preciso ponderar esse achado à luz de "
            f"{concept_b.lower()}, uma vez que “{quote_b}” {ref_b}. "
            + (
                f"Nessa tensão, {student_note_clean.rstrip('.')}."
                if student_note_clean
                else "[Complete aqui com sua análise: qual dos dois recortes mais se aproxima do seu objeto de pesquisa?]"
            )
        )
    elif relation_type == "corroboracao":
        scaffold = (
            f"A premissa de que “{quote_a}” {ref_a} encontra respaldo em {concept_b.lower()}, "
            f"visto que “{quote_b}” {ref_b}. "
            + (
                f"Assim, {student_note_clean.rstrip('.')}."
                if student_note_clean
                else "[Complete aqui explicando como essa convergência sustenta o objetivo do seu capítulo.]"
            )
        )
    else:
        scaffold = (
            f"Para articular {concept_a.lower()} e {concept_b.lower()} em {section_title}, "
            f"parte-se de que “{quote_a}” {ref_a} para compreender por que “{quote_b}” {ref_b}. "
            + (
                f"Na leitura deste trabalho, {student_note_clean.rstrip('.')}."
                if student_note_clean
                else "[Complete aqui com sua conclusão analítica conectando os dois autores ao seu problema.]"
            )
        )

    synthesis_text = scaffold
    mode_used = "scaffold_socratico"
    llm_used = False
    notice: str | None = None

    if intensity > 55:
        # Full dialectical synthesis requires the LLM. Without it, say so and keep the scaffold.
        try:
            res = call_json(
                client,
                (
                    "Você é o orientador de síntese dialética. Construa UM parágrafo comparativo acadêmico "
                    "que use obrigatoriamente as duas citações literais fornecidas, entre aspas e com a "
                    "referência exatamente como dada, e a análise do aluno. Não acrescente fontes. "
                    "Escreva em português brasileiro acadêmico, com frases de tamanho variado e sem "
                    "fórmulas de transição genéricas."
                ),
                (
                    f"Seção: {section_title}\n"
                    f"Relação: {rel_label}\n"
                    f"Trecho A: “{quote_a}” {ref_a}\n"
                    f"Trecho B: “{quote_b}” {ref_b}\n"
                    f"Análise crítica do aluno: {student_note_clean or '(não informada)'}\n\n"
                    'Responda em JSON: {"synthesis": "..."}'
                ),
                text_schema("synthesis"),
                operation="compare_synthesis",
            )
            synthesis_text = str(res["synthesis"]).strip()
            mode_used = "sintese_assistida"
            llm_used = True
        except LLMUnavailable:
            notice = (
                "A síntese completa precisa de IA, que está indisponível agora. "
                "Entregamos o esqueleto com as duas citações para você completar."
            )

    return {
        "llm_used": llm_used,
        "notice": notice,
        "relation_type": relation_type,
        "relation_label": rel_label,
        "intensity": intensity,
        "mode_used": mode_used,
        "passage_a": {
            "id": claim_a["id"],
            "citation_ref": ref_a,
            "concept": concept_a,
            "quote": quote_a,
            "role_label": role_a["role_label"],
            "reading_tip": role_a["reading_tip"],
        },
        "passage_b": {
            "id": claim_b["id"],
            "citation_ref": ref_b,
            "concept": concept_b,
            "quote": quote_b,
            "role_label": role_b["role_label"],
            "reading_tip": role_b["reading_tip"],
        },
        "comparison_matrix": {
            "shared_terms": shared_terms,
            "convergence": convergence_point,
            "difference": difference_point,
            "guiding_question": guiding_question,
        },
        "synthesis_text": synthesis_text,
    }


def extract_verified_passages_deterministic(
    pages: list[str],
    doc_title: str,
) -> list[dict[str, Any]]:
    """Deterministic fallback extractor when no external LLM API key is configured.
    Every extracted sentence is strictly verified against `pages` via `verify_quote` (Rule 1)."""
    candidates: list[dict[str, Any]] = []
    seen_quotes: set[str] = set()

    for page_idx, page_text in enumerate(pages):
        raw_sentences = re.split(r"(?<=[.!?])\s+", page_text.strip())
        for sent in raw_sentences:
            clean = re.sub(r"\s+", " ", sent).strip()
            if len(clean) < 40 or len(clean) > 260:
                continue
            if clean.lower() in seen_quotes:
                continue
            r = verify_quote(clean, pages)
            if not r.found:
                continue

            # Derive a concise concept label from significant words in the sentence or title
            words = [
                w
                for w in re.findall(r"[A-Za-zÀ-ÿçÇ]{5,}", clean)
                if w.lower()
                not in {
                    "sobre",
                    "entre",
                    "quando",
                    "como",
                    "para",
                    "pelos",
                    "pelas",
                    "deste",
                    "desta",
                    "nesse",
                    "nessa",
                    "segundo",
                    "estudo",
                    "artigo",
                    "texto",
                    "resultados",
                    "entretanto",
                    "todavia",
                    "contudo",
                }
            ]
            concept_label = (
                " ".join(words[:2]).capitalize()
                if len(words) >= 2
                else (doc_title.split(" ")[0].capitalize() or "Conceito central")
            )
            seen_quotes.add(clean.lower())
            candidates.append(
                {
                    "concept": concept_label,
                    "statement": clean,
                    "quote": clean,
                    "page_verified": r.page or (page_idx + 1),
                    "char_start": r.start,
                    "char_end": r.end,
                    "verify_method": r.method,
                    "quote_verified": True,
                    "certainty": "sugere",
                    "scope": {},
                }
            )
            if len(candidates) >= 15:
                return candidates

    return candidates

