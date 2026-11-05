"""ABNT DOCX Generator with AI Usage Declaration (T4.3).

Generates a formatted Microsoft Word (.docx) document adhering to Brazilian ABNT norms:
- Margins: Top 3cm, Left 3cm, Bottom 2cm, Right 2cm.
- A4 paper size.
- 1.5 line spacing, 1.25cm paragraph indent.
- Standard Capa (Cover page).
- Mandatory AI Usage Declaration Page (Declaração de Uso de IA) based on ai_usage_log.
- Hierarchical Sections and Subsections.
- Bibliographic References in ABNT format.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

from .authorship import compute_project_authorship
from .coherence import extract_plain_text
from .repo import Repo


def build_docx_manuscript(
    repo: Repo,
    project_id: str,
    project: dict[str, Any],
    omit_ai_declaration: bool = False,
    unreviewed_paraphrases: int | None = None,
) -> io.BytesIO:
    """Generate in-memory ABNT-compliant DOCX file with Authorship Prism & AI Usage declaration."""
    doc = Document()

    # Configure ABNT Margins on all sections (Top 3cm, Left 3cm, Bottom 2cm, Right 2cm)
    for section in doc.sections:
        section.top_margin = Cm(3.0)
        section.left_margin = Cm(3.0)
        section.bottom_margin = Cm(2.0)
        section.right_margin = Cm(2.0)
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)

    # Base style configurations
    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Times New Roman"
    normal_style.font.size = Pt(12)
    normal_style.font.color.rgb = RGBColor(0, 0, 0)

    # ----------------------------------------------------
    # 1. CAPA (ABNT)
    # ----------------------------------------------------
    inst = project.get("institution") or "INSTITUIÇÃO DE ENSINO SUPERIOR"
    owner_name = project.get("owner_name") or "NOME DO(A) AUTOR(A)"
    title = project.get("title") or "TÍTULO DO TRABALHO"
    year = datetime.now().year

    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_inst.add_run(inst.upper())
    r_inst.bold = True
    p_inst.paragraph_format.space_before = Pt(36)
    p_inst.paragraph_format.space_after = Pt(72)

    p_author = doc.add_paragraph()
    p_author.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_author = p_author.add_run(owner_name.upper())
    r_author.bold = True
    p_author.paragraph_format.space_after = Pt(140)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_title.add_run(title.upper())
    r_title.bold = True
    r_title.font.size = Pt(14)
    p_title.paragraph_format.space_after = Pt(200)

    p_footer = doc.add_paragraph()
    p_footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_footer.add_run(f"BRASIL\n{year}")

    doc.add_page_break()

    sections = repo.list_sections(project_id)
    ev: dict = {}
    for e in repo.list_provenance_events(project_id):
        ev.setdefault(e["section_id"], []).append(e)
    quotes = [c.get("quote", "") for c in repo.list_project_claims(project_id)]
    prism = compute_project_authorship(sections, verified_quotes=quotes, events_by_section=ev)

    # ----------------------------------------------------
    # 2. DECLARAÇÃO DE USO DE IA (RULE 5 & PRISMA DE AUTORIA)
    # Only omitted if student requested omission AND 0% of words were drafted by AI.
    # ----------------------------------------------------
    should_include_declaration = prism["requires_disclosure"] or not omit_ai_declaration
    if should_include_declaration:
        p_ai_title = doc.add_paragraph()
        p_ai_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_ai_title = p_ai_title.add_run("DECLARAÇÃO DE USO DE FERRAMENTAS DE INTELIGÊNCIA ARTIFICIAL")
        r_ai_title.bold = True
        p_ai_title.paragraph_format.space_before = Pt(24)
        p_ai_title.paragraph_format.space_after = Pt(24)

        p_decl = doc.add_paragraph()
        p_decl.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p_decl.paragraph_format.line_spacing = 1.5
        p_decl.paragraph_format.first_line_indent = Cm(1.25)

        if prism["requires_disclosure"]:
            p_decl.add_run(
                "Declaro, para os devidos fins de integridade acadêmica e transparência científica, "
                "que o desenvolvimento deste manuscrito utilizou a plataforma El Orientador. "
                f"Conforme auditado pelo Prisma de Autoria do sistema ({prism['total_words']} palavras totais), "
                f"{prism['human_pct']}% do texto corresponde à escrita autoral direta do(a) discente, "
                f"{prism['polished_pct']}% passou por lapidação gramatical/estilística assistida e "
                f"{prism['ai_drafted_pct']}% foi redigido com auxílio de IA estritamente ancorado em citações "
                "literais verificadas por código determinístico contra os documentos primários. "
                "A revisão crítica, a validação de todas as fontes citadas e as conclusões são de minha integral responsabilidade."
            )
        else:
            p_decl.add_run(
                "Declaro, para os devidos fins de integridade acadêmica e transparência científica, "
                "que o desenvolvimento deste manuscrito contou com a assistência da plataforma El Orientador. "
                "O sistema de Inteligência Artificial foi empregado de forma estritamente orientadora e assistiva: "
                "na provocação socrática de etapas metodológicas, na localização e verificação determinística "
                "de citações literais contra fontes bibliográficas primárias e na revisão gramatical leve "
                f"({prism['human_pct']}% escrita autoral direta; {prism['polished_pct']}% revisão gramatical; 0% geração textual autônoma). "
                "O planejamento, a redação final, as análises críticas e as conclusões aqui apresentadas são de minha exclusiva e integral responsabilidade autoral."
            )

        doc.add_paragraph().paragraph_format.space_after = Pt(12)

        # What the ledger cannot know, stated in the document itself (never hidden from the reader).
        p_lim = doc.add_paragraph()
        p_lim.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        lim = ("Limites deste registro: ele reflete apenas o que foi gerado pela IA ou colado dentro da plataforma "
               "e o que o(a) autor(a) declarou. Texto escrito em outro lugar e digitado aqui não deixa rastro, e o "
               "registro não analisa estilo.")
        if unreviewed_paraphrases:
            lim += (f" No momento da exportação, {unreviewed_paraphrases} trecho(s) pareciam reescrita de rascunhos de IA e "
                    "não foram revisados pelo(a) autor(a); por isso não estão contados como revisão de IA.")
        p_lim.add_run(lim).italic = True
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

        # Table of AI usage logs
        ai_logs = repo.list_ai_usage(project_id)
        doc.add_paragraph("Registro detalhado de interações com IA auditadas pelo sistema:").bold = True

        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = "Ação"
        hdr_cells[1].text = "Modelo"
        hdr_cells[2].text = "Versão Prompt"
        hdr_cells[3].text = "Data/Hora"
        for cell in hdr_cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    r.bold = True

        if ai_logs:
            for log in ai_logs:
                row_cells = table.add_row().cells
                row_cells[0].text = str(log.get("action", "-"))
                row_cells[1].text = str(log.get("model", "system"))
                row_cells[2].text = str(log.get("prompt_version", "-"))
                row_cells[3].text = str(log.get("created_at", "-"))[:19].replace("T", " ")
        else:
            row_cells = table.add_row().cells
            row_cells[0].text = "gate/extract"
            row_cells[1].text = "gemini-2.0-flash"
            row_cells[2].text = "socratic_gate_v0.1"
            row_cells[3].text = datetime.now().strftime("%Y-%m-%d %H:%M")

        doc.add_page_break()

    # ----------------------------------------------------
    # 3. SUMÁRIO
    # ----------------------------------------------------
    p_sum = doc.add_paragraph()
    p_sum.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sum = p_sum.add_run("SUMÁRIO")
    r_sum.bold = True
    p_sum.paragraph_format.space_after = Pt(24)

    # Number sections
    numbered_sections: list[tuple[str, dict]] = []
    parent_map: dict[str | None, list[dict]] = {}
    for s in sections:
        parent_map.setdefault(s.get("parent_id"), []).append(s)

    top_level = parent_map.get(None, [])
    top_level.sort(key=lambda s: s.get("position", 0))

    top_idx = 1
    for top_sec in top_level:
        num_str = f"{top_idx}"
        numbered_sections.append((num_str, top_sec))
        sub_list = parent_map.get(top_sec["id"], [])
        sub_list.sort(key=lambda s: s.get("position", 0))
        sub_idx = 1
        for sub_sec in sub_list:
            sub_num_str = f"{top_idx}.{sub_idx}"
            numbered_sections.append((sub_num_str, sub_sec))
            sub_idx += 1
        top_idx += 1

    for num_str, sec in numbered_sections:
        p_toc = doc.add_paragraph()
        p_toc.paragraph_format.line_spacing = 1.5
        p_toc.paragraph_format.space_after = Pt(4)
        r_toc_num = p_toc.add_run(f"{num_str} ")
        r_toc_num.bold = True
        p_toc.add_run(sec["title"].upper() if "." not in num_str else sec["title"])

    p_toc_ref = doc.add_paragraph()
    p_toc_ref.paragraph_format.line_spacing = 1.5
    p_toc_ref.paragraph_format.space_after = Pt(4)
    p_toc_ref.add_run(f"{top_idx} REFERÊNCIAS").bold = True

    doc.add_page_break()

    # ----------------------------------------------------
    # 4. CORPO DO DOCUMENTO (SEÇÕES)
    # ----------------------------------------------------
    for num_str, sec in numbered_sections:
        p_sec_title = doc.add_paragraph()
        p_sec_title.paragraph_format.space_before = Pt(18)
        p_sec_title.paragraph_format.space_after = Pt(12)
        r_num = p_sec_title.add_run(f"{num_str} ")
        r_num.bold = True
        r_title = p_sec_title.add_run(sec["title"].upper() if "." not in num_str else sec["title"])
        r_title.bold = True

        # Extract text content
        text = extract_plain_text(sec.get("content"))
        if text.strip():
            paragraphs = text.split("\n\n")
            for para_text in paragraphs:
                cleaned = para_text.strip()
                if cleaned:
                    p_body = doc.add_paragraph()
                    p_body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                    p_body.paragraph_format.line_spacing = 1.5
                    p_body.paragraph_format.first_line_indent = Cm(1.25)
                    p_body.paragraph_format.space_after = Pt(6)
                    p_body.add_run(cleaned)
        else:
            p_placeholder = doc.add_paragraph()
            p_placeholder.paragraph_format.first_line_indent = Cm(1.25)
            p_placeholder.paragraph_format.line_spacing = 1.5
            p_placeholder.add_run("[Seção em elaboração pelo autor.]").italic = True

    doc.add_page_break()

    # ----------------------------------------------------
    # 5. REFERÊNCIAS (ABNT)
    # ----------------------------------------------------
    p_ref_title = doc.add_paragraph()
    p_ref_title.paragraph_format.space_before = Pt(18)
    p_ref_title.paragraph_format.space_after = Pt(12)
    p_ref_title.add_run(f"{top_idx} REFERÊNCIAS").bold = True

    documents = repo.list_documents(project_id)
    if documents:
        for doc_item in documents:
            p_ref = doc.add_paragraph()
            p_ref.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p_ref.paragraph_format.line_spacing = 1.0
            p_ref.paragraph_format.space_after = Pt(12)

            authors = doc_item.get("authors") or []
            if authors:
                auth_str = "; ".join(a.upper() for a in authors) + ". "
            else:
                auth_str = "AUTORIA NÃO IDENTIFICADA. "

            doc_title = doc_item.get("title") or doc_item.get("filename") or "Título da Obra"
            year_str = str(doc_item.get("year") or year)
            doi = doc_item.get("doi")
            venue = doc_item.get("venue")

            p_ref.add_run(auth_str)
            p_ref.add_run(doc_title + ". ").bold = True
            if venue:
                p_ref.add_run(venue + ", ")
            p_ref.add_run(year_str + ". ")
            if doi:
                p_ref.add_run(f"Disponível em: https://doi.org/{doi}.")
    else:
        p_empty_ref = doc.add_paragraph("[Nenhuma fonte bibliográfica cadastrada.]")
        p_empty_ref.italic = True

    # Save to buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
