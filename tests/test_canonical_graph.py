import torch

from src.data import CanonicalGraph
from src.data.validation import validate_canonical_graph


def toy_graph(**overrides):
    values = dict(
        node_ids=torch.arange(3),
        node_features=None,
        edge_index=torch.tensor([[0, 1], [1, 2]]),
        edge_type=torch.tensor([0, 1]),
        edge_weight=None,
        labels={},
        relation_schema={0: {"name": "a"}, 1: {"name": "b"}},
        metadata={"dataset_name": "toy"},
    )
    values.update(overrides)
    return CanonicalGraph(**values)


def test_canonical_schema_supports_optional_fields():
    graph = toy_graph()
    validate_canonical_graph(graph)
    assert graph.edge_index.shape == (2, 2)
    assert graph.metadata["dataset_name"] == "toy"
    assert graph.labels == {}
    assert graph.node_features is None
    assert graph.edge_weight is None


def test_invalid_edge_is_rejected():
    graph = toy_graph(edge_index=torch.tensor([[0, 1], [1, 5]]))
    try:
        validate_canonical_graph(graph)
    except ValueError as error:
        assert "node id 5" in str(error)
    else:
        raise AssertionError("invalid edge was accepted")


def test_invalid_edge_type_length_is_rejected():
    graph = toy_graph(edge_type=torch.tensor([0]))
    try:
        validate_canonical_graph(graph)
    except ValueError as error:
        assert "edge_type length" in str(error)
    else:
        raise AssertionError("invalid edge_type length was accepted")
