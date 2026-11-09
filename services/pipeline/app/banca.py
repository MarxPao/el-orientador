"""Academic Defense Committee Simulator — Socratic Oral Defense Training.

Simulates committee examiners (Strict/Methodological vs Constructive/Thematic)
grounded on the student's actual manuscript sections and verified evidence.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .repo import Repo

logger = logging.getLogger("orientador.banca")

PROMPT_VERSION = "banca_defense_v0.1"

EXAMINER_PROFILES = {
    "estrito": {
        "title": "Examinador Metodológico (Perfil Estrito)",
        "description": "Foco em validade interna/externa, delimitação da amostra, inferência causal, limites e contraexemplos.",
        "tone": "Formal, incisivo, analítico e rigoroso com evidências empíricas.",
    },
    "construtivo": {
        "title": "Examinador Propositivo (Perfil Construtivo)",
        "description": "Foco em contribuição acadêmica, relevância social, originalidade e diálogo entre referenciais teóricos.",
        "tone": "Instigante, dialético, encorajador e voltado à maturidade crítica.",
    },
}


def _extract_plain_text(content: Any) -> str:
    """Extract plain text from TipTap JSON or plain strings."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, dict):
        return ""
    if content.get("type") == "text":
        return str(content.get("text", ""))
    chunks = []
    for child in content.get("content") or []:
        t = _extract_plain_text(child)
        if t:
            chunks.append(t)
    return " ".join(chunks)


def compile_defense_context(repo: Repo, project_id: str) -> dict:
    """Compile manuscript text, claims, and project metadata for the defense committee."""
    project = repo.get_project_by_id(project_id) or {}
    sections = repo.list_sections(project_id) if hasattr(repo, "list_sections") else []
    claims = repo.list_project_claims(project_id) if hasattr(repo, "list_project_claims") else []
    docs = {d["id"]: d for d in (repo.list_documents(project_id) if hasattr(repo, "list_documents") else [])}

    sec_summaries = []
    for s in sections:
        txt = _extract_plain_text(s.get("content"))
        if txt:
            snippet = txt[:400] + ("…" if len(txt) > 400 else "")
            sec_summaries.append(f"• Seção '{s.get('title', 'Sem título')}': {snippet}")

    claim_summaries = []
    for c in claims[:12]:
        doc = docs.get(c.get("document_id")) or {}
        author = (doc.get("authors") or ["Autor"])[0]
        year = doc.get("year") or "s.d."
        claim_summaries.append(
            f"• Afirmação: \"{c.get('statement')}\" (Citação: \"{c.get('quote')}\", p. {c.get('page_no')}, {author}, {year})"
        )

    return {
        "project_id": project_id,
        "title": project.get("title") or "Trabalho Acadêmico",
        "work_type": project.get("work") or "tcc",
        "institution": project.get("institution") or "Instituição de Ensino Superior",
        "research_problem": project.get("research_problem") or "Problema não formalizado",
        "sections": sec_summaries,
        "claims": claim_summaries,
        "sections_count": len(sec_summaries),
        "claims_count": len(claim_summaries),
    }


def _format_context_prompt(context: dict, examiner_profile: str) -> str:
    profile_info = EXAMINER_PROFILES.get(examiner_profile, EXAMINER_PROFILES["estrito"])
    sections_block = "\n".join(context.get("sections") or ["(Nenhuma seção redigida no manuscrito ainda)"])
    claims_block = "\n".join(context.get("claims") or ["(Nenhuma alegação verificada registrada)"])

    return f"""Dados do Trabalho para a Arguição:
- Título: {context.get('title')}
- Tipo de trabalho: {context.get('work_type')}
- Instituição: {context.get('institution')}
- Problema de pesquisa delimitado: {context.get('research_problem')}
- Perfil do examinador: {profile_info['title']} ({profile_info['tone']})

Seções redigidas pelo estudante no manuscrito:
{sections_block}

Alegações e citações verificadas na literatura do projeto:
{claims_block}
"""


