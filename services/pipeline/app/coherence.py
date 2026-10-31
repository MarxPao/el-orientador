"""Deterministic Coherence Checks (T4.2).

Performs strict, deterministic verification of the manuscript structure without LLM:
1. 'secao_sem_fonte': Section has substantive text (> 40 words) but 0 linked concepts.
2. 'referencia_orfa': Concept or confirmed document in the project never linked to any section.
3. 'objetivo_sem_capitulo': Research problem defined in project settings but no section addresses objectives.
4. 'conceito_nao_mencionado': Section links to a concept but the text does not cite or mention it.
"""
from __future__ import annotations

import re
from typing import Any

from .repo import Repo


def extract_plain_text(content: Any) -> str:
    """Extract plain text from Tiptap JSON or string content."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        text_parts: list[str] = []

        def recurse(node: dict):
            if node.get("type") == "text" and "text" in node:
                text_parts.append(str(node["text"]))
            for child in node.get("content", []):
                if isinstance(child, dict):
                    recurse(child)

        recurse(content)
        return " ".join(text_parts)
    return ""


def check_coherence(repo: Repo, project_id: str, project: dict) -> list[dict[str, Any]]:
    """Run all deterministic coherence checks for a project."""
    warnings: list[dict[str, Any]] = []

    sections = repo.list_sections(project_id)
    concepts = repo.list_concepts(project_id)
    claims = repo.list_project_claims(project_id)
    documents = repo.list_documents(project_id)

    # Map concept id to concept label
    concept_map = {c["id"]: c["label"] for c in concepts}

    # Set of all concept IDs linked across all sections
    all_linked_concept_ids: set[str] = set()

    for sec in sections:
        sec_text = extract_plain_text(sec.get("content"))
        words = [w for w in re.split(r"\s+", sec_text) if w]
        word_count = len(words)
        concept_ids = sec.get("concept_ids", [])
        all_linked_concept_ids.update(concept_ids)

        # Check 1: Seção sem fonte (substantive text with no evidence linked)
        # Skip references or pre-textual sections like 'Referências' or 'Agradecimentos'
        sec_title_lower = sec["title"].lower()
        is_exempt = any(ex in sec_title_lower for ex in ["referência", "referencias", "anexo", "apêndice"])

        if word_count >= 30 and not concept_ids and not is_exempt:
            warnings.append({
                "type": "secao_sem_fonte",
                "severity": "warning",
                "section_id": sec["id"],
                "section_title": sec["title"],
                "message": (
                    f"A seção '{sec['title']}' contém {word_count} palavras mas nenhuma fonte ou conceito "
                    "do mapa de conhecimento associado. Vincule conceitos evidenciados."
                ),
            })

        # Check 4: Conceito vinculado não mencionado no texto
        for cid in concept_ids:
            label = concept_map.get(cid)
            if label and len(sec_text) > 100:
                # Check if concept name (or part of it) appears in text
                pattern = re.compile(re.escape(label), re.IGNORECASE)
                if not pattern.search(sec_text):
                    warnings.append({
                        "type": "conceito_nao_mencionado",
                        "severity": "info",
                        "section_id": sec["id"],
                        "section_title": sec["title"],
                        "concept_id": cid,
                        "concept_label": label,
                        "message": (
                            f"O conceito '{label}' está vinculado à seção '{sec['title']}', "
                            "mas seu termo não foi identificado no corpo do texto."
                        ),
                    })

    # Check 2: Referência órfã (concepts with claims in project that are never used in any section)
    for c in concepts:
        if c["n_claims"] > 0 and c["id"] not in all_linked_concept_ids:
            warnings.append({
                "type": "referencia_orfa",
                "severity": "info",
                "concept_id": c["id"],
                "concept_label": c["label"],
                "message": (
                    f"O conceito '{c['label']}' possui {c['n_claims']} afirmação(ões) verificada(s) no mapa, "
                    "mas ainda não foi incorporado a nenhuma seção do documento."
                ),
            })

    # Documents never cited or linked
    doc_ids_with_claims = {c["document_id"] for c in claims}
    for doc in documents:
        if doc["id"] not in doc_ids_with_claims:
            warnings.append({
                "type": "documento_sem_alegacoes",
                "severity": "info",
                "document_id": doc["id"],
                "document_title": doc.get("title") or doc.get("filename"),
                "message": (
                    f"O documento '{doc.get('title') or doc.get('filename')}' foi cadastrado, "
                    "mas ainda não possui afirmações extraídas e verificadas."
                ),
            })

    # Check 3: Objetivo sem capítulo
    research_problem = project.get("research_problem")
    if research_problem and len(research_problem.strip()) > 10:
        has_intro_or_obj = any(
            any(k in s["title"].lower() for k in ["objetivo", "introdução", "introducao", "problema"])
            for s in sections
        )
        if not has_intro_or_obj and len(sections) > 0:
            warnings.append({
                "type": "objetivo_sem_capitulo",
                "severity": "warning",
                "message": (
                    "O projeto possui um problema de pesquisa definido, mas nenhuma seção de "
                    "'Introdução' ou 'Objetivos' foi criada na estrutura de capítulos."
                ),
            })

    return warnings
