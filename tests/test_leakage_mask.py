import torch

from src.data import CanonicalGraph
from src.split import LeakageMasker, build_observed_graph, split_positive_links
from src.tasks import DirectedConnectionTask


def test_directed_mask_hides_inverse_equivalent_but_keeps_interactions():
    graph = CanonicalGraph(
        node_ids=torch.arange(3), node_features=None,
        edge_index=torch.tensor([[0, 1, 0], [1, 0, 1]]),
        edge_type=torch.tensor([1, 0, 2]), edge_weight=None,
        relation_schema={
            0: {"name": "followers", "directed": True},
            1: {"name": "friends", "directed": True},
            2: {"name": "mention", "directed": True},
        },
    )
    masked = LeakageMasker(graph).hide_directed_target(0, 1, "friend")
    assert masked.metadata["masked_edge_rows"] == 2
    assert masked.edge_type.tolist() == [2]
    assert graph.edge_index.shape[1] == 3


def test_train_graph_hides_validation_and_test_pairs():
    graph = CanonicalGraph(
        node_ids=torch.arange(4), node_features=None,
        edge_index=torch.tensor([[0, 1, 2, 3], [1, 0, 3, 2]]),
        edge_type=torch.tensor([1, 1, 1, 1]), edge_weight=None,
        relation_schema={1: {"name": "friends", "directed": True}},
    )
    task = DirectedConnectionTask(graph, "friends").build()
    split = split_positive_links(task.positive_edges, train_ratio=.5, val_ratio=.25, test_ratio=.25)
    observed = build_observed_graph(task, torch.cat([split.val_pos, split.test_pos]))
    hidden = {tuple(pair) for pair in torch.cat([split.val_pos, split.test_pos]).tolist()}
    remaining = {tuple(pair) for pair in observed.observed_edge_index.t().tolist()}
    assert hidden.isdisjoint(remaining)
    assert graph.edge_index.shape[1] == 4