def generate_opening_question(context: dict, examiner_profile: str, client: Any = None) -> dict:
    """Generate the first incisive defense question based on the student's text."""
    if examiner_profile not in EXAMINER_PROFILES:
        examiner_profile = "estrito"

    if client:
        system = f"""Você é membro de uma banca acadêmica com o seguinte perfil:
{EXAMINER_PROFILES[examiner_profile]['title']}: {EXAMINER_PROFILES[examiner_profile]['description']}
Tom: {EXAMINER_PROFILES[examiner_profile]['tone']}

Sua tarefa: formular a primeira pergunta de abertura da arguição oral do estudante.
A pergunta deve ser afiada, substantiva e citar ou fazer referência explícita ao título, problema ou a uma das seções ou evidências do trabalho do estudante.
Nunca seja genérico. Não elogie nem faça discursos introdutórios longos."""

        user = f"""{_format_context_prompt(context, examiner_profile)}

Formule a pergunta inicial de arguição.
Responda estritamente em JSON com o formato:
{{
  "question": "texto da pergunta direta ao aluno",
  "focus_area": "metodologia | fundamentacao | problema_pesquisa | escopo",
  "examiner_tone": "estrito | construtivo"
}}"""

        schema = {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "focus_area": {"type": "string"},
                "examiner_tone": {"type": "string"},
            },
            "required": ["question", "focus_area"],
        }
        try:
            res = client.complete_json(system, user, schema)
            if res and isinstance(res, dict) and res.get("question"):
                return {
                    "question": res["question"],
                    "focus_area": res.get("focus_area", "metodologia"),
                    "examiner_profile": examiner_profile,
                    "prompt_version": PROMPT_VERSION,
                }
        except Exception as e:
            logger.warning("Opening question LLM failed, using deterministic scaffold: %s", e)

    # Deterministic fallback when client is None or fails
    title = context.get("title", "seu trabalho")
    problem = context.get("research_problem")
    first_sec = context.get("sections")[0] if context.get("sections") else None

    if examiner_profile == "estrito":
        if first_sec:
            q = f"Em seu manuscrito, na {first_sec.split(':')[0]}, você apresenta premissas centrais sobre '{title}'. Diante de potenciais vieses metodológicos, como você assegura a validade dos achados caso seu recorte encontre contraexemplos empíricos?"
        else:
            q = f"Ao analisar sua proposta de pesquisa sobre '{title}' ({problem}), qual é a principal fragilidade metodológica do seu desenho que impediria uma generalização segura dos resultados?"
        focus = "validade_metodologica"
    else:
        if first_sec:
            q = f"Considerando o problema que você delimitou ({problem}), de que maneira a articulação apresentada em seu trabalho avança o estado da arte na área, diferenciando-se das abordagens tradicionais já consolidadas?"
        else:
            q = f"Seu estudo se propõe a investigar '{title}'. Qual é o impacto prático e formativo mais urgente que a conclusão desta pesquisa entrega para a sua área de atuação?"
        focus = "relevancia_e_contribuicao"

    return {
        "question": q,
        "focus_area": focus,
        "examiner_profile": examiner_profile,
        "prompt_version": None,
    }


