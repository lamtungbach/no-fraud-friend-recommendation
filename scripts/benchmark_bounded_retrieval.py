"""Reproducible microbenchmark for bounded two-hop candidate retrieval."""

from __future__ import annotations

import json
import platform
import random
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.graph import GraphView
from src.retrieval import RetrievalConfig, retrieve_bounded_two_hop_candidates
from src.serving import ServingGraphIndex


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * percentile)]


def main() -> None:
    seed, nodes, edge_draws, query_count = 42, 1_000, 5_000, 100
    # Intentionally conservative demonstration caps; Phase 03 will evaluate a
    # quality/speed grid rather than selecting a production value here.
    config = RetrievalConfig(first_hop_cap=4, second_hop_cap=8, candidate_cap=16)
    rng = random.Random(seed)
    edges = {(rng.randrange(nodes), rng.randrange(nodes)) for _ in range(edge_draws)}
    edge_index = torch.tensor(sorted(edges), dtype=torch.long).t().contiguous()
    graph = ServingGraphIndex.from_graph_view(
        GraphView(torch.arange(nodes), edge_index, directed=True)
    )

    records: list[dict[str, int | bool | float]] = []
    for user_id in range(query_count):
        start = time.perf_counter()
        result = retrieve_bounded_two_hop_candidates(user_id, graph, config)
        latency_ms = (time.perf_counter() - start) * 1_000
        records.append(
            {
                "query_degree": graph.degree(user_id),
                "candidates_returned": result.stats.candidates_returned,
                "truncated": result.stats.truncated,
                "latency_ms": latency_ms,
            }
        )

    latencies = [float(record["latency_ms"]) for record in records]
    output = {
        "benchmark": "sprint2_phase01_bounded_retrieval",
        "config": {
            "seed": seed,
            "dataset_identifier": "synthetic_uniform_directed",
            "graph_semantics": "directed",
            "nodes": nodes,
            "unique_directed_edges": graph.num_edges(),
            "query_count": query_count,
            "first_hop_cap": config.first_hop_cap,
            "second_hop_cap": config.second_hop_cap,
            "candidate_cap": config.candidate_cap,
            "strategy": config.strategy,
            "retrieval_seed": config.seed,
        },
        "latency_ms": {
            "p50": round(_percentile(latencies, 0.50), 3),
            "p95": round(_percentile(latencies, 0.95), 3),
            "p99": round(_percentile(latencies, 0.99), 3),
        },
        "queries": records,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "torch": torch.__version__,
        },
    }
    output_path = Path("artifacts/sprint2/phase01/bounded_retrieval_benchmark.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
