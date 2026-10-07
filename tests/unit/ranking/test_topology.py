import math

import pytest
import torch

from src.baselines import (
    AdamicAdarScorer,
    CommonNeighborsScorer,
    JaccardScorer,
    PreferentialAttachmentScorer,
)
from src.graph import GraphView
from src.ranking import (
    RankingConfig,
    rank_topology_candidates,
    score_topology_candidates,
)
from src.ranking.topk import select_top_m
from src.retrieval import (
    retrieve_bounded_two_hop_candidates,
    retrieve_two_hop_candidates_reference,
)
from src.serving import ServingGraphIndex
from src.tasks.base_link_task import TaskGraph


def _index(edges: list[tuple[int, int]], *, directed: bool = True, nodes: int = 7):
    edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
    return ServingGraphIndex.from_graph_view(
        GraphView(torch.arange(nodes), edge_index, directed=directed)
    )


def _scoring_index() -> ServingGraphIndex:
    return _index([(0, 1), (0, 2), (1, 3), (1, 4), (2, 3), (2, 5), (3, 1), (3, 2)])


def test_hand_computed_cn_aa_jaccard_and_pa():
    scores = score_topology_candidates(0, [3], _scoring_index())[3]

    assert scores.common_neighbors == 2.0
    assert scores.adamic_adar == pytest.approx(2 / math.log(2))
    assert scores.jaccard == 1.0
    assert scores.preferential_attachment == 4.0


@pytest.mark.parametrize(
    ("method", "expected"),
    [("cn", 2.0), ("aa", 2 / math.log(2)), ("jaccard", 1.0), ("pa", 4.0)],
)
def test_ranking_configuration_selects_each_supported_score(method, expected):
    ranked = rank_topology_candidates(0, [3], _scoring_index(), RankingConfig(method, 1))

    assert ranked[0].candidate_id == 3
    assert ranked[0].score == pytest.approx(expected)


def test_top_m_is_deterministic_and_breaks_ties_by_candidate_id():
    graph = _index([(0, 1), (0, 2), (1, 3), (2, 4)])
    config = RankingConfig("cn", 2)

    first = rank_topology_candidates(0, [4, 3], graph, config)
    second = rank_topology_candidates(0, [3, 4], graph, config)

    assert first == second
    assert [item.candidate_id for item in first] == [3, 4]


def test_empty_pool_single_candidate_and_zero_denominator_are_safe():
    graph = _index([(0, 1)], nodes=3)

    assert rank_topology_candidates(0, [], graph, RankingConfig("cn", 5)) == ()
    single = rank_topology_candidates(2, [1], graph, RankingConfig("jaccard", 1))
    assert single[0].candidate_id == 1
    assert single[0].score == 0.0


def test_low_degree_aa_contribution_is_zero_and_all_scores_are_finite():
    graph = _index([(0, 1), (1, 2)])

    scores = score_topology_candidates(0, [2], graph)[2]

    assert scores.adamic_adar == 0.0
    assert all(math.isfinite(value) for value in scores.__dict__.values())


def test_top_m_rejects_invalid_size_and_nonfinite_scores():
    with pytest.raises(ValueError, match="non-negative"):
        select_top_m({1: 1.0}, -1)
    with pytest.raises(ValueError, match="finite"):
        select_top_m({1: float("nan")}, 1)
    with pytest.raises(ValueError, match="one of"):
        RankingConfig("unknown", 1)


def test_directed_scores_match_sprint1_baselines():
    edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 3), (2, 5), (3, 1), (3, 2)]
    graph = _index(edges)
    task = TaskGraph(7, torch.tensor(edges).t(), torch.zeros(len(edges), dtype=torch.long), torch.empty((0, 2), dtype=torch.long), True, "directed")
    retrieved = retrieve_bounded_two_hop_candidates(0, graph)

    assert set(retrieved.candidate_ids) == retrieve_two_hop_candidates_reference(0, graph)
    scores = score_topology_candidates(0, retrieved.candidate_ids, graph)
    for candidate, score in scores.items():
        assert score.common_neighbors == CommonNeighborsScorer(task).score(0, candidate)
        assert score.adamic_adar == pytest.approx(AdamicAdarScorer(task).score(0, candidate))
        assert score.jaccard == JaccardScorer(task).score(0, candidate)
        assert score.preferential_attachment == PreferentialAttachmentScorer(task).score(0, candidate)


def test_mutual_scores_match_sprint1_baselines_without_reinterpreting_edges():
    edges = [(0, 1), (1, 0), (0, 2), (2, 0), (1, 3), (3, 1), (2, 3), (3, 2)]
    graph = _index(edges, directed=False, nodes=4)
    task = TaskGraph(4, torch.tensor(edges).t(), torch.zeros(len(edges), dtype=torch.long), torch.empty((0, 2), dtype=torch.long), False, "mutual")
    scores = score_topology_candidates(0, [3], graph)[3]

    assert scores.common_neighbors == CommonNeighborsScorer(task).score(0, 3)
    assert scores.adamic_adar == pytest.approx(AdamicAdarScorer(task).score(0, 3))
    assert scores.jaccard == JaccardScorer(task).score(0, 3)
    assert scores.preferential_attachment == PreferentialAttachmentScorer(task).score(0, 3)
