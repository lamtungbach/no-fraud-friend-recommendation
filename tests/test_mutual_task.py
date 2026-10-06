import torch

from src.data import CanonicalGraph
from src.tasks import MutualConnectionTask


def test_mutual_task_canonicalizes_reciprocal_pairs():
    graph = CanonicalGraph(
        node_ids=torch.arange(3), node_features=None,
        edge_index=torch.tensor([[0, 1, 1], [1, 0, 2]]),
        edge_type=torch.tensor([1, 1, 1]), edge_weight=None,
        relation_schema={1: {"name": "friends", "directed": True}},
    )
    task = MutualConnectionTask(graph, target_relation="friends").build()
    assert task.directed is False
    assert task.positive_edges.tolist() == [[0, 1]]
    assert task.metadata["mutual_ratio"] == 2 / 3
