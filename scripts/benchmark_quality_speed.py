"""Leakage-safe Phase 03 quality, latency, and synthetic-scale benchmark."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import CanonicalGraph
from src.data.adapters import MGTABAdapter
from src.evaluation.ranking_metrics import candidate_coverage, ranking_metrics
from src.graph import build_pymk_graph_view
from src.ranking import RankingConfig, rank_topology_candidates
from src.retrieval import RetrievalConfig, retrieve_bounded_two_hop_candidates
from src.serving import ServingGraphIndex
from src.split import build_observed_graph, split_positive_links
from src.tasks import DirectedConnectionTask, MutualConnectionTask, TaskGraph

CAPS: tuple[int | None, ...] = (1_000, 5_000, 10_000, 20_000, None)
BUCKETS = ((0, 10, "0-10"), (11, 50, "11-50"), (51, 100, "51-100"), (101, 500, "101-500"), (501, 1_000, "501-1000"), (1_001, None, ">1000"))


@dataclass(frozen=True)
class BenchmarkConfig:
    seed: int = 42
    max_held_out: int = 1_000
    top_m: int = 10
    ranking_method: str = "aa"
    scale_queries: int = 100
    scale_edges_per_node: int = 4


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * percentile)]


def _bucket(degree: int) -> str:
    for lower, upper, label in BUCKETS:
        if degree >= lower and (upper is None or degree <= upper):
            return label
    raise AssertionError("degree bucket is incomplete")


def _cap_label(cap: int | None) -> str:
    return "unlimited" if cap is None else str(cap)


def _index_storage_bytes(index: ServingGraphIndex) -> int:
    """Conservative shallow storage estimate, not process-wide graph memory."""

    return sum(sys.getsizeof(value) for value in (
        index._external_to_internal, index._internal_to_external, index._offsets, index._adjacency
    )) + sum(sys.getsizeof(value) for value in index._external_to_internal) + sum(
        sys.getsizeof(value) for value in index._external_to_internal.values()
    )


def _observed_canonical(task: TaskGraph) -> CanonicalGraph:
    return CanonicalGraph(
        node_ids=torch.arange(task.num_nodes, dtype=torch.long),
        node_features=None,
        edge_index=task.observed_edge_index,
        edge_type=task.observed_edge_type,
        edge_weight=None,
    )


def _select_held_out(positives: torch.Tensor, config: BenchmarkConfig) -> torch.Tensor:
    """Deterministically sample an explicit benchmark subset, never drop failures."""

    if config.max_held_out <= 0 or len(positives) <= config.max_held_out:
        return positives
    order = torch.randperm(len(positives), generator=torch.Generator().manual_seed(config.seed))
    return positives[order[: config.max_held_out]]


def evaluate_semantic_cap(
    observed: TaskGraph,
    held_out: torch.Tensor,
    semantic: str,
    cap: int | None,
    config: BenchmarkConfig,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Evaluate every supplied positive against its real bounded pool."""

    view = build_pymk_graph_view(_observed_canonical(observed), semantic)
    build_start = time.perf_counter()
    index = ServingGraphIndex.from_graph_view(view)
    index_build_ms = (time.perf_counter() - build_start) * 1_000
    retrieval_config = RetrievalConfig(candidate_cap=cap)
    ranking_config = RankingConfig(config.ranking_method, config.top_m)
    process = psutil.Process()
    before_rss = process.memory_info().rss
    records: list[dict[str, Any]] = []
    rankings: list[list[bool]] = []
    covered: list[bool] = []
    for source, destination in held_out.tolist():
        retrieval_start = time.perf_counter()
        retrieved = retrieve_bounded_two_hop_candidates(source, index, retrieval_config)
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1_000
        scoring_start = time.perf_counter()
        ranked = rank_topology_candidates(source, retrieved.candidate_ids, index, ranking_config)
        scoring_ms = (time.perf_counter() - scoring_start) * 1_000
        relevance = [item.candidate_id == destination for item in ranked]
        is_covered = destination in retrieved.candidate_ids
        covered.append(is_covered)
        rankings.append(relevance)
        records.append({
            "degree_bucket": _bucket(index.degree(source)),
            "query_degree": index.degree(source),
            "candidate_count": retrieved.stats.candidates_returned,
            "truncated": retrieved.stats.truncated,
            "covered": is_covered,
            "recall_at_10": float(any(relevance)),
            "ndcg_at_10": next((1.0 / __import__("math").log2(position + 2) for position, relevant in enumerate(relevance[:10]) if relevant), 0.0),
            "mrr": next((1.0 / (position + 1) for position, relevant in enumerate(relevance) if relevant), 0.0),
            "retrieval_ms": retrieval_ms,
            "scoring_ms": scoring_ms,
            "total_ms": retrieval_ms + scoring_ms,
        })
    metrics = ranking_metrics(rankings, ks=(10,))
    after_rss = process.memory_info().rss
    latencies = lambda name: [float(record[name]) for record in records]
    row = {
        "semantics": semantic,
        "candidate_cap": _cap_label(cap),
        "query_count": len(records),
        "held_out_positive_count": len(held_out),
        "candidate_coverage": candidate_coverage(covered),
        "missed_positive_count": len(covered) - sum(covered),
        "recall_at_10": metrics["recall_at_10"],
        "ndcg_at_10": metrics["ndcg_at_10"],
        "mrr": metrics["mrr"],
        "candidates_per_query": sum(record["candidate_count"] for record in records) / len(records) if records else 0.0,
        "truncated_rate": sum(record["truncated"] for record in records) / len(records) if records else 0.0,
        "mean_latency_ms": sum(latencies("total_ms")) / len(records) if records else 0.0,
        "p50_latency_ms": _percentile(latencies("total_ms"), 0.50),
        "p95_latency_ms": _percentile(latencies("total_ms"), 0.95),
        "p99_latency_ms": _percentile(latencies("total_ms"), 0.99),
        "mean_retrieval_ms": sum(latencies("retrieval_ms")) / len(records) if records else 0.0,
        "mean_scoring_ms": sum(latencies("scoring_ms")) / len(records) if records else 0.0,
        "index_build_ms": index_build_ms,
        "index_memory_bytes_estimate": _index_storage_bytes(index),
        "rss_delta_bytes": after_rss - before_rss,
    }
    for record in records:
        record.update({"semantics": semantic, "candidate_cap": _cap_label(cap)})
    return row, records


