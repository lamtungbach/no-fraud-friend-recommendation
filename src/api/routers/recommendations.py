"""Thin safe-recommendation HTTP transport."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.observability import record_recommendation, record_recommendation_error
from src.api.runtime import ApiRuntime
from src.api.schemas import (
    EmptyResultContextResponse,
    PYMKRecommendationExplanationResponse,
    RecommendationRequest,
    RecommendationResponse,
    RetrievalRankingDiagnosticsResponse,
    SafeRecommendationItem,
    SafeTwoHopPathSummaryResponse,
)

router = APIRouter(prefix="/v1", tags=["recommendations"])


def get_runtime(request: Request) -> ApiRuntime:
    return request.app.state.runtime


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    response_model_exclude_none=True,
)
def recommend_safe(
    payload: RecommendationRequest,
    runtime: ApiRuntime = Depends(get_runtime),
) -> RecommendationResponse:
    """Validate, orchestrate and serialize only; core owns retrieval and Trust."""

    if payload.top_k > runtime.settings.max_top_k:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"top_k must be less than or equal to configured MAX_TOP_K ({runtime.settings.max_top_k})",
        )
    ready, _, _ = runtime.readiness()
    if not ready:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="service not ready")
    started = time.perf_counter()
    try:
        details = None
        if (
            payload.include_diagnostics
            or payload.include_explanations
            or payload.include_path_summaries
            or payload.include_empty_result_context
        ):
            details = runtime.engine.recommend_safe_details(
                payload.user_id,
                payload.top_k,
                top_m=runtime.settings.raw_top_m,
                trust_provider=runtime.trust_provider,
                trust_policy=runtime.trust_policy,
                include_explanations=payload.include_explanations,
                include_path_summaries=payload.include_path_summaries,
                include_empty_result_context=payload.include_empty_result_context,
            )
            result = details.safe_result
        else:
            result = runtime.engine.recommend_safe(
                payload.user_id,
                payload.top_k,
                top_m=runtime.settings.raw_top_m,
                trust_provider=runtime.trust_provider,
                trust_policy=runtime.trust_policy,
            )
    except KeyError as error:
        record_recommendation_error()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown user_id") from error
    except (RuntimeError, ValueError) as error:
        record_recommendation_error()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="recommendation unavailable") from error
    record_recommendation(result, time.perf_counter() - started)
    return RecommendationResponse(
        user_id=payload.user_id,
        recommendations=[SafeRecommendationItem(**item.__dict__) for item in result.recommendations],
        graph_version=result.graph_version,
        trust_version=result.trust_version,
        trust_policy_version=result.trust_policy_version,
        raw_cache_hit=result.raw_cache_hit,
        diagnostics=(
            RetrievalRankingDiagnosticsResponse(**details.diagnostics.__dict__)
            if payload.include_diagnostics and details is not None
            else None
        ),
        explanations=(
            [PYMKRecommendationExplanationResponse(**item.__dict__) for item in details.explanations]
            if payload.include_explanations and details is not None
            else None
        ),
        path_summaries=(
            [SafeTwoHopPathSummaryResponse(**item.__dict__) for item in details.path_summaries]
            if payload.include_path_summaries and details is not None
            else None
        ),
        empty_result_context=(
            EmptyResultContextResponse(**details.empty_result_context.__dict__)
            if payload.include_empty_result_context
            and details is not None
            and details.empty_result_context is not None
            else None
        ),
    )
