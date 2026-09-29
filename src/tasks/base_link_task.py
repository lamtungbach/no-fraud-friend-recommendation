"""Shared task graph contract and relation resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch
from torch import Tensor

from src.data import CanonicalGraph


DEFAULT_RELATION_EQUIVALENCES: dict[str, dict[str, str]] = {
    "friends": {"inverse_equivalent": "followers"},
}


@dataclass
class TaskGraph:
    """Task-specific view; the source ``CanonicalGraph`` remains untouched."""

    num_nodes: int
    observed_edge_index: Tensor
    observed_edge_type: Tensor
    positive_edges: Tensor
    directed: bool
    task_name: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def num_positive_edges(self) -> int:
        return int(self.positive_edges.shape[0])


class BaseLinkTask:
    def __init__(self, graph: CanonicalGraph, target_relation: str, relation_equivalences: dict[str, dict[str, str]] | None = None):
        self.graph = graph
        self.target_relation = self._resolve_relation_name(target_relation)
        self.relation_equivalences = relation_equivalences or DEFAULT_RELATION_EQUIVALENCES
        self.target_relation_id = self._relation_id(self.target_relation)

    def _resolve_relation_name(self, requested: str) -> str:
        requested = requested.lower().strip()
        names = {str(value["name"]): relation_id for relation_id, value in self.graph.relation_schema.items()}
        if requested in names:
            return requested
        matches = [name for name in names if name.rstrip("s") == requested.rstrip("s")]
        if len(matches) == 1:
            return matches[0]
        raise ValueError(f"Unknown relation '{requested}'. Available relations: {sorted(names)}")

    def _relation_id(self, relation_name: str) -> int:
        for relation_id, schema in self.graph.relation_schema.items():
            if schema.get("name") == relation_name:
                return int(relation_id)
        raise ValueError(f"Relation schema has no ID for '{relation_name}'")

    def _selected_relation_ids(self) -> set[int]:
        ids = {self.target_relation_id}
        equivalence = self.relation_equivalences.get(self.target_relation, {})
        inverse_name = equivalence.get("inverse_equivalent")
        if inverse_name is not None:
            available_names = {str(value["name"]) for value in self.graph.relation_schema.values()}
            normalized_inverse = inverse_name.lower().strip()
            matching_names = [name for name in available_names if name == normalized_inverse or name.rstrip("s") == normalized_inverse.rstrip("s")]
            if len(matching_names) == 1:
                ids.add(self._relation_id(matching_names[0]))
        return ids

    def _task_edges(self) -> tuple[Tensor, Tensor]:
        # Scorers receive target social topology only.  Equivalent relations are
        # handled by LeakageMasker when masking a full CanonicalGraph; keeping
        # them out here prevents an implicit mixed-relation baseline.
        mask = self.graph.edge_type == self.target_relation_id
        return self.graph.edge_index[:, mask].clone(), self.graph.edge_type[mask].clone()

    def _base_metadata(self) -> dict[str, Any]:
        return {
            "target_relation": self.target_relation,
            "target_relation_id": self.target_relation_id,
            "selected_relation_ids": [self.target_relation_id],
            "inverse_equivalent_relation_ids": sorted(self._selected_relation_ids() - {self.target_relation_id}),
            "interaction_relations_excluded": True,
        }