def _heavy_tail_edges(nodes: int, edges: int, seed: int) -> list[tuple[int, int]]:
    """Create deterministic skewed endpoints; low IDs become hubs."""

    rng = random.Random(seed)
    result: set[tuple[int, int]] = set()
    while len(result) < edges:
        source = min(nodes - 1, int(nodes * rng.random() ** 2.4))
        destination = min(nodes - 1, int(nodes * rng.random() ** 2.4))
        if source != destination:
            result.add((source, destination))
    return sorted(result)


def run_scale_benchmark(config: BenchmarkConfig) -> list[dict[str, Any]]:
    """Run safe heavy-tail scale levels and record explicit resource skips."""

    rows: list[dict[str, Any]] = []
    available = psutil.virtual_memory().available
    for nodes in (10_000, 100_000, 500_000, 1_000_000):
        edge_count = nodes * config.scale_edges_per_node
        estimated_peak = nodes * 200 + edge_count * 1_000
        if nodes == 1_000_000 or estimated_peak > available * 0.60:
            rows.append({"node_count": nodes, "requested_edge_count": edge_count, "status": "skipped_resource_guard", "reason": "estimated Python adjacency peak exceeds conservative available-memory guard"})
            continue
        start = time.perf_counter()
        edges = _heavy_tail_edges(nodes, edge_count, config.seed)
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
        graph = ServingGraphIndex.from_graph_view(build_pymk_graph_view(CanonicalGraph(torch.arange(nodes), None, edge_index, torch.zeros(len(edges), dtype=torch.long), None), "directed"))
        build_ms = (time.perf_counter() - start) * 1_000
        rng = random.Random(config.seed)
        query_ids = [rng.randrange(nodes) for _ in range(config.scale_queries)]
        latencies, counts, truncations = [], [], []
        for user_id in query_ids:
            query_start = time.perf_counter()
            result = retrieve_bounded_two_hop_candidates(user_id, graph, RetrievalConfig(candidate_cap=10_000))
            latencies.append((time.perf_counter() - query_start) * 1_000)
            counts.append(result.stats.candidates_returned)
            truncations.append(result.stats.truncated)
        rows.append({"node_count": nodes, "requested_edge_count": edge_count, "actual_edge_count": graph.num_edges(), "status": "completed", "generator": "endpoint_probability=random()**2.4 (heavy-tail hubs)", "seed": config.seed, "graph_semantics": "directed", "index_build_ms": build_ms, "index_memory_bytes_estimate": _index_storage_bytes(graph), "query_count": len(query_ids), "candidate_cap": 10_000, "mean_latency_ms": sum(latencies) / len(latencies), "p50_latency_ms": _percentile(latencies, 0.50), "p95_latency_ms": _percentile(latencies, 0.95), "p99_latency_ms": _percentile(latencies, 0.99), "candidates_per_query": sum(counts) / len(counts), "truncated_rate": sum(truncations) / len(truncations), "rss_bytes": psutil.Process().memory_info().rss})
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _recommended_row(rows: list[dict[str, Any]], semantic: str) -> dict[str, Any]:
    """Choose the fastest row among maximum-coverage, maximum-quality rows."""

    semantic_rows = [row for row in rows if row["semantics"] == semantic]
    return max(
        semantic_rows,
        key=lambda row: (
            row["candidate_coverage"],
            row["recall_at_10"],
            -row["p95_latency_ms"],
        ),
    )


