"""Reusable validation for :class:`CanonicalGraph`."""

from __future__ import annotations

import logging

import torch

from .canonical_graph import CanonicalGraph

LOGGER = logging.getLogger(__name__)


def validate_canonical_graph(graph: CanonicalGraph) -> None:
    """Raise ``ValueError`` with an actionable message when the schema is invalid."""
    node_ids = graph.node_ids
    if node_ids.ndim != 1:
        raise ValueError(f"node_ids must have shape [N], got {tuple(node_ids.shape)}")
    if node_ids.numel() and not torch.equal(node_ids, torch.arange(graph.num_nodes, device=node_ids.device, dtype=node_ids.dtype)):
        raise ValueError("node_ids must be contiguous canonical IDs 0..N-1")

    edge_index = graph.edge_index
    if edge_index.ndim != 2 or edge_index.shape[0] != 2:
        raise ValueError(f"edge_index must have shape [2, E], got {tuple(edge_index.shape)}")
    num_edges = int(edge_index.shape[1])
    if graph.edge_type.ndim != 1 or graph.edge_type.shape[0] != num_edges:
        raise ValueError(f"edge_type length must equal num_edges={num_edges}, got shape {tuple(graph.edge_type.shape)}")
    if graph.edge_weight is not None and (graph.edge_weight.ndim != 1 or graph.edge_weight.shape[0] != num_edges):
        raise ValueError(f"edge_weight length must equal num_edges={num_edges}, got shape {tuple(graph.edge_weight.shape)}")
    if edge_index.numel():
        minimum, maximum = int(edge_index.min()), int(edge_index.max())
        if minimum < 0:
            raise ValueError(f"edge_index contains negative node id {minimum}")
        if maximum >= graph.num_nodes:
            raise ValueError(f"edge_index contains node id {maximum} but num_nodes={graph.num_nodes}")

    if graph.node_features is not None:
        if graph.node_features.ndim != 2 or graph.node_features.shape[0] != graph.num_nodes:
            raise ValueError(f"node_features must have shape [N, F] with N={graph.num_nodes}, got {tuple(graph.node_features.shape)}")
        if not torch.isfinite(graph.node_features).all():
            raise ValueError("node_features contains NaN or Inf")
    for name, label in graph.labels.items():
        if label.ndim == 0 or label.shape[0] != graph.num_nodes:
            raise ValueError(f"label '{name}' must have first dimension num_nodes={graph.num_nodes}, got {tuple(label.shape)}")
        if label.is_floating_point() and not torch.isfinite(label).all():
            raise ValueError(f"label '{name}' contains NaN or Inf")

    relation_ids = set(int(value) for value in graph.edge_type.detach().cpu().unique().tolist())
    schema_ids = set(int(value) for value in graph.relation_schema)
    missing = sorted(relation_ids - schema_ids)
    if missing:
        raise ValueError(f"edge_type contains relation IDs without schema entries: {missing}")

    pairs = edge_index.t()
    if pairs.numel():
        self_loops = int((pairs[:, 0] == pairs[:, 1]).sum())
        duplicates = int(pairs.shape[0] - torch.unique(pairs, dim=0).shape[0])
        if self_loops:
            LOGGER.warning("CanonicalGraph contains %d self-loop edge(s); none were removed", self_loops)
        if duplicates:
            LOGGER.warning("CanonicalGraph contains %d duplicate edge row(s); none were removed", duplicates)
