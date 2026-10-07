import torch

from src.data import CanonicalGraph
from src.graph.graph_view import (
    build_directed_view,
    build_mutual_view,
    build_pymk_graph_view,
)


def _canonical_graph() -> CanonicalGraph:
    return CanonicalGraph(
        node_ids=torch.tensor([10, 20, 30, 40]),
        node_features=None,
        edge_index=torch.tensor([[2, 0, 1, 0, 2], [0, 1, 0, 1, 3]]),
        edge_type=torch.zeros(5, dtype=torch.long),
        edge_weight=None,
    )


def test_directed_view_keeps_unique_directed_edges_in_deterministic_order():
    view = build_directed_view(_canonical_graph())
    assert view.directed is True
    assert view.num_nodes == 4
    assert view.edge_index.tolist() == [[0, 1, 2, 2], [1, 0, 0, 3]]


def test_mutual_view_keeps_only_reciprocal_pairs_as_undirected_edges():
    view = build_mutual_view(_canonical_graph())
    assert view.directed is False
    assert view.edge_index.tolist() == [[0], [1]]


def test_graph_view_rejects_unknown_mode():
    try:
        build_pymk_graph_view(_canonical_graph(), mode="weighted")
    except ValueError as error:
        assert "mode" in str(error)
    else:
        raise AssertionError("Expected an invalid mode to be rejected")
