"""ABNT LaTeX Generator and Overleaf Package Builder (T7.3).

Generates a complete, modular, ready-to-compile .zip package conforming to
Brazilian ABNT standards using the `abntex2` document class:
- Margins: 3cm top, 3cm left, 2cm bottom, 2cm right (A4 paper).
- Modular architecture with chapters in `capitulos/` and pre-textual elements.
- Standard Capa, Folha de Rosto, and Folha de Aprovação.
- Mandatory AI Usage Declaration based on Authorship Prism (AGENTS.md rule 5).
- Clean TipTap to LaTeX AST converter with safe character escaping.
- Full `referencias.bib` bibliography with auto-generated cite keys.
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from datetime import datetime
from typing import Any

from .authorship import compute_project_authorship
from .bibliography import format_bibtex
from .repo import Repo

LATEX_SPECIAL_CHARS = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(text: str) -> str:
    """Safely escape LaTeX reserved characters in plain text."""
    if not text:
        return ""

    def _replace(m: re.Match[str]) -> str:
        ch = m.group(0)
        if ch == "\\":
            return r"\textbackslash{}"
        if ch == "~":
            return r"\textasciitilde{}"
        if ch == "^":
            return r"\textasciicircum{}"
        return "\\" + ch

    # Single-pass substitution avoids double-escaping braces in \textbackslash{}
    res = re.sub(r"[\\&%$#_{}~^]", _replace, text)
    # Replace smart quotes with standard LaTeX quotes
    res = res.replace("“", "``").replace("”", "''").replace("\"", "''")
    res = res.replace("‘", "`").replace("’", "'")
    return res


def slugify_cite_key(doc: dict[str, Any], fallback_index: int) -> str:
    """Generate a clean citation key like 'silva2020' or 'moran2015metodologias'."""
    authors = doc.get("authors") or []
    lead_author = "anon"
    if authors and isinstance(authors[0], str):
        parts = authors[0].strip().split()
        lead_author = parts[-1] if parts else "anon"

    year = str(doc.get("year") or "nd")
    clean_author = unicodedata.normalize("NFKD", lead_author).encode("ascii", "ignore").decode("ascii").lower()
    clean_author = re.sub(r"[^a-z0-9]", "", clean_author) or f"ref{fallback_index}"
    return f"{clean_author}{year}"


def tiptap_to_latex(content: Any, base_heading_level: int = 1) -> str:
    """Convert TipTap JSON document to clean LaTeX syntax."""
    if not content:
        return ""
    if isinstance(content, str):
        return escape_latex(content)
    if not isinstance(content, dict):
        return ""

    node_type = content.get("type", "")

    # Handle text leaf node with inline marks
    if node_type == "text":
        txt = escape_latex(content.get("text", ""))
        marks = content.get("marks") or []
        for mark in marks:
            mtype = mark.get("type")
            if mtype == "bold":
                txt = f"\\textbf{{{txt}}}"
            elif mtype == "italic":
                txt = f"\\textit{{{txt}}}"
            elif mtype == "code":
                txt = f"\\texttt{{{txt}}}"
            elif mtype == "strike":
                txt = f"\\sout{{{txt}}}"
        return txt

    # Recursive children handler
    children = content.get("content") or []
    inner_latex = "".join(tiptap_to_latex(child, base_heading_level) for child in children)

    if node_type == "paragraph":
        return f"{inner_latex}\n\n" if inner_latex.strip() else "\n"

    if node_type == "heading":
        level = content.get("attrs", {}).get("level", 1) + base_heading_level - 1
        heading_cmds = {
            1: "section",
            2: "subsection",
            3: "subsubsection",
            4: "paragraph",
            5: "subparagraph",
        }
        cmd = heading_cmds.get(level, "paragraph")
        return f"\n\\{cmd}{{{inner_latex.strip()}}}\n\n"

    if node_type == "bulletList":
        items = "\n".join(
            f"  \\item {tiptap_to_latex(item, base_heading_level).strip()}"
            for item in children
            if item.get("type") == "listItem"
        )
        return f"\\begin{{itemize}}\n{items}\n\\end{{itemize}}\n\n"

    if node_type == "orderedList":
        items = "\n".join(
            f"  \\item {tiptap_to_latex(item, base_heading_level).strip()}"
            for item in children
            if item.get("type") == "listItem"
        )
        return f"\\begin{{enumerate}}\n{items}\n\\end{{enumerate}}\n\n"

    if node_type == "listItem":
        return inner_latex.strip()

    if node_type == "blockquote":
        # ABNT long direct citation (> 3 lines, 4cm indent, single space, smaller font)
        return f"\\begin{{citacao}}\n{inner_latex.strip()}\n\\end{{citacao}}\n\n"

    if node_type == "doc":
        return inner_latex

    return inner_latex


def build_latex_package(
    repo: Repo,
    project_id: str,
    include_approval: bool = True,
    include_ai_declaration: bool = True,
) -> io.BytesIO:
    """Build a complete, standalone .zip file ready for Overleaf compilation."""
    project = repo.get_project_by_id(project_id) or {}
    sections = repo.list_sections(project_id) if hasattr(repo, "list_sections") else []
    documents = repo.list_documents(project_id) if hasattr(repo, "list_documents") else []
    claims = repo.list_project_claims(project_id) if hasattr(repo, "list_project_claims") else []

    # Compile authorship prism for AI usage transparency (AGENTS.md rule 5)
    ev_by_section: dict[str, list[dict]] = {}
    if hasattr(repo, "list_provenance_events"):
        for e in repo.list_provenance_events(project_id):
            ev_by_section.setdefault(e["section_id"], []).append(e)
    quotes = [c.get("quote", "") for c in claims]
    prism = compute_project_authorship(sections, verified_quotes=quotes, events_by_section=ev_by_section)

    title = project.get("title") or "Trabalho Acadêmico"
    owner_name = project.get("owner_name") or "Nome do Estudante"
    inst = project.get("institution") or "Instituição de Ensino Superior"
    work_type = project.get("work") or "tcc"
    work_label = {
        "tcc": "Trabalho de Conclusão de Curso (Graduação)",
        "pre_projeto_mestrado": "Pré-projeto de Mestrado",
        "pre_projeto_doutorado": "Pré-projeto de Doutorado",
        "dissertacao": "Dissertação de Mestrado",
        "tese": "Tese de Doutorado",
        "artigo": "Artigo Científico",
    }.get(work_type, "Trabalho Acadêmico")

    current_year = datetime.now().year

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # -------------------------------------------------------------
        # 1. referencias.bib
        # -------------------------------------------------------------
        bib_entries = []
        for idx, doc in enumerate(documents, start=1):
            key = slugify_cite_key(doc, idx)
            bib_entries.append(format_bibtex(doc, key))
        bib_content = "\n\n".join(bib_entries) if bib_entries else "% Nenhuma referencia cadastrada no projeto\n"
        zf.writestr("referencias.bib", bib_content)

        # -------------------------------------------------------------
        # 2. elementos_pre_textuais/folha_aprovacao.tex
        # -------------------------------------------------------------
        folha_aprovacao = f"""% Folha de Aprovacao (ABNT NBR 14724)
