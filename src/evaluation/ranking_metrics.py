"""Candidate-pool ranking metrics."""

from __future__ import annotations

import math


def candidate_coverage(hidden_positive_in_pool: list[bool]) -> float:
    return sum(hidden_positive_in_pool) / len(hidden_positive_in_pool) if hidden_positive_in_pool else 0.0


def ranking_metrics(rankings: list[list[bool]], ks: tuple[int, ...] = (5, 10, 20)) -> dict[str, float]:
    """Evaluate only supplied query rankings; each has at least one hidden target."""
    count = len(rankings)
    result = {"num_queries": count, "mrr": 0.0}
    for k in ks:
        result.update({
            f"precision_at_{k}": 0.0,
            f"recall_at_{k}": 0.0,
            f"hits_at_{k}": 0.0,
            f"ndcg_at_{k}": 0.0,
        })
    if not count:
        return result
    for relevance in rankings:
        first_rank = next((index + 1 for index, relevant in enumerate(relevance) if relevant), None)
        if first_rank is not None:
            result["mrr"] += 1.0 / first_rank
        positives = sum(relevance)
        for k in ks:
            hits = sum(relevance[:k])
            result[f"precision_at_{k}"] += hits / k
            result[f"recall_at_{k}"] += hits / positives if positives else 0.0
            result[f"hits_at_{k}"] += float(hits > 0)
            dcg = sum(relevant / math.log2(index + 2) for index, relevant in enumerate(relevance[:k]))
            ideal_hits = min(positives, k)
            ideal_dcg = sum(1.0 / math.log2(index + 2) for index in range(ideal_hits))
            result[f"ndcg_at_{k}"] += dcg / ideal_dcg if ideal_dcg else 0.0
    for key in result:
        if key not in {"num_queries"}:
            result[key] /= count
    return result
