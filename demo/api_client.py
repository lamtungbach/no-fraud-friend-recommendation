"""Small, testable HTTP client used by the Streamlit demo only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

_SAFE_RECOMMENDATION_FIELDS = (
    "candidate_id",
    "score",
    "rank",
    "eligibility",
    "risk_score",
    "trust_score",
    "reason_code",
)


class DemoApiError(RuntimeError):
    """Safe, UI-facing API failure with an optional HTTP status."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class RecommendationResult:
    user_id: int
    recommendations: list[dict[str, Any]]
    graph_version: str
    trust_version: str
    trust_policy_version: str
    raw_cache_hit: bool
    diagnostics: dict[str, Any] | None = None
    explanations: list[dict[str, Any]] | None = None
    path_summaries: list[dict[str, Any]] | None = None
    empty_result_context: dict[str, Any] | None = None


@dataclass(frozen=True)
class DatasetJob:
    job_id: str
    dataset_id: str
    graph_version: str
    graph_semantics: str
    status: str
    created_at: str
    updated_at: str
    error_code: str | None


class PymkApiClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 15.0, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def live(self) -> dict[str, Any]:
        return self._get_json("/health/live")

    def ready(self) -> dict[str, Any]:
        return self._get_json("/health/ready", accepted_statuses={200, 503})

    def recommend(
        self,
        user_id: int,
        top_k: int,
        *,
        include_diagnostics: bool = False,
        include_explanations: bool = False,
        include_path_summaries: bool = False,
        include_empty_result_context: bool = False,
    ) -> RecommendationResult:
        if user_id < 0 or top_k < 1:
            raise ValueError("User ID phải không âm và Top-K phải lớn hơn 0")
        request_payload = {
            "user_id": user_id,
            "top_k": top_k,
        }
        for field, enabled in (
            ("include_diagnostics", include_diagnostics),
            ("include_explanations", include_explanations),
            ("include_path_summaries", include_path_summaries),
            ("include_empty_result_context", include_empty_result_context),
        ):
            if enabled:
                request_payload[field] = True
        return _recommendation(
            self._request_json("POST", "/v1/recommendations", json=request_payload)
        )

    def trust_profile(self, user_id: int) -> dict[str, Any]:
        if user_id < 0:
            raise ValueError("User ID phải không âm")
        payload = self._get_json(f"/api/v1/trust/{user_id}")
        pillars = payload.get("pillars")
        required = {"user_id", "trust_score", "p_bot", "recommendation_tier", "decision"}
        pillar_names = {"identity_auth", "interaction_health", "network_hygiene", "content_safety"}
        if (not required.issubset(payload) or payload["user_id"] != user_id
                or not isinstance(pillars, dict) or not pillar_names.issubset(pillars)):
            raise DemoApiError("Response hồ sơ Trust không đúng định dạng")
        for value, maximum in [(payload["trust_score"], 100), (payload["p_bot"], 1),
                               *((pillars[name], 1) for name in pillar_names)]:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= maximum:
                raise DemoApiError("Response hồ sơ Trust có điểm không hợp lệ")
        return payload

    def trust_reasoning(self, user_id: int) -> dict[str, Any]:
        if user_id < 0:
            raise ValueError("User ID phải không âm")
        payload = self._request_json("POST", "/api/v1/trust/reason", json={"user_id": user_id})
        trace = payload.get("reasoning_trace")
        if payload.get("user_id") != user_id or not isinstance(trace, list) or not all(isinstance(x, str) for x in trace):
            raise DemoApiError("Response giải thích Trust không đúng định dạng")
        return payload

    def create_mgtab_job(self) -> DatasetJob:
        return _dataset_job(self._request_json("POST", "/datasets/jobs", json={"dataset_id": "mgtab"}))

    def get_job(self, job_id: str) -> DatasetJob:
        return _dataset_job(self._request_json("GET", f"/datasets/jobs/{job_id}"))

    def _get_json(self, path: str, *, accepted_statuses: set[int] | None = None) -> dict[str, Any]:
        return self._request_json("GET", path, accepted_statuses=accepted_statuses)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        accepted_statuses: set[int] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, f"{self.base_url}{path}", json=json)
        except httpx.TimeoutException as error:
            raise DemoApiError("API phản hồi quá thời gian chờ") from error
        except httpx.HTTPError as error:
            raise DemoApiError("Không thể kết nối tới FastAPI backend") from error
        accepted = accepted_statuses or {200, 202}
        if response.status_code not in accepted:
            detail = _error_detail(response)
            raise DemoApiError(detail, status_code=response.status_code)
        try:
            payload = response.json()
        except ValueError as error:
            raise DemoApiError("Backend trả về dữ liệu không phải JSON", status_code=response.status_code) from error
        if not isinstance(payload, dict):
            raise DemoApiError("Backend trả về JSON không đúng định dạng", status_code=response.status_code)
        return payload


def _recommendation(payload: dict[str, Any]) -> RecommendationResult:
    required = {"user_id", "recommendations", "graph_version", "trust_version", "trust_policy_version", "raw_cache_hit"}
    if not required.issubset(payload) or not isinstance(payload["recommendations"], list):
        raise DemoApiError("Response recommendation thiếu trường bắt buộc")
    safe_items = [item for item in payload["recommendations"] if isinstance(item, dict)]
    if len(safe_items) != len(payload["recommendations"]):
        raise DemoApiError("Response recommendation không đúng định dạng")
    safe_items = [
        {field: item[field] for field in _SAFE_RECOMMENDATION_FIELDS if field in item}
        for item in safe_items
    ]
    diagnostics = payload.get("diagnostics")
    explanations = payload.get("explanations")
    path_summaries = payload.get("path_summaries")
    empty_result_context = payload.get("empty_result_context")
    if diagnostics is not None and not isinstance(diagnostics, dict):
        raise DemoApiError("Response diagnostics must be an object")
    for label, value in (("explanations", explanations), ("path_summaries", path_summaries)):
        if value is not None and (
            not isinstance(value, list) or any(not isinstance(item, dict) for item in value)
        ):
            raise DemoApiError(f"Response {label} must be a list of objects")
    if empty_result_context is not None and not isinstance(empty_result_context, dict):
        raise DemoApiError("Response empty_result_context must be an object")
    return RecommendationResult(
        user_id=int(payload["user_id"]),
        recommendations=safe_items,
        graph_version=str(payload["graph_version"]),
        trust_version=str(payload["trust_version"]),
        trust_policy_version=str(payload["trust_policy_version"]),
        raw_cache_hit=bool(payload["raw_cache_hit"]),
        diagnostics=diagnostics,
        explanations=explanations,
        path_summaries=path_summaries,
        empty_result_context=empty_result_context,
    )


def _dataset_job(payload: dict[str, Any]) -> DatasetJob:
    required = {"job_id", "dataset_id", "graph_version", "graph_semantics", "status", "created_at", "updated_at"}
    if not required.issubset(payload):
        raise DemoApiError("Response dataset job thiếu trường bắt buộc")
    return DatasetJob(
        job_id=str(payload["job_id"]),
        dataset_id=str(payload["dataset_id"]),
        graph_version=str(payload["graph_version"]),
        graph_semantics=str(payload["graph_semantics"]),
        status=str(payload["status"]),
        created_at=str(payload["created_at"]),
        updated_at=str(payload["updated_at"]),
        error_code=str(payload["error_code"]) if payload.get("error_code") else None,
    )


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Backend trả lỗi HTTP {response.status_code}"
    detail = payload.get("detail") if isinstance(payload, dict) else None
    return str(detail) if detail else f"Backend trả lỗi HTTP {response.status_code}"
