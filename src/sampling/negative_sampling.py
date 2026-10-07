"""Negative samplers that exclude every known positive, including hidden links."""

from __future__ import annotations

from dataclasses import dataclass
import random

import torch
from torch import Tensor

from src.candidates import TwoHopCandidateGenerator
from src.tasks.base_link_task import TaskGraph


def canonical_pair(u: int, v: int, directed: bool) -> tuple[int, int]:
    return (u, v) if directed else (min(u, v), max(u, v))


def _positive_set(pairs: Tensor | set[tuple[int, int]], directed: bool) -> set[tuple[int, int]]:
    iterable = pairs if isinstance(pairs, set) else pairs.tolist()
    return {canonical_pair(int(u), int(v), directed) for u, v in iterable}


def sample_random_negatives(num_nodes: int, all_known_positive_pairs: Tensor | set[tuple[int, int]], directed: bool, num_negatives: int, seed: int = 42) -> Tensor:
    positives = _positive_set(all_known_positive_pairs, directed)
    available = num_nodes * (num_nodes - 1) if directed else num_nodes * (num_nodes - 1) // 2
    if num_negatives > available - len(positives):
        raise ValueError("Requested more random negatives than available non-positive pairs")
    # This is seeded experiment sampling, not cryptographic randomness.
    rng = random.Random(seed)  # nosec B311
    negatives: set[tuple[int, int]] = set()
    while len(negatives) < num_negatives:
        u, v = rng.randrange(num_nodes), rng.randrange(num_nodes)
        if u == v:
            continue
        pair = canonical_pair(u, v, directed)
        if pair not in positives:
            negatives.add(pair)
    return torch.tensor(sorted(negatives), dtype=torch.long)


@dataclass
class HardNegativeSample:
    pairs: Tensor
    sources_without_enough_candidates: int
    fallback_count: int


def sample_hard_negatives(observed_graph: TaskGraph, positives: Tensor, all_known_positive_pairs: Tensor | set[tuple[int, int]], candidate_generator: TwoHopCandidateGenerator, num_negatives_per_positive: int = 1, seed: int = 42, fallback: str = "skip") -> HardNegativeSample:
    if fallback not in {"skip", "random"}:
        raise ValueError("fallback must be 'skip' or 'random'")
    known = _positive_set(all_known_positive_pairs, observed_graph.directed)
    # This is seeded experiment sampling, not cryptographic randomness.
    rng = random.Random(seed)  # nosec B311
    negatives: set[tuple[int, int]] = set()
    missing_sources = 0
    fallback_count = 0
    for u, _ in positives.tolist():
        pool = [v for v in candidate_generator.generate(int(u)) if canonical_pair(int(u), int(v), observed_graph.directed) not in known and canonical_pair(int(u), int(v), observed_graph.directed) not in negatives]
        rng.shuffle(pool)
        selected = pool[:num_negatives_per_positive]
        if len(selected) < num_negatives_per_positive:
            missing_sources += 1
            if fallback == "random":
                choices = [v for v in range(observed_graph.num_nodes) if v != u and canonical_pair(int(u), v, observed_graph.directed) not in known and canonical_pair(int(u), v, observed_graph.directed) not in negatives]
                rng.shuffle(choices)
                extra = choices[:num_negatives_per_positive - len(selected)]
                selected.extend(extra)
                fallback_count += len(extra)
        for v in selected:
            negatives.add(canonical_pair(int(u), int(v), observed_graph.directed))
    pairs = torch.tensor(sorted(negatives), dtype=torch.long) if negatives else torch.empty((0, 2), dtype=torch.long)
    return HardNegativeSample(pairs, missing_sources, fallback_count)
