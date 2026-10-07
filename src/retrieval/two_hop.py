"""Exact, unbounded two-hop candidate retrieval baseline."""

from __future__ import annotations

from collections.abc import Hashable

from src.serving.graph_index import ServingGraphIndex


def retrieve_two_hop_candidates(
    user_id: Hashable, graph: ServingGraphIndex
) -> frozenset[Hashable]:
    """Return unique distance-two candidates that are not already linked."""
    current_neighbors = frozenset(graph.neighbors(user_id))
    candidates: set[Hashable] = set()
    for middle in current_neighbors:
        for candidate in graph.neighbors(middle):
            if (
                candidate != user_id
                and candidate not in current_neighbors
                and not graph.has_edge(user_id, candidate)
            ):
                candidates.add(candidate)
    return frozenset(candidates)


def retrieve_two_hop_candidates_reference(
    user_id: Hashable, graph: ServingGraphIndex
) -> frozenset[Hashable]:
    """Straightforward reference implementation used for correctness checks."""
    first_hop = graph.neighbors(user_id)
    excluded = set(first_hop)
    excluded.add(user_id)
    result: set[Hashable] = set()
    for middle in first_hop:
        for candidate in graph.neighbors(middle):
            if candidate not in excluded and not graph.has_edge(user_id, candidate):
                result.add(candidate)
    return frozenset(result)
