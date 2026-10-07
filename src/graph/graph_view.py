"""Deterministic graph views used by the PYMK serving pipeline."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from src.data import CanonicalGraph


@dataclass(frozen=True)
class GraphView:
    """A compact semantic view over canonical node IDs and topology.

    ``edge_index`` stores internal positions into ``node_ids``.  Undirected
    views store each logical edge once with its endpoints in ascending order.
    """

    node_ids: Tensor
    edge_index: Tensor
    directed: bool

    @property
    def num_nodes(self) -> int:
        return int(self.node_ids.numel())

    @property
    def num_edges(self) -> int:
        return int(self.edge_index.shape[1])


def _edge_tensor(edges: list[tuple[int, int]]) -> Tensor:
    if not edges:
        return torch.empty((2, 0), dtype=torch.long)
    return torch.tensor(edges, dtype=torch.long).t().contiguous()


def build_directed_view(canonical_graph: CanonicalGraph) -> GraphView:
    """Keep unique directed edges, ordered lexicographically for repeatability."""
    edges = sorted(
        {
            (int(source), int(destination))
            for source, destination in canonical_graph.edge_index.t().tolist()
        }
    )
    return GraphView(
        node_ids=canonical_graph.node_ids.clone(),
        edge_index=_edge_tensor(edges),
        directed=True,
    )


def build_mutual_view(canonical_graph: CanonicalGraph) -> GraphView:
    """Keep reciprocal directed relationships as one undirected connection."""
    directed_edges = {
        (int(source), int(destination))
        for source, destination in canonical_graph.edge_index.t().tolist()
    }
    mutual_edges = sorted(
        (source, destination)
        for source, destination in directed_edges
        if source < destination and (destination, source) in directed_edges
    )
    return GraphView(
        node_ids=canonical_graph.node_ids.clone(),
        edge_index=_edge_tensor(mutual_edges),
        directed=False,
    )


def build_pymk_graph_view(
    canonical_graph: CanonicalGraph, mode: str = "directed"
) -> GraphView:
    """Build the requested serving topology without changing ``CanonicalGraph``."""
    if mode == "directed":
        return build_directed_view(canonical_graph)
    if mode == "mutual":
        return build_mutual_view(canonical_graph)
    raise ValueError("mode must be either 'directed' or 'mutual'")
