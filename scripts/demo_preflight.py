"""Read-only preflight for the local Safe Top-K demonstration.

Run this after FastAPI starts and before opening Streamlit. It deliberately
does not create a dataset job, touch Redis/PostgreSQL, or alter the registry.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class PreflightError(RuntimeError):
    """A demo prerequisite is not satisfied."""


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 -- explicit local demo URL
            parsed = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise PreflightError(f"{method} {url} returned HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise PreflightError(f"{method} {url} failed: {error}") from error
    if not isinstance(parsed, dict):
        raise PreflightError(f"{method} {url} did not return a JSON object")
    return parsed


def validate_live(payload: dict[str, Any]) -> None:
    if payload != {"status": "live"}:
        raise PreflightError("/health/live did not report status=live")


def validate_ready(payload: dict[str, Any]) -> tuple[str, int]:
    if payload.get("status") != "ready":
        raise PreflightError(f"/health/ready is not ready: {payload.get('reasons', [])}")
    graph_version = payload.get("graph_version")
    max_top_k = payload.get("max_top_k")
    if not isinstance(graph_version, str) or not graph_version:
        raise PreflightError("/health/ready did not expose an active graph version")
    if not isinstance(max_top_k, int) or max_top_k < 1:
        raise PreflightError("/health/ready did not expose a valid max_top_k")
    return graph_version, max_top_k


def validate_recommendation(
    payload: dict[str, Any], *, graph_version: str, top_k: int
) -> int:
    required = {
        "user_id",
        "recommendations",
        "graph_version",
        "trust_version",
        "trust_policy_version",
        "raw_cache_hit",
    }
    if not required.issubset(payload) or "raw_candidates" in payload:
        raise PreflightError("recommendation response is missing Safe Top-K fields or exposes raw candidates")
    if payload["graph_version"] != graph_version:
        raise PreflightError("recommendation graph version does not match readiness")
    recommendations = payload["recommendations"]
    if not isinstance(recommendations, list) or len(recommendations) > top_k:
        raise PreflightError("recommendation list has an invalid size")
    for item in recommendations:
        if not isinstance(item, dict) or item.get("eligibility") != "ELIGIBLE":
            raise PreflightError("recommendation response contains a non-safe item")
        if not isinstance(item.get("candidate_id"), int) or not isinstance(item.get("rank"), int):
            raise PreflightError("recommendation response contains an invalid item")
        if "raw_candidates" in item:
            raise PreflightError("recommendation item exposes raw candidates")
    return len(recommendations)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the local Safe Top-K demo without changing state.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--user-id", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    if args.user_id < 0 or args.top_k < 1 or args.timeout <= 0:
        parser.error("--user-id must be non-negative; --top-k and --timeout must be positive")

    api_url = args.api_url.rstrip("/")
    try:
        validate_live(request_json(f"{api_url}/health/live", timeout=args.timeout))
        graph_version, max_top_k = validate_ready(
            request_json(f"{api_url}/health/ready", timeout=args.timeout)
        )
        if args.top_k > max_top_k:
            raise PreflightError(f"requested top_k={args.top_k} exceeds backend max_top_k={max_top_k}")
        result = request_json(
            f"{api_url}/v1/recommendations",
            method="POST",
            payload={"user_id": args.user_id, "top_k": args.top_k},
            timeout=args.timeout,
        )
        count = validate_recommendation(result, graph_version=graph_version, top_k=args.top_k)
    except PreflightError as error:
        print(f"DEMO PREFLIGHT FAILED: {error}", file=sys.stderr)
        return 1

    print(f"DEMO PREFLIGHT PASSED: graph={graph_version}; safe_recommendations={count}; max_top_k={max_top_k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
