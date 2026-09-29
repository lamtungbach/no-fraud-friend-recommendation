import torch
import pytest

from src.data import CanonicalGraph
from src.data.validation import validate_canonical_graph


def test_nonfinite_features_fail_validation():
    graph = CanonicalGraph(
        node_ids=torch.arange(2), node_features=torch.tensor([[1.0], [float("nan")]]),
        edge_index=torch.tensor([[0], [1]]), edge_type=torch.tensor([0]), edge_weight=None,
        relation_schema={0: {"name": "r"}},
    )
    with pytest.raises(ValueError, match="NaN or Inf"):
        validate_canonical_graph(graph)
