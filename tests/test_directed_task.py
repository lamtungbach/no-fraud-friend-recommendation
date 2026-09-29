import torch

from src.data import CanonicalGraph
from src.tasks import DirectedConnectionTask


def graph():
    return CanonicalGraph(
        node_ids=torch.arange(3), node_features=None,
        edge_index=torch.tensor([[0, 1, 1], [1, 0, 2]]),
        edge_type=torch.tensor([1, 1, 1]), edge_weight=None,
        relation_schema={1: {"name": "friends", "directed": True}},
    )


def test_directed_task_keeps_ordered_positive_edges():
    task = DirectedConnectionTask(graph(), target_relation="friend").build()
    assert task.directed is True
    assert {tuple(pair) for pair in task.positive_edges.tolist()} == {(0, 1), (1, 0), (1, 2)}