def evaluate_turn_and_reply(
    context: dict,
    examiner_profile: str,
    history: list[dict],
    student_answer: str,
    client: Any = None,
) -> dict:
    """Evaluate student's answer using rubrics and provide the next counter-argument or question."""
    if examiner_profile not in EXAMINER_PROFILES:
        examiner_profile = "estrito"

    history_text = "\n".join(
        f"[{t.get('speaker', 'examiner').upper()}]: {t.get('content')}"
        for t in history[-6:]
    )

    if client:
        system = f"""Você é membro examinador de banca acadêmica ({EXAMINER_PROFILES[examiner_profile]['title']}).
Avalie a sustentação oral do estudante com base em rubricas de 0 a 3 pontos:
- dominio_conteudo (0-3): precisão conceitual e resposta direta à questão.
- fundamentacao_evidencias (0-3): citação de autores, dados empíricos e literatura.
- coerencia_metodologica (0-3): reconhecimento de limites, rigor de raciocínio e consistência.
- postura_argumentativa (0-3): serenidade acadêmica, firmeza sem defensividade.

Em seguida, gere um parecer pontual (turn_feedback) e a próxima pergunta ou tréplica (next_question) aprofundando outro ponto do trabalho."""

        user = f"""{_format_context_prompt(context, examiner_profile)}

Histórico recente da arguição:
{history_text}

Resposta que o estudante acabou de fornecer:
"{student_answer}"

Retorne estritamente um JSON no seguinte formato:
{{
  "rubric_scores": {{
    "dominio_conteudo": 2,
    "fundamentacao_evidencias": 2,
    "coerencia_metodologica": 2,
    "postura_argumentativa": 2
  }},
  "turn_feedback": "Síntese avaliativa do desempenho nesta resposta.",
  "next_question": "Próxima questão incisiva da banca para continuar a arguição.",
  "focus_area": "fundamentacao | metodo | resultados | conclusao"
}}"""

        schema = {
            "type": "object",
            "properties": {
                "rubric_scores": {
                    "type": "object",
                    "properties": {
                        "dominio_conteudo": {"type": "integer"},
                        "fundamentacao_evidencias": {"type": "integer"},
                        "coerencia_metodologica": {"type": "integer"},
                        "postura_argumentativa": {"type": "integer"},
                    },
                    "required": ["dominio_conteudo", "fundamentacao_evidencias", "coerencia_metodologica", "postura_argumentativa"],
                },
                "turn_feedback": {"type": "string"},
                "next_question": {"type": "string"},
                "focus_area": {"type": "string"},
            },
            "required": ["rubric_scores", "turn_feedback", "next_question"],
        }
        try:
            res = client.complete_json(system, user, schema)
            if res and isinstance(res, dict) and "rubric_scores" in res:
                return {
                    "rubric_scores": res["rubric_scores"],
                    "turn_feedback": res.get("turn_feedback", "Resposta avaliada pela banca."),
                    "next_question": res.get("next_question", "Como você responde às limitações teóricas do seu método?"),
                    "focus_area": res.get("focus_area", "metodologia"),
                    "prompt_version": PROMPT_VERSION,
                }
        except Exception as e:
            logger.warning("Turn evaluation LLM failed, using deterministic evaluation: %s", e)

    # Deterministic rubric calculation based on academic heuristics
    words = len(student_answer.split())
    has_author = any(term in student_answer.lower() for term in ("segundo", "conforme", "de acordo", "(", ")", "afirma", "estudo"))
    has_limits = any(term in student_answer.lower() for term in ("limite", "limitação", "recorte", "escopo", "entretanto", "contudo", "embora"))
    has_method = any(term in student_answer.lower() for term in ("método", "dados", "amostra", "análise", "procedimento", "pesquisa"))

    score_dom = 3 if words >= 40 else (2 if words >= 20 else 1)
    score_evid = 3 if (has_author and words >= 30) else (2 if has_author or words >= 30 else 1)
    score_met = 3 if (has_limits and has_method) else (2 if (has_limits or has_method) else 1)
    score_post = 3 if words >= 35 else (2 if words >= 15 else 1)

    turn_count = len([t for t in history if t.get("speaker") == "examiner"])
    if examiner_profile == "estrito":
        fb = "Sua resposta aponta elementos relevantes, mas a banca exige precisão quanto ao controle de variáveis e limites da literatura."
        next_q = f"Aprofundando a discussão ({turn_count + 1}ª questão): se a banca questionar a representatividade do seu corpus bibliográfico frente a publicações internacionais recentes, como você defende a atualidade do seu referencial?"
    else:
        fb = "Boa fundamentação. O argumento demonstra maturidade, mas precisa explicitar a ponte entre o referencial teórico e a prática investigada."
        next_q = f"Na sequência ({turn_count + 1}ª questão): de que maneira as conclusões do seu trabalho dialogam com políticas públicas ou com a formação docente no cenário educacional contemporâneo?"

    return {
        "rubric_scores": {
            "dominio_conteudo": score_dom,
            "fundamentacao_evidencias": score_evid,
            "coerencia_metodologica": score_met,
            "postura_argumentativa": score_post,
        },
        "turn_feedback": fb,
        "next_question": next_q,
        "focus_area": "metodologia" if examiner_profile == "estrito" else "relevancia",
        "prompt_version": None,
    }


