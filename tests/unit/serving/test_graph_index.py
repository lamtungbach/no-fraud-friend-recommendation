import random

import torch

from src.graph.graph_view import GraphView
from src.serving.graph_index import ServingGraphIndex


def test_index_exposes_sorted_neighbors_degree_and_edges_for_directed_view():
    view = GraphView(
        torch.tensor([100, 200, 300]), torch.tensor([[1, 0, 0], [2, 2, 1]]), True
    )
    index = ServingGraphIndex.from_graph_view(view)
    assert index.neighbors(100) == (200, 300)
    assert index.degree(100) == 2
    assert index.has_edge(100, 300) is True
    assert index.has_edge(300, 100) is False
    assert index.num_nodes() == 3
    assert index.num_edges() == 3
    assert index.external_to_internal(200) == 1
    assert index.internal_to_external(2) == 300


def test_index_expands_an_undirected_graph_view_in_both_directions():
    view = GraphView(torch.tensor([10, 20, 30]), torch.tensor([[0, 1], [1, 2]]), False)
    index = ServingGraphIndex.from_graph_view(view)
    assert index.neighbors(20) == (10, 30)
    assert index.has_edge(10, 20) is True
    assert index.has_edge(20, 10) is True
    assert index.num_edges() == 2


def test_index_rejects_unknown_external_node():
    index = ServingGraphIndex.from_graph_view(
        GraphView(torch.tensor([0]), torch.empty((2, 0), dtype=torch.long), True)
    )
    try:
        index.neighbors(99)
    except KeyError as error:
        assert "99" in str(error)
    else:
        raise AssertionError("Expected unknown node lookup to fail")


def test_index_rejects_negative_and_out_of_range_internal_nodes():
    index = ServingGraphIndex.from_graph_view(
        GraphView(torch.tensor([0]), torch.empty((2, 0), dtype=torch.long), True)
    )

    for node_id in (-1, 1):
        try:
            index.internal_to_external(node_id)
        except KeyError as error:
            assert str(node_id) in str(error)
        else:
            raise AssertionError("Expected unknown internal node lookup to fail")


def test_index_matches_reference_adjacency_for_seeded_random_graph():
    rng = random.Random(42)
    node_ids = list(range(20, 32))
    edges = {(rng.randrange(12), rng.randrange(12)) for _ in range(50)}
    reference = {node: set() for node in node_ids}
    for source, destination in edges:
        reference[node_ids[source]].add(node_ids[destination])
    edge_index = torch.tensor(sorted(edges), dtype=torch.long).t().contiguous()
    index = ServingGraphIndex.from_graph_view(GraphView(torch.tensor(node_ids), edge_index, True))

    for node in rng.sample(node_ids, 6):
        assert index.neighbors(node) == tuple(sorted(reference[node]))
        assert index.degree(node) == len(reference[node])
