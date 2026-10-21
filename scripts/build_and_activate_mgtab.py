"""Submit a real MGTAB Phase 08 job to a running local API and poll its state."""

from __future__ import annotations

import argparse
import sys
import time

import httpx


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--graph-version", default=None)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    api_url = args.api_url.rstrip("/")
    payload: dict[str, object] = {"dataset_id": "mgtab"}
    if args.graph_version:
        payload["graph_version"] = args.graph_version
    try:
        with httpx.Client(timeout=15.0) as client:
            created = client.post(f"{api_url}/datasets/jobs", json=payload)
            created.raise_for_status()
            job = created.json()
            job_id = job["job_id"]
            print(f"MGTAB job accepted: {job_id} ({job['graph_version']})")
            deadline = time.monotonic() + args.timeout_seconds
            while time.monotonic() < deadline:
                response = client.get(f"{api_url}/datasets/jobs/{job_id}")
                response.raise_for_status()
                job = response.json()
                print(f"status={job['status']} updated_at={job['updated_at']}")
                if job["status"] == "READY":
                    print(f"Activated graph version: {job['graph_version']}")
                    return 0
                if job["status"] == "FAILED":
                    print(f"Job failed safely: {job.get('error_code') or 'unknown'}", file=sys.stderr)
                    return 1
                time.sleep(args.poll_seconds)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        print(f"Could not run MGTAB job: {type(error).__name__}", file=sys.stderr)
        return 2
    print("Timed out waiting for MGTAB job", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