def synthesize_final_report(
    context: dict,
    examiner_profile: str,
    turns: list[dict],
    client: Any = None,
) -> dict:
    """Generate final committee verdict, strengths, vulnerabilities, and tactical recommendations."""
    # Compute average rubric score across student turns
    all_scores = [t.get("rubric_scores") for t in turns if t.get("rubric_scores")]
    if all_scores:
        avg_score = sum(
            sum(s.values()) / max(len(s), 1) for s in all_scores
        ) / len(all_scores)
        scaled_score = round((avg_score / 3.0) * 10, 1)
    else:
        scaled_score = 7.0

    if client:
        system = f"""Você é presidente de banca examinadora ({EXAMINER_PROFILES.get(examiner_profile, EXAMINER_PROFILES['estrito'])['title']}).
Sua tarefa é emitir a ATA DE SIMULAÇÃO DE DEFESA (parecer formativo final) sintetizando a performance do estudante na arguição oral.
O veredito deve ser justo, sóbrio e rigoroso."""

        turns_summary = []
        for i, t in enumerate(turns):
            turns_summary.append(f"Turno {i+1} [{t.get('speaker')}]: {t.get('content')[:200]}")

        user = f"""{_format_context_prompt(context, examiner_profile)}

Histórico completo da arguição:
{chr(10).join(turns_summary)}

Média de pontuação das rubricas: {scaled_score}/10.0

Gere o parecer final em JSON com a seguinte estrutura:
{{
  "verdict": "apto_com_louvor | apto_com_ressalvas | recomenda_revisao",
  "verdict_title": "Título oficial do veredito acadêmico",
  "overall_score": {scaled_score},
  "strengths": ["ponto forte 1 observado na sustentação", "ponto forte 2"],
  "vulnerabilities": ["flanco ou fragilidade apontada 1", "flanco 2"],
  "recommendations": ["recomendação prática 1 para o dia da defesa real", "recomendação 2", "recomendação 3"]
}}"""

        schema = {
            "type": "object",
            "properties": {
                "verdict": {"type": "string"},
                "verdict_title": {"type": "string"},
                "overall_score": {"type": "number"},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "vulnerabilities": {"type": "array", "items": {"type": "string"}},
                "recommendations": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["verdict", "verdict_title", "overall_score", "strengths", "vulnerabilities", "recommendations"],
        }
        try:
            res = client.complete_json(system, user, schema)
            if res and isinstance(res, dict) and "verdict" in res:
                return {
                    **res,
                    "overall_score": res.get("overall_score", scaled_score),
                    "examiner_profile": examiner_profile,
                    "prompt_version": PROMPT_VERSION,
                }
        except Exception as e:
            logger.warning("Final report LLM failed, using deterministic report: %s", e)

    # Deterministic final report
    if scaled_score >= 8.5:
        verdict = "apto_com_louvor"
        v_title = "Apto com Louvor — Excelente Sustentação Oral"
    elif scaled_score >= 6.0:
        verdict = "apto_com_ressalvas"
        v_title = "Apto com Ressalvas — Ajustes Recomendados antes da Banca"
    else:
        verdict = "recomenda_revisao"
        v_title = "Recomenda-se Revisão Substancial antes da Defesa"

    strengths = [
        "Articulação coerente com o problema de pesquisa proposto.",
        "Postura receptiva aos questionamentos da banca, mantendo o foco acadêmico.",
    ]
    vulnerabilities = [
        "Necessidade de fundamentar respostas metodológicas diretamente nos autores do acervo.",
        "Cuidado para não fazer afirmações causais sem a comprovação experimental correspondente.",
    ]
    recommendations = [
        "Revisar o capítulo metodológico garantindo que o recorte amostral e critérios de exclusão estejam explícitos.",
        "Preparar notas de apoio com as principais referências empíricas para consulta rápida durante a arguição.",
        "Praticar a resposta direta à pergunta da banca antes de expandir para considerações teóricas mais amplas.",
    ]

    return {
        "verdict": verdict,
        "verdict_title": v_title,
        "overall_score": scaled_score,
        "strengths": strengths,
        "vulnerabilities": vulnerabilities,
        "recommendations": recommendations,
        "examiner_profile": examiner_profile,
        "prompt_version": None,
    }