\\begin{{folhadeaprovacao}}
  \\begin{{center}}
    {{\\ABNTEXchapterfont\\large {escape_latex(owner_name).upper()}}}

    \\vspace*{{2cm}}
    {{\\ABNTEXchapterfont\\bfseries\\large {escape_latex(title).upper()}}}
    \\vspace*{{2cm}}
  \\end{{center}}

  \\noindent
  {escape_latex(work_label)} submetido(a) como requisito parcial para obtenção do título, avaliado(a) e aprovado(a) pela banca examinadora em: \\underline{{\\hspace{{4cm}}}}.

  \\vspace*{{1.5cm}}
  \\begin{{center}}
    {{\\bfseries BANCA EXAMINADORA}}
  \\end{{center}}

  \\assinatura{{\\textbf{{Prof(a). Dr(a). Orientador(a)}} \\\\ Presidente da Banca / Orientador(a)}}
  \\assinatura{{\\textbf{{Prof(a). Dr(a). Examinador(a) 1}} \\\\ Membro da Banca Examinadora}}
  \\assinatura{{\\textbf{{Prof(a). Dr(a). Examinador(a) 2}} \\\\ Membro da Banca Examinadora}}

\\end{{folhadeaprovacao}}
"""
        if include_approval:
            zf.writestr("elementos_pre_textuais/folha_aprovacao.tex", folha_aprovacao)

        # -------------------------------------------------------------
        # 3. elementos_pre_textuais/declaracao_ia.tex (AGENTS.md rule 5)
        # -------------------------------------------------------------
        ai_pct = prism.get("pct_ai", 0.0)
        verified_pct = prism.get("pct_verified_evidence", 0.0)
        direct_pct = prism.get("pct_direct_student", 0.0)

        declaracao_ia = f"""% Declaracao de Uso de Ferramentas de Inteligencia Artificial (Regra 5 - El Orientador)
