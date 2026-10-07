"""Reproducible synthetic latency and memory smoke benchmark for the graph index."""

from __future__ import annotations

import json
import platform
import random
import sys
import time
import tracemalloc
from pathlib import Path

import torch

# Make this standalone script runnable from the repository root on all OSes.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.graph import GraphView
from src.retrieval import retrieve_two_hop_candidates
from src.serving import ServingGraphIndex


def _percentile(values: list[float], percentile: float) -> float:
    """Return a deterministic nearest-rank percentile for a non-empty sample."""
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile)))
    return ordered[rank]


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "min": round(min(values), 3),
        "mean": round(sum(values) / len(values), 3),
        "p50": round(_percentile(values, 0.50), 3),
        "p95": round(_percentile(values, 0.95), 3),
        "p99": round(_percentile(values, 0.99), 3),
        "max": round(max(values), 3),
    }


def main() -> None:
    seed, nodes, edges, queries = 42, 1_000, 5_000, 100
    rng = random.Random(seed)
    pairs = {(rng.randrange(nodes), rng.randrange(nodes)) for _ in range(edges)}
    edge_index = torch.tensor(sorted(pairs), dtype=torch.long).t().contiguous()
    tracemalloc.start()
    start = time.perf_counter()
    index = ServingGraphIndex.from_graph_view(
        GraphView(torch.arange(nodes), edge_index, directed=True)
    )
    build_ms = (time.perf_counter() - start) * 1_000
    candidate_counts: list[float] = []
    query_latencies_ms: list[float] = []
    for node in range(queries):
        start = time.perf_counter()
        candidate_counts.append(float(len(retrieve_two_hop_candidates(node, index))))
        query_latencies_ms.append((time.perf_counter() - start) * 1_000)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    output = {
        "benchmark": "sprint2_part1_graph_index",
        "config": {
            "seed": seed,
            "graph_semantics": "directed",
            "dataset_identifier": "synthetic_uniform_directed",
            "requested_nodes": nodes,
            "requested_edge_draws": edges,
            "query_count": queries,
            "retrieval": "exact_unbounded_two_hop",
        },
        "index": {
            "node_count": index.num_nodes(),
            "edge_count": index.num_edges(),
            "index_build_ms": round(build_ms, 3),
            "peak_tracemalloc_bytes": peak_bytes,
        },
        "latency_ms": _summary(query_latencies_ms),
        "candidate_count": _summary(candidate_counts),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "torch": torch.__version__,
        },
    }
    path = Path("artifacts/sprint2/part1/graph_index_benchmark.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
