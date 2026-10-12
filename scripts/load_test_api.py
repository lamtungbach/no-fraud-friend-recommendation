"""Repeatable, lightweight HTTP load smoke for the Phase 07 endpoint.

This is deliberately not a production capacity benchmark. It records a fixed
request count, bounded concurrency, latency percentiles, error rate and the
observed raw-cache mix against an already-running local service.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class RequestOutcome:
    latency_seconds: float
    status_code: int | None
    raw_cache_hit: bool | None


def _request(url: str, user_id: int, top_k: int, timeout: float) -> RequestOutcome:
    body = json.dumps({"user_id": user_id, "top_k": top_k}).encode()
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - URL is explicit CLI input.
            payload = json.loads(response.read())
            return RequestOutcome(
                time.perf_counter() - started,
                response.status,
                payload.get("raw_cache_hit") if isinstance(payload, dict) else None,
            )
    except HTTPError as error:
        return RequestOutcome(time.perf_counter() - started, error.code, None)
    except (OSError, URLError, ValueError):
        return RequestOutcome(time.perf_counter() - started, None, None)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((percentile / 100) * (len(ordered) - 1)))
    return ordered[index]


def run_load_smoke(
    *, url: str, user_id: int, top_k: int, request_count: int, concurrency: int, timeout: float
) -> dict[str, object]:
    if request_count < 1 or concurrency < 1 or timeout <= 0:
        raise ValueError("request_count, concurrency and timeout must be positive")
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        outcomes = list(
            executor.map(lambda _: _request(url, user_id, top_k, timeout), range(request_count))
        )
    latencies = [outcome.latency_seconds for outcome in outcomes]
    successes = [outcome for outcome in outcomes if outcome.status_code == 200]
    cache_hits = sum(outcome.raw_cache_hit is True for outcome in successes)
    return {
        "kind": "phase07_load_smoke_not_production_capacity_test",
        "url": url,
        "request_count": request_count,
        "concurrency": concurrency,
        "success_count": len(successes),
        "error_rate": (request_count - len(successes)) / request_count,
        "raw_cache_hits": cache_hits,
        "raw_cache_misses": sum(outcome.raw_cache_hit is False for outcome in successes),
        "latency_seconds": {
            "mean": statistics.fmean(latencies),
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "p99": _percentile(latencies, 99),
        },
        "status_codes": {
            str(code): sum(outcome.status_code == code for outcome in outcomes)
            for code in sorted({outcome.status_code for outcome in outcomes}, key=str)
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1/recommendations")
    parser.add_argument("--user-id", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_load_smoke(
        url=args.url,
        user_id=args.user_id,
        top_k=args.top_k,
        request_count=args.requests,
        concurrency=args.concurrency,
        timeout=args.timeout,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
