import torch

from src.graph.graph_view import GraphView
from src.retrieval import (
    RetrievalConfig,
    RetrievalStats,
    retrieve_bounded_two_hop_candidates,
)
from src.retrieval.two_hop import retrieve_two_hop_candidates_reference
from src.serving.graph_index import ServingGraphIndex


def _index(edges: list[tuple[int, int]], nodes: int = 7) -> ServingGraphIndex:
    edge_index = (
        torch.tensor(edges, dtype=torch.long).t().contiguous()
        if edges
        else torch.empty((2, 0), dtype=torch.long)
    )
    return ServingGraphIndex.from_graph_view(
        GraphView(torch.arange(nodes), edge_index, directed=True)
    )


def test_isolated_and_degree_one_users_have_empty_bounded_results():
    graph = _index([(0, 1)], nodes=3)

    isolated = retrieve_bounded_two_hop_candidates(2, graph)
    degree_one = retrieve_bounded_two_hop_candidates(0, graph)

    assert isolated.candidate_ids == ()
    assert isolated.stats == RetrievalStats(0, 0, 0, 0, 0, False)
    assert degree_one.candidate_ids == ()
    assert degree_one.stats.first_hop_seen == 1
    assert degree_one.stats.second_hop_expansions == 0


def test_candidates_exclude_self_direct_neighbors_and_duplicates():
    graph = _index(
        [
            (0, 1),
            (0, 2),
            (0, 4),
            (1, 0),
            (1, 3),
            (1, 4),
            (2, 0),
            (2, 3),
        ]
    )

    result = retrieve_bounded_two_hop_candidates(0, graph)

    assert result.candidate_ids == (3,)
    assert result.stats.second_hop_expansions == 5
    assert result.stats.candidates_before_cap == 1
    assert result.stats.truncated is False


def test_first_hop_cap_uses_deterministic_first_adjacency_entries():
    graph = _index([(0, 1), (0, 2), (1, 4), (2, 5)])

    result = retrieve_bounded_two_hop_candidates(
        0, graph, RetrievalConfig(first_hop_cap=1)
    )

    assert result.candidate_ids == (4,)
    assert result.stats.first_hop_seen == 2
    assert result.stats.first_hop_used == 1
    assert result.stats.truncated is True


def test_second_hop_cap_is_applied_per_first_hop_neighbor():
    graph = _index([(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)])

    result = retrieve_bounded_two_hop_candidates(
        0, graph, RetrievalConfig(second_hop_cap=1)
    )

    assert result.candidate_ids == (3, 5)
    assert result.stats.second_hop_expansions == 2
    assert result.stats.truncated is True


def test_candidate_cap_preserves_deterministic_discovery_order_and_stats():
    graph = _index([(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)])

    result = retrieve_bounded_two_hop_candidates(
        0, graph, RetrievalConfig(candidate_cap=2)
    )

    assert result.candidate_ids == (3, 4)
    assert result.stats.candidates_before_cap == 4
    assert result.stats.candidates_returned == 2
    assert result.stats.truncated is True


def test_all_caps_combined_never_exceed_their_limits():
    graph = _index([(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)])

    result = retrieve_bounded_two_hop_candidates(
        0,
        graph,
        RetrievalConfig(first_hop_cap=1, second_hop_cap=1, candidate_cap=1),
    )

    assert result.candidate_ids == (3,)
    assert result.stats.first_hop_used <= 1
    assert result.stats.second_hop_expansions <= 1
    assert result.stats.candidates_returned <= 1
    assert result.stats.truncated is True


def test_caps_larger_than_neighborhood_do_not_truncate():
    graph = _index([(0, 1), (1, 2)])

    result = retrieve_bounded_two_hop_candidates(
        0,
        graph,
        RetrievalConfig(first_hop_cap=10, second_hop_cap=10, candidate_cap=10),
    )

    assert result.candidate_ids == (2,)
    assert result.stats.truncated is False


def test_repeated_calls_are_deterministic_and_unlimited_mode_matches_reference():
    graph = _index([(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 3)])
    config = RetrievalConfig()

    first = retrieve_bounded_two_hop_candidates(0, graph, config)
    second = retrieve_bounded_two_hop_candidates(0, graph, config)

    assert first == second
    assert set(first.candidate_ids) == retrieve_two_hop_candidates_reference(0, graph)
    assert first.stats.truncated is False


def test_invalid_caps_and_unsupported_strategy_are_rejected():
    for kwargs in (
        {"first_hop_cap": -1},
        {"second_hop_cap": -1},
        {"candidate_cap": -1},
        {"strategy": "random"},
    ):
        try:
            RetrievalConfig(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected invalid retrieval configuration to fail")
