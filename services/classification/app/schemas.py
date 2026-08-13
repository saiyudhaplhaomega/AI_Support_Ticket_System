"""Request/response models for ai.classify-ticket.v1 and ai.rag-lookup.v1.

These mirror the JSON Schemas published in
capability-module-architecture.md §3.1/§3.2 exactly for the required fields.
Additional *optional* fields below (e.g. `collection` on rag-lookup) are
additive per the versioning rule in §4 ("additive optional fields do not
require a bump") and documented in README.md.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# ai.classify-ticket.v1
# ---------------------------------------------------------------------------


class ClassifyTicketInput(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000, description="Ticket body to classify.")
    context: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional passthrough context. Recognized key: "
            "`categories` (string[]) — override the default taxonomy for this call."
        ),
    )
    locale: str | None = Field(default=None, max_length=32)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


class ClassifyTicketOutputData(BaseModel):
    category: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    raw_model_output: dict[str, Any] | None = None


# Internal shape asked of the OpenAI structured-output call. Kept separate
# from ClassifyTicketOutputData so the wire contract can gain fields (e.g.
# `raw_model_output`) without changing what we require the model to emit.
class _ModelClassification(BaseModel):
    category: str = Field(..., description="Best-fit category from the provided taxonomy.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Self-assessed confidence, 0-1.")
    tags: list[str] = Field(default_factory=list, description="Short free-form labels, e.g. 'refund', 'urgent'.")


# ---------------------------------------------------------------------------
# ai.rag-lookup.v1
# ---------------------------------------------------------------------------


class RagLookupInput(BaseModel):
    query: str = Field(..., min_length=1, max_length=8_000)
    top_k: int | None = Field(default=None, ge=1, le=200)
    filter: dict[str, Any] | None = Field(
        default=None,
        description="Qdrant filter payload (must/should/must_not), passed through to the vector store.",
    )
    collection: str | None = Field(
        default=None,
        description=(
            "Optional Qdrant collection name (additive field, not in the v1 spec's "
            "required set). Defaults to AI_RAG_COLLECTION so single-collection "
            "products never need to pass it."
        ),
    )

    @field_validator("query")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank")
        return v


class RagMatch(BaseModel):
    id: str
    score: float
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagLookupOutputData(BaseModel):
    matches: list[RagMatch]


# ---------------------------------------------------------------------------
# Internal ingestion endpoint (operational tooling, not a published
# family.module interface — see README "Ingestion" section).
# ---------------------------------------------------------------------------


class IngestRecord(BaseModel):
    id: str | None = Field(default=None, description="Stable id; generated if omitted.")
    content: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    collection: str | None = None
    records: list[IngestRecord] = Field(..., min_length=1, max_length=500)

    @field_validator("records")
    @classmethod
    def _non_empty(cls, v: list[IngestRecord]) -> list[IngestRecord]:
        if not v:
            raise ValueError("records must not be empty")
        return v


class IngestOutputData(BaseModel):
    collection: str
    ingested: int
