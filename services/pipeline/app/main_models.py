"""Modelos Pydantic compartilhados e estado de rate-limit de login.

Importado por todos os roteadores de domínio para manter uma única fonte de verdade
para os tipos de entrada da API.
"""
from __future__ import annotations

import os
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Enumerações
# ---------------------------------------------------------------------------

class WorkType(str, Enum):
    tcc = "tcc"
    pre_projeto_mestrado = "pre_projeto_mestrado"
    pre_projeto_doutorado = "pre_projeto_doutorado"
    dissertacao = "dissertacao"
    tese = "tese"
    artigo = "artigo"


class RelationType(str, Enum):
    apoia = "apoia"
    contrasta = "contrasta"
    estende = "estende"
    aplica = "aplica"
    critica = "critica"


# ---------------------------------------------------------------------------
# Modelos de autenticação
# ---------------------------------------------------------------------------

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


# ---------------------------------------------------------------------------
# Modelos de projeto
# ---------------------------------------------------------------------------

class ProjectIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    work: WorkType
    institution: str | None = Field(default=None, max_length=200)
    citation_style: str = "abnt"
    deadline: date | None = None
    weekly_hours: int | None = Field(default=None, ge=1, le=100)
    research_problem: str | None = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Modelos de documentos / biblioteca
# ---------------------------------------------------------------------------

class DoiIn(BaseModel):
    doi: str = Field(min_length=7, max_length=300)


class ImportCitationIn(BaseModel):
    raw_citation: str = Field(min_length=8, max_length=2000)
    citation_style: str = Field(default="abnt", max_length=20)


class TextCompareIn(BaseModel):
    claim_a_id: str
    claim_b_id: str
    relation_type: Literal["corroboracao", "contraponto", "complementaridade", "lacuna"] = "complementaridade"
    student_analysis: str | None = Field(default=None, max_length=1500)
    section_id: str | None = None
    intensity: int = Field(default=35, ge=0, le=100)
    insert_into_section: bool = False


# ---------------------------------------------------------------------------
# Modelos de mapa / grafo de conhecimento
# ---------------------------------------------------------------------------

class EdgeDecisionIn(BaseModel):
    action: Literal["confirm", "reject", "edit"]
    relation: RelationType | None = None
    note: str | None = Field(default=None, max_length=500)


class GapDecisionIn(BaseModel):
    status: Literal["open", "adopted_as_problem", "dismissed"]
    note: str | None = Field(default=None, max_length=1000)


# ---------------------------------------------------------------------------
# Modelos de árvore / gate
# ---------------------------------------------------------------------------

class NodeUpdateIn(BaseModel):
    status: Literal["locked", "available", "done", "skipped", "needs_review"] | None = None
    queued: bool | None = None
    skipped_reason: str | None = Field(default=None, max_length=500)


class NodeFeedbackIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class SharedNodeFeedbackIn(BaseModel):
    advisor_email: EmailStr
    advisor_name: str = Field(default="", max_length=120)
    content: str = Field(min_length=1, max_length=5000)


class GateTurnIn(BaseModel):
    user_input: str = Field(default="", max_length=5000)
    history: list[dict[str, str]] = Field(default_factory=list)
    skip: bool = False
    skip_reason: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Modelos de seções
# ---------------------------------------------------------------------------

class SectionIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None
    position: int = 0
    content: dict = Field(default_factory=dict)
    concept_ids: list[str] = Field(default_factory=list)


class SectionUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: str | None = None
    position: int | None = None
    content: dict | None = None
    concept_ids: list[str] | None = None


class AiAssistIn(BaseModel):
    mode: Literal["polish", "coauthor", "draft"] | None = None
    intensity: int | None = Field(default=None, ge=0, le=100)
    selected_text: str | None = Field(default=None, max_length=5000)
    instruction: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Modelos de autoria / proveniência
# ---------------------------------------------------------------------------

class ValidateAuthenticityIn(BaseModel):
    sync_prism: bool = False


class PasteIn(BaseModel):
    text: str = Field(min_length=1, max_length=50000)