\\begin{{pretextualsection}}{{Declaração de Uso de Ferramentas de Inteligência Artificial}}

Esta declaração certifica, em conformidade com as diretrizes de integridade acadêmica e transparência científica, o nível e a modalidade de assistência de ferramentas de Inteligência Artificial na elaboração deste manuscrito.

\\vspace{{0.5cm}}
\\noindent
\\textbf{{Extrato do Prisma de Autoria:}}
\\begin{{itemize}}
  \\item \\textbf{{Escrita Direta do(a) Autor(a):}} {direct_pct}\\% das palavras redigidas integralmente pelo estudante.
  \\item \\textbf{{Trechos com Evidência Literal Verificada:}} {verified_pct}\\% correspondentes a citações com conferência determinística no texto-fonte.
  \\item \\textbf{{Assistência Textual por IA:}} {ai_pct}\\% das palavras geradas com suporte de IA em níveis supervisionados (rascunho de evidência, coautoria ou polimento acadêmico).
\\end{{itemize}}

\\vspace{{0.5cm}}
\\noindent
\\textbf{{Termo de Responsabilidade Autoral:}}
\\begin{{citacao}}
O(A) autor(a) declara que todas as ideias, argumentos, conclusões e análises apresentadas neste trabalho foram concebidas e revisadas criticamente pelo(a) próprio(a), assumindo responsabilidade integral pelo conteúdo, rigor científico e veracidade das afirmações expostas. Nenhuma referência bibliográfica ou evidência foi inventada.
\\end{{citacao}}

\\vspace{{1cm}}
\\begin{{center}}
  \\rule{{10cm}}{{0.4pt}}\\\\
  {escape_latex(owner_name)}\\\\
  Autor(a) e Pesquisador(a) Responsável
\\end{{center}}

\\end{{pretextualsection}}
"""
        if include_ai_declaration:
            zf.writestr("elementos_pre_textuais/declaracao_ia.tex", declaracao_ia)

        # -------------------------------------------------------------
        # 4. capitulos/*.tex
        # -------------------------------------------------------------
        input_chapters = []
        for idx, sec in enumerate(sections, start=1):
            sec_title = sec.get("title") or f"Seção {idx}"
            clean_slug = unicodedata.normalize('NFKD', sec_title).encode('ascii', 'ignore').decode('ascii').lower()
            clean_slug = re.sub(r"[^a-z0-9_]", "_", clean_slug)[:40].strip("_") or f"secao_{idx}"
            sec_filename = f"capitulos/{idx:02d}_{clean_slug}.tex"

            sec_body = tiptap_to_latex(sec.get("content"), base_heading_level=2)
            chapter_text = f"\\chapter{{{escape_latex(sec_title)}}}\n\\label{{cap:{idx:02d}}}\n\n{sec_body}"

            zf.writestr(sec_filename, chapter_text)
            input_chapters.append(f"\\include{{{sec_filename[:-4]}}}")

        if not input_chapters:
            sample_chapter = "\\chapter{Introdução}\n\\label{cap:introducao}\n\nEste trabalho foi estruturado no ambiente \\textbf{El Orientador}.\n"
            zf.writestr("capitulos/01_introducao.tex", sample_chapter)
            input_chapters.append("\\include{capitulos/01_introducao}")

        # -------------------------------------------------------------
        # 5. main.tex
        # -------------------------------------------------------------
        inputs_block = "\n".join(input_chapters)
        approval_block = "\\include{elementos_pre_textuais/folha_aprovacao}" if include_approval else ""
        ai_decl_block = "\\include{elementos_pre_textuais/declaracao_ia}" if include_ai_declaration else ""

        main_tex = f"""\\documentclass[
  12pt,
  openright,
  twoside,
  a4paper,
  english,
  brazil
]{{abntex2}}

