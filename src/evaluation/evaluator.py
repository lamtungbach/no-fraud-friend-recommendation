"""Reusable evaluator for classical scorers over a leakage-safe TaskGraph."""

from __future__ import annotations

import random
from statistics import median
from time import perf_counter

import torch

from src.candidates import TwoHopCandidateGenerator
from src.sampling.negative_sampling import canonical_pair
from src.tasks.base_link_task import TaskGraph
from .binary_metrics import binary_metrics
from .ranking_metrics import candidate_coverage, ranking_metrics


class ClassicalEvaluator:
    def __init__(self, observed_graph: TaskGraph, all_known_positives: torch.Tensor, seed: int = 42, ks: tuple[int, ...] = (5, 10, 20)):
        self.observed_graph = observed_graph
        self.seed = seed
        self.ks = ks
        self.known = {canonical_pair(int(u), int(v), observed_graph.directed) for u, v in all_known_positives.tolist()}
        self.generator = TwoHopCandidateGenerator(observed_graph)
        self._candidate_cache: dict[int, set[int]] = {}

    def _candidate_pool(self, source: int) -> set[int]:
        if source not in self._candidate_cache:
            self._candidate_cache[source] = self.generator.generate(source)
        return self._candidate_cache[source]

    def evaluate_binary(self, scorer, positives: torch.Tensor, negatives: torch.Tensor) -> dict:
        start = perf_counter()
        result = binary_metrics(scorer.score_pairs(positives.tolist()), scorer.score_pairs(negatives.tolist()))
        result["binary_runtime_seconds"] = perf_counter() - start
        return result

    def evaluate_ranking(self, scorer, positives: torch.Tensor, negative_mode: str, negatives_per_query: int = 100) -> dict:
        if negative_mode not in {"random", "hard"}:
            raise ValueError("negative_mode must be random or hard")
        start = perf_counter()
        rng = random.Random(self.seed)
        coverage_flags: list[bool] = []
        candidate_sizes: list[int] = []
        rankings: list[list[bool]] = []
        oriented = positives.tolist()
        if not self.observed_graph.directed:
            oriented = [pair for u, v in oriented for pair in ((u, v), (v, u))]
        for source, target in oriented:
            pool = self._candidate_pool(int(source))
            covered = int(target) in pool
            coverage_flags.append(covered)
            candidate_sizes.append(len(pool))
            if not covered:
                continue
            if negative_mode == "hard":
                choices = [node for node in pool if canonical_pair(int(source), int(node), self.observed_graph.directed) not in self.known and node != target]
            else:
                choices = [node for node in range(self.observed_graph.num_nodes) if node != source and node != target and canonical_pair(int(source), node, self.observed_graph.directed) not in self.known]
            rng.shuffle(choices)
            candidates = [int(target)] + choices[:negatives_per_query]
            scored = sorted(((scorer.score(int(source), node), node == target) for node in candidates), key=lambda row: row[0], reverse=True)
            rankings.append([relevant for _, relevant in scored])
        result = ranking_metrics(rankings, self.ks)
        result.update({
            "candidate_coverage": candidate_coverage(coverage_flags),
            "avg_candidates": sum(candidate_sizes) / len(candidate_sizes) if candidate_sizes else 0.0,
            "median_candidates": float(median(candidate_sizes)) if candidate_sizes else 0.0,
            "ranking_runtime_seconds": perf_counter() - start,
        })
        return result