class ConfirmParaphraseIn(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
    event_id: str | None = None


class DismissParaphraseIn(BaseModel):
    text: str = Field(min_length=1, max_length=50000)


class DeclarePasteIn(BaseModel):
    declared: Literal["own_text"] | None = None


# ---------------------------------------------------------------------------
# Modelos de orientadores / comentários
# ---------------------------------------------------------------------------

class AdvisorInviteIn(BaseModel):
    advisor_email: EmailStr
    can_comment: bool = True


class CommentIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class CommentUpdateIn(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    resolved: bool | None = None


class SharedCommentIn(BaseModel):
    section_id: str
    author_name: str = Field(min_length=2, max_length=120)
    author_email: EmailStr
    content: str = Field(min_length=1, max_length=5000)
    anchor_quote: str | None = Field(default=None, max_length=500)


class BetaFeedbackIn(BaseModel):
    project_id: str | None = None
    overall_rating: int = Field(ge=1, le=5)
    socratic_gate_helpful: int = Field(ge=1, le=5)
    evidence_trust: int = Field(ge=1, le=5)
    relief_level: int = Field(ge=1, le=5)
    pricing_preference: str = Field(min_length=2, max_length=50)
    brand_impression: str = Field(min_length=2, max_length=100)
    comments: str | None = Field(default=None, max_length=2000)


class RepositoryImportIn(BaseModel):
    source_id: str | None = None
    repository: str = Field(pattern="^(scielo|bdtd|openalex|crossref|outro)$")
    title: str = Field(min_length=1, max_length=500)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1800, le=2100)
    venue: str | None = Field(default=None, max_length=255)
    doi: str | None = Field(default=None, max_length=255)
    pdf_url: str | None = Field(default=None, max_length=1000)
    fetch_pdf: bool = False


class BancaSessionCreateIn(BaseModel):
    examiner_profile: str = Field(default="estrito", pattern="^(estrito|construtivo)$")


class BancaTurnIn(BaseModel):
    answer: str = Field(min_length=1, max_length=10000)


# ---------------------------------------------------------------------------
# Rate-limit de login (estado em memória, por processo)
# ---------------------------------------------------------------------------

_LOGIN_FAILS: dict[str, list[float]] = {}


def _login_limits() -> tuple[int, int]:
    def _i(name: str, default: int) -> int:
        try:
            return max(1, int(os.environ.get(name, default)))
        except ValueError:
            return default
    return _i("LOGIN_MAX_FAILS", 8), _i("LOGIN_LOCK_SECONDS", 300)


def _login_failed(key: str) -> None:
    import time
    _, window = _login_limits()
    now = time.time()
    recent = [t for t in _LOGIN_FAILS.get(key, []) if now - t < window]
    recent.append(now)
    _LOGIN_FAILS[key] = recent
    if len(_LOGIN_FAILS) > 5000:  # limita uso de memória
        for k in [k for k, v in _LOGIN_FAILS.items() if now - v[-1] >= window]:
            _LOGIN_FAILS.pop(k, None)


def _login_lock_remaining(key: str) -> int:
    import time
    limit, window = _login_limits()
    now = time.time()
    recent = [t for t in _LOGIN_FAILS.get(key, []) if now - t < window]
    if len(recent) < limit:
        return 0
    return int(window - (now - recent[-1])) + 1


# ---------------------------------------------------------------------------
# Constantes de mensagens de IA
# ---------------------------------------------------------------------------

LLM_DOWN_MSG = (
    "O serviço de IA está indisponível no momento. Tente de novo em alguns minutos."
)
AI_ASSIST_NO_LLM_MSG = (
    "IA não configurada neste servidor: entregamos um esqueleto com as citações verificadas "
    "e lacunas [entre colchetes] para você completar com a sua análise."
)
AI_ASSIST_DEGRADED_MSG = (
    "O serviço de IA falhou agora: entregamos um esqueleto com as citações verificadas "
    "e lacunas [entre colchetes] para você completar. Tente de novo em alguns minutos."
)
GATE_NO_LLM_MSG = (
    "O diálogo socrático precisa de IA ativa, e ela não está configurada neste servidor. "
    "Você pode avançar com aviso consciente: a etapa fica registrada como pulada no relatório do orientador."
)
CONTEXT_CHARS = 250
