"""Public HTTP schemas; raw PYMK candidates are intentionally not exposed."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(ge=0)
    top_k: int = Field(ge=1)
    include_diagnostics: bool = False
    include_explanations: bool = False
    include_path_summaries: bool = False
    include_empty_result_context: bool = False


class SafeRecommendationItem(BaseModel):
    candidate_id: int
    score: float
    rank: int = Field(ge=1)
    eligibility: str
    risk_score: float | None = None
    trust_score: float | None = None
    reason_code: str | None = None


class RetrievalRankingDiagnosticsResponse(BaseModel):
    """Aggregate-only PYMK execution evidence; no raw candidate IDs."""

    graph_version: str
    requested_top_k: int = Field(ge=1)
    raw_top_m: int = Field(ge=1)
    raw_cache_hit: bool
    stage_execution: Literal["computed", "cache_hit"]
    first_hop_seen: int | None = Field(default=None, ge=0)
    first_hop_used: int | None = Field(default=None, ge=0)
    first_hop_capped: bool | None = None
    second_hop_expansions: int | None = Field(default=None, ge=0)
    second_hop_seen: int | None = Field(default=None, ge=0)
    second_hop_used: int | None = Field(default=None, ge=0)
    second_hop_capped: bool | None = None
    unique_candidates: int | None = Field(default=None, ge=0)
    candidates_returned: int | None = Field(default=None, ge=0)
    candidate_capped: bool | None = None
    excluded_self: int | None = Field(default=None, ge=0)
    excluded_existing_connection: int | None = Field(default=None, ge=0)
    duplicate_candidates: int | None = Field(default=None, ge=0)
    retrieval_truncated: bool | None = None
    scored_candidates: int | None = Field(default=None, ge=0)
    raw_ranked_count: int = Field(ge=0)
    returned_safe_count: int = Field(ge=0)
    first_hop_cap: int | None = Field(default=None, ge=0)
    second_hop_cap: int | None = Field(default=None, ge=0)
    candidate_cap: int | None = Field(default=None, ge=0)
    cache_lookup_ms: float = Field(ge=0)
    retrieval_ms: float | None = Field(default=None, ge=0)
    scoring_ms: float | None = Field(default=None, ge=0)
    total_backend_ms: float = Field(ge=0)


class PYMKRecommendationExplanationResponse(BaseModel):
    """Topology evidence for an already-safe candidate, without path IDs."""

    candidate_id: int
    rank: int = Field(ge=1)
    score: float
    graph_version: str
    graph_semantics: Literal["directed", "mutual"]
    ranking_method: Literal["cn", "aa", "jaccard", "pa"]
    common_neighbors: float = Field(ge=0)
    adamic_adar: float = Field(ge=0)
    jaccard: float = Field(ge=0)
    preferential_attachment: float = Field(ge=0)
    note: str


class SafeTwoHopPathSummaryResponse(BaseModel):
    """Safe aggregate two-hop evidence without intermediate graph-node IDs."""

    candidate_id: int
    graph_version: str
    graph_semantics: Literal["directed", "mutual"]
    path_count_total: int | None = Field(default=None, ge=0)
    path_count_observed: int = Field(ge=0)
    sampled_path_count: int = Field(ge=0, le=10)
    scan_truncated: bool
    truncated: bool
    edge_type_evidence_available: bool
    note: str


class EmptyResultContextResponse(BaseModel):
    """Neutral evidence-backed reason for an empty Safe Top-K response."""

    status: Literal[
        "ISOLATED_USER",
        "NO_TWO_HOP_CANDIDATES",
        "NO_RANKED_CANDIDATES",
        "EMPTY_RAW_RESULT_UNSPECIFIED",
        "SAFE_RESULT_EMPTY_UNSPECIFIED",
        "TRUST_UNAVAILABLE_FAIL_CLOSED",
    ]
    graph_version: str
    evidence: str


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: list[SafeRecommendationItem]
    graph_version: str
    trust_version: str
    trust_policy_version: str
    raw_cache_hit: bool
    diagnostics: RetrievalRankingDiagnosticsResponse | None = None
    explanations: list[PYMKRecommendationExplanationResponse] | None = None
    path_summaries: list[SafeTwoHopPathSummaryResponse] | None = None
    empty_result_context: EmptyResultContextResponse | None = None


class DatasetJobCreateRequest(BaseModel):
    """Local-admin request; dataset paths are selected server-side."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: Literal["mgtab"] = "mgtab"
    graph_version: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
    graph_semantics: Literal["directed", "mutual"] = "directed"
    build_config: dict[str, str | int | float | bool] = Field(default_factory=dict)


class DatasetJobResponse(BaseModel):
    job_id: str
    dataset_id: str
    graph_version: str
    graph_semantics: str
    status: str
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None
