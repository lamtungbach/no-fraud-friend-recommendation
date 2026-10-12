"""Public HTTP schemas; raw PYMK candidates are intentionally not exposed."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(ge=0)
    top_k: int = Field(ge=1)


class SafeRecommendationItem(BaseModel):
    candidate_id: int
    score: float
    rank: int = Field(ge=1)
    eligibility: str
    risk_score: float | None = None
    trust_score: float | None = None
    reason_code: str | None = None


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: list[SafeRecommendationItem]
    graph_version: str
    trust_version: str
    trust_policy_version: str
    raw_cache_hit: bool
