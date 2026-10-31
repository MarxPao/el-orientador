from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class Certainty(str, Enum):
    demonstra = "demonstra"
    sugere = "sugere"
    especula = "especula"
    desconhecido = "desconhecido"


class RelationType(str, Enum):
    apoia = "apoia"
    contrasta = "contrasta"
    estende = "estende"
    aplica = "aplica"
    critica = "critica"


class Scope(BaseModel):
    population: str | None = None
    method: str | None = None
    context: str | None = None


class RawClaim(BaseModel):
    """What the LLM returns for each claim."""
    concept: str = Field(min_length=2)
    statement: str = Field(min_length=10)
    quote: str = Field(min_length=10)
    page: int | None = None
    scope: Scope = Scope()
    certainty: Certainty = Certainty.desconhecido


class ExtractionOutput(BaseModel):
    claims: list[RawClaim]


class VerifiedClaim(RawClaim):
    quote_verified: bool
    verify_method: str  # exact | loose | none | too_short
    page_verified: int | None = None
    char_start: int | None = None
    char_end: int | None = None


class RelationCandidate(BaseModel):
    concept_a: str
    concept_b: str
    relation: RelationType
    rationale: str
    evidence_a_quote: str
    evidence_b_quote: str
    confidence: float = Field(ge=0, le=1)
