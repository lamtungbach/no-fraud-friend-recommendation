"""Thin safe-recommendation HTTP transport."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.observability import record_recommendation, record_recommendation_error
from src.api.runtime import ApiRuntime
from src.api.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    SafeRecommendationItem,
)

router = APIRouter(prefix="/v1", tags=["recommendations"])


def get_runtime(request: Request) -> ApiRuntime:
    return request.app.state.runtime


@router.post("/recommendations", response_model=RecommendationResponse)
def recommend_safe(
    payload: RecommendationRequest,
    runtime: ApiRuntime = Depends(get_runtime),
) -> RecommendationResponse:
    """Validate, orchestrate and serialize only; core owns retrieval and Trust."""

    if payload.top_k > runtime.settings.max_top_k:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"top_k must be less than or equal to configured MAX_TOP_K ({runtime.settings.max_top_k})",
        )
    ready, _, _ = runtime.readiness()
    if not ready:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="service not ready")
    started = time.perf_counter()
    try:
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
    )