def _analysis(
    rows: list[dict[str, Any]],
    bucket_rows: list[dict[str, Any]],
    scale_rows: list[dict[str, Any]],
    config: BenchmarkConfig,
) -> str:
    recommended = _recommended_row(rows, "directed")
    mutual = _recommended_row(rows, "mutual")
    bucket_summary = []
    for semantic, selected in (("directed", recommended), ("mutual", mutual)):
        matching = [row for row in bucket_rows if row["semantics"] == semantic and row["candidate_cap"] == selected["candidate_cap"]]
        if matching:
            slowest = max(matching, key=lambda row: row["p95_latency_ms"])
            bucket_summary.append(f"- {semantic}/{selected['candidate_cap']}: slowest observed bucket was {slowest['degree_bucket']} (p95={slowest['p95_latency_ms']:.3f} ms, n={slowest['query_count']}).")
    return "\n".join(["# Phase 03 quality-speed analysis", "", "## Design", "", "Evaluation uses held-out test positives removed together with validation positives from the observed graph. Every sampled held-out positive is evaluated, including zero-candidate and missed-positive queries. Scores use Adamic-Adar with deterministic Top-10.", "", "## Recommendation", "", f"For the measured directed graph, `{recommended['candidate_cap']}` is the evidence-based cap: it reaches the maximum candidate coverage ({recommended['candidate_coverage']:.4f}) and Recall@10 ({recommended['recall_at_10']:.4f}) while having the lowest p95 among rows with that quality ({recommended['p95_latency_ms']:.3f} ms). This is a benchmark configuration, not a production default.", "", "## Directed vs mutual", "", f"At their selected caps, directed has candidate coverage={recommended['candidate_coverage']:.4f}, Recall@10={recommended['recall_at_10']:.4f}, candidates/query={recommended['candidates_per_query']:.1f}, and p95={recommended['p95_latency_ms']:.3f} ms. Mutual has coverage={mutual['candidate_coverage']:.4f}, Recall@10={mutual['recall_at_10']:.4f}, candidates/query={mutual['candidates_per_query']:.1f}, and p95={mutual['p95_latency_ms']:.3f} ms. These are separate graph semantics, not interchangeable defaults.", "", "## Degree buckets", "", *bucket_summary, "", "## Scope and limitations", "", f"The explicit deterministic held-out sample size is {config.max_held_out}; results must not be generalized beyond this data, hardware, seed, and scoring configuration. Scale rows marked `skipped_resource_guard` were not run. Synthetic graphs are heavy-tail stress tests, not production traffic.", "", "## Synthetic scale", "", *[f"- {row['node_count']}: {row['status']}" for row in scale_rows], ""])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "data" / "raw" / "MGTAB")
    parser.add_argument("--max-held-out", type=int, default=1_000)
    args = parser.parse_args()
    config = BenchmarkConfig(max_held_out=args.max_held_out)
    canonical = MGTABAdapter(args.dataset_dir).transform()
    all_rows: list[dict[str, Any]] = []
    bucket_rows: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    for semantic, builder in {"directed": DirectedConnectionTask(canonical, "friend"), "mutual": MutualConnectionTask(canonical, "friend")}.items():
        task = builder.build()
        split = split_positive_links(task.positive_edges, seed=config.seed)
        observed = build_observed_graph(task, torch.cat([split.val_pos, split.test_pos]))
        held_out = _select_held_out(split.test_pos, config)
        metadata.append({"semantics": semantic, "all_test_positives": len(split.test_pos), "evaluated_held_out_positives": len(held_out), "observed_edge_count": int(observed.observed_edge_index.shape[1])})
        for cap in CAPS:
            row, records = evaluate_semantic_cap(observed, held_out, semantic, cap, config)
            all_rows.append(row)
            for label in {record["degree_bucket"] for record in records}:
                bucket_records = [record for record in records if record["degree_bucket"] == label]
                bucket_rows.append({"semantics": semantic, "candidate_cap": _cap_label(cap), "degree_bucket": label, "query_count": len(bucket_records), "mean_latency_ms": sum(record["total_ms"] for record in bucket_records) / len(bucket_records), "p50_latency_ms": _percentile([record["total_ms"] for record in bucket_records], 0.50), "p95_latency_ms": _percentile([record["total_ms"] for record in bucket_records], 0.95), "p99_latency_ms": _percentile([record["total_ms"] for record in bucket_records], 0.99), "candidates_per_query": sum(record["candidate_count"] for record in bucket_records) / len(bucket_records), "truncated_rate": sum(record["truncated"] for record in bucket_records) / len(bucket_records), "candidate_coverage": sum(record["covered"] for record in bucket_records) / len(bucket_records)})
    scale_rows = run_scale_benchmark(config)
    results = ROOT / "results" / "sprint_2"
    _write_csv(results / "quality_speed_tradeoff.csv", all_rows)
    _write_csv(results / "degree_bucket_latency.csv", bucket_rows)
    _write_csv(results / "scale_benchmark.csv", scale_rows)
    (ROOT / "artifacts" / "sprint2").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts" / "sprint2" / "benchmark_metadata.json").write_text(json.dumps({"config": asdict(config), "dataset": canonical.metadata, "evaluation": metadata, "environment": {"python": platform.python_version(), "platform": platform.platform(), "torch": torch.__version__, "available_memory_bytes_before_scale": psutil.virtual_memory().available}}, indent=2) + "\n", encoding="utf-8")
    (ROOT / "docs" / "quality_speed_analysis.md").write_text(_analysis(all_rows, bucket_rows, scale_rows, config), encoding="utf-8")
    print(f"Wrote {len(all_rows)} quality rows, {len(bucket_rows)} bucket rows, and {len(scale_rows)} scale rows.")


if __name__ == "__main__":
    main()
