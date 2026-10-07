"""Reproducible Phase 02 benchmark with retrieval/scoring/Top-M timings."""

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
from src.ranking import RankingConfig, score_topology_candidates, select_top_m
from src.retrieval import RetrievalConfig, retrieve_bounded_two_hop_candidates
from src.serving import ServingGraphIndex


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * percentile)]


def main() -> None:
    seed, nodes, edge_draws, query_count = 42, 1_000, 5_000, 100
    retrieval_config = RetrievalConfig(first_hop_cap=4, second_hop_cap=8, candidate_cap=16)
    ranking_config = RankingConfig("aa", top_m=10)
    rng = random.Random(seed)
    edges = {(rng.randrange(nodes), rng.randrange(nodes)) for _ in range(edge_draws)}
    edge_index = torch.tensor(sorted(edges), dtype=torch.long).t().contiguous()
    graph = ServingGraphIndex.from_graph_view(GraphView(torch.arange(nodes), edge_index, directed=True))

    queries: list[dict[str, float | int | bool]] = []
    for user_id in range(query_count):
        start = time.perf_counter()
        retrieved = retrieve_bounded_two_hop_candidates(user_id, graph, retrieval_config)
        retrieval_ms = (time.perf_counter() - start) * 1_000
        start = time.perf_counter()
        all_scores = score_topology_candidates(user_id, retrieved.candidate_ids, graph)
        scoring_ms = (time.perf_counter() - start) * 1_000
        start = time.perf_counter()
        select_top_m(
            {candidate: score.value_for(ranking_config.ranking_method) for candidate, score in all_scores.items()},
            ranking_config.top_m,
        )
        topk_ms = (time.perf_counter() - start) * 1_000
        queries.append({"query_degree": graph.degree(user_id), "candidates_returned": retrieved.stats.candidates_returned, "truncated": retrieved.stats.truncated, "retrieval_ms": retrieval_ms, "scoring_ms": scoring_ms, "topk_ms": topk_ms, "total_ms": retrieval_ms + scoring_ms + topk_ms})

    output = {"benchmark": "sprint2_phase02_fused_ranking", "config": {"seed": seed, "dataset_identifier": "synthetic_uniform_directed", "graph_semantics": "directed", "nodes": nodes, "unique_directed_edges": graph.num_edges(), "query_count": query_count, "retrieval": retrieval_config.__dict__, "ranking": ranking_config.__dict__}, "latency_ms": {name: {"p50": round(_percentile([float(query[name]) for query in queries], 0.50), 3), "p95": round(_percentile([float(query[name]) for query in queries], 0.95), 3), "p99": round(_percentile([float(query[name]) for query in queries], 0.99), 3)} for name in ("retrieval_ms", "scoring_ms", "topk_ms", "total_ms")}, "queries": queries, "environment": {"python": platform.python_version(), "platform": platform.platform(), "torch": torch.__version__}}
    output_path = Path("artifacts/sprint2/phase02/fused_ranking_benchmark.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output["latency_ms"], indent=2))


if __name__ == "__main__":
    main()
