"""Fused topology scoring over already retrieved PYMK candidates."""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable
from dataclasses import dataclass

from src.ranking.config import RankingConfig
from src.ranking.topk import RankedCandidate, select_top_m
from src.serving.graph_index import ServingGraphIndex


@dataclass(frozen=True)
class TopologyScores:
    """All classical topology scores for a single query/candidate pair."""

    common_neighbors: float
    adamic_adar: float
    jaccard: float
    preferential_attachment: float

    def value_for(self, ranking_method: str) -> float:
        """Return the configured finite score."""

        values = {
            "cn": self.common_neighbors,
            "aa": self.adamic_adar,
            "jaccard": self.jaccard,
            "pa": self.preferential_attachment,
        }
        try:
            return values[ranking_method]
        except KeyError as error:
            raise ValueError("unknown ranking method") from error


def score_topology_candidates(
    user_id: Hashable,
    candidate_ids: Iterable[Hashable],
    graph: ServingGraphIndex,
) -> dict[Hashable, TopologyScores]:
    """Compute CN, AA, Jaccard, and PA in one query-neighborhood traversal.

    The active ``ServingGraphIndex`` defines every neighborhood and degree.
    Therefore directed indexes use out-neighbor semantics, while mutual
    indexes use their undirected mutual-neighbor semantics without conversion.
    Candidates do not need to be reachable in two hops; callers commonly pass
    the bounded retrieval result.
    """

    unique_candidates = tuple(dict.fromkeys(candidate_ids))
    user_neighbors = frozenset(graph.neighbors(user_id))
    user_degree = graph.degree(user_id)
    scores: dict[Hashable, TopologyScores] = {}
    for candidate in unique_candidates:
        common_neighbors = 0.0
        adamic_adar = 0.0
        # CN and AA share this one candidate-neighborhood traversal.  This
        # preserves Sprint 1's out-neighbor definition for directed graphs;
        # on mutual indexes it is the same undirected common-neighbor set.
        for middle in graph.neighbors(candidate):
            if middle in user_neighbors:
                common_neighbors += 1.0
                middle_degree = graph.degree(middle)
                if middle_degree > 1:
                    adamic_adar += 1.0 / math.log(middle_degree)
        candidate_degree = graph.degree(candidate)
        denominator = user_degree + candidate_degree - common_neighbors
        jaccard = common_neighbors / denominator if denominator > 0 else 0.0
        scores[candidate] = TopologyScores(
            common_neighbors=common_neighbors,
            adamic_adar=adamic_adar,
            jaccard=jaccard,
            preferential_attachment=float(user_degree * candidate_degree),
        )
    return scores


def rank_topology_candidates(
    user_id: Hashable,
    candidate_ids: Iterable[Hashable],
    graph: ServingGraphIndex,
    config: RankingConfig,
) -> tuple[RankedCandidate, ...]:
    """Score retrieved candidates and return deterministic Top-M results."""

    all_scores = score_topology_candidates(user_id, candidate_ids, graph)
    selected_scores = {
        candidate: score.value_for(config.ranking_method)
        for candidate, score in all_scores.items()
    }
    return select_top_m(selected_scores, config.top_m)