% --- Pacotes fundamentais ---
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{lmodern}}
\\usepackage{{indentfirst}}
\\usepackage{{color}}
\\usepackage{{graphicx}}
\\usepackage{{microtype}}
\\usepackage{{ulem}}

% --- Citacoes e Referencias ABNT ---
\\usepackage[brazilian,hyperpageref]{{backref}}
\\usepackage[alf,abnt-emphasize=bf,abnt-etal-list=3]{{abntex2cite}}

% --- Metadados do Trabalho ---
\\titulo{{{escape_latex(title)}}}
\\autor{{{escape_latex(owner_name)}}}
\\local{{Brasil}}
\\data{{{current_year}}}
\\instituicao{{{escape_latex(inst)}}}
\\tipotrabalho{{{escape_latex(work_label)}}}
\\preambulo{{{escape_latex(work_label)} apresentado(a) à {escape_latex(inst)} como parte dos requisitos para conclusão.}}

% --- Configuracao de Links PDF ---
\\usepackage{{hyperref}}
\\hypersetup{{
  colorlinks=true,
  linkcolor=blue,
  citecolor=blue,
  urlcolor=blue,
  pdfauthor={{{escape_latex(owner_name)}}},
  pdftitle={{{escape_latex(title)}}}
}}

% --- Configuracao de Espacamento ABNT ---
\\setlength{{\\parindent}}{{1.25cm}}
\\setlength{{\\parskip}}{{0.2cm}}

\\begin{{document}}
\\selectlanguage{{brazil}}
\\frenchspacing

% ==================== ELEMENTOS PRE-TEXTUAIS ====================
\\imprimircapa
\\imprimirfolhaderosto*

{approval_block}

{ai_decl_block}

% Sumario Automatico
\\pdfbookmark[0]{{\\contentsname}}{{toc}}
\\tableofcontents*
\\cleardoublepage

% ==================== ELEMENTOS TEXTUAIS ====================
\\textual

{inputs_block}

% ==================== ELEMENTOS POS-TEXTUAIS ====================
\\postextual

% Referencias Bibliograficas
\\bibliography{{referencias}}

\\end{{document}}
"""
        zf.writestr("main.tex", main_tex)

        # -------------------------------------------------------------
        # 6. INSTRUCOES_OVERLEAF.md
        # -------------------------------------------------------------
        instructions = f"""# Instruções para Compilação no Overleaf

Este pacote foi gerado automaticamente pelo **El Orientador** no padrão **abnTeX2 / ABNT**.

## Como importar no Overleaf:
1. Acesse [https://www.overleaf.com](https://www.overleaf.com) e entre em sua conta.
2. Clique no botão verde **"New Project"** (Novo Projeto) no canto superior esquerdo.
3. Selecione a opção **"Upload Project"** (Carregar Projeto).
4. Arraste ou selecione este arquivo `.zip` diretamente (sem descompactar).
5. O Overleaf criará o projeto com todos os capítulos, referências e capas pré-configurados.

## Compilação:
- O motor de compilação recomendado no Overleaf é **pdfLaTeX** ou **XeLaTeX** com o TeX Live mais recente.
- Para gerar as citações ABNT corretas, certifique-se de que a opção de bibliografia esteja configurada para **BibTeX**.
"""
        zf.writestr("INSTRUCOES_OVERLEAF.md", instructions)

    zip_buffer.seek(0)
    return zip_buffer
