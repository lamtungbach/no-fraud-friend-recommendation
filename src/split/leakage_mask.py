"""Central leakage masking rules for task graphs."""

from __future__ import annotations

import torch
from torch import Tensor

from src.data import CanonicalGraph
from src.tasks.base_link_task import DEFAULT_RELATION_EQUIVALENCES, TaskGraph


def _unordered_pair_set(edges: Tensor) -> set[tuple[int, int]]:
    return {(min(int(u), int(v)), max(int(u), int(v))) for u, v in edges.tolist()}


def mask_task_graph_edges(task_graph: TaskGraph, hidden_edges: Tensor) -> TaskGraph:
    """Hide both orientations of every hidden pair from a task graph.

    TaskGraph contains target social topology only. Removing both orientations
    prevents the held-out pair from remaining visible in that topology.
    ``LeakageMasker`` below additionally handles inverse-equivalent relations
    when masking a full CanonicalGraph.
    """
    if hidden_edges.numel() == 0:
        return TaskGraph(task_graph.num_nodes, task_graph.observed_edge_index.clone(), task_graph.observed_edge_type.clone(), task_graph.positive_edges.clone(), task_graph.directed, task_graph.task_name, dict(task_graph.metadata))
    hidden_pairs = _unordered_pair_set(hidden_edges)
    edges = task_graph.observed_edge_index
    keep = torch.tensor([(min(int(u), int(v)), max(int(u), int(v))) not in hidden_pairs for u, v in edges.t().tolist()], dtype=torch.bool)
    metadata = dict(task_graph.metadata)
    metadata["hidden_edge_rows"] = int((~keep).sum())
    return TaskGraph(task_graph.num_nodes, edges[:, keep].clone(), task_graph.observed_edge_type[keep].clone(), task_graph.positive_edges.clone(), task_graph.directed, task_graph.task_name, metadata)


class LeakageMasker:
    """Mask task-specific social topology without mutating the source graph."""

    def __init__(self, graph):
        self.graph = graph

    def _task_edges(self, relation: str) -> tuple[Tensor, Tensor, int, set[int]]:
        names = {str(schema["name"]): int(relation_id) for relation_id, schema in self.graph.relation_schema.items()}
        requested = relation.lower().rstrip("s")
        matches = [(name, relation_id) for name, relation_id in names.items() if name.rstrip("s") == requested]
        if len(matches) != 1:
            raise ValueError(f"Unknown relation '{relation}'")
        name, target_id = matches[0]
        relation_ids = {target_id}
        inverse_name = DEFAULT_RELATION_EQUIVALENCES.get(name, {}).get("inverse_equivalent")
        if inverse_name in names:
            relation_ids.add(names[inverse_name])
        mask = torch.zeros(self.graph.edge_type.shape[0], dtype=torch.bool)
        for relation_id in relation_ids:
            mask |= self.graph.edge_type == relation_id
        return self.graph.edge_index[:, mask], self.graph.edge_type[mask], target_id, relation_ids

    def _hide(self, u: int, v: int, relation: str) -> CanonicalGraph:
        _, _, _, relation_ids = self._task_edges(relation)
        social = torch.zeros(self.graph.edge_type.shape[0], dtype=torch.bool)
        for relation_id in relation_ids:
            social |= self.graph.edge_type == relation_id
        endpoints = ((self.graph.edge_index[0] == u) & (self.graph.edge_index[1] == v)) | ((self.graph.edge_index[0] == v) & (self.graph.edge_index[1] == u))
        keep = ~(social & endpoints)
        metadata = dict(self.graph.metadata)
        metadata["masked_edge_rows"] = int((~keep).sum())
        return CanonicalGraph(
            node_ids=self.graph.node_ids.clone(),
            node_features=None if self.graph.node_features is None else self.graph.node_features.clone(),
            edge_index=self.graph.edge_index[:, keep].clone(),
            edge_type=self.graph.edge_type[keep].clone(),
            edge_weight=None if self.graph.edge_weight is None else self.graph.edge_weight[keep].clone(),
            labels={name: label.clone() for name, label in self.graph.labels.items()},
            relation_schema=dict(self.graph.relation_schema),
            metadata=metadata,
        )

    def hide_directed_target(self, u: int, v: int, relation: str):
        return self._hide(u, v, relation)

    def hide_mutual_target(self, u: int, v: int, relation: str):
        return self._hide(u, v, relation)
