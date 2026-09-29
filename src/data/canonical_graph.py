"""Dataset-independent graph representation used by downstream pipeline code."""

from dataclasses import dataclass, field
from typing import Any

import torch
from torch import Tensor


@dataclass
class CanonicalGraph:
    """A normalized graph contract.

    Node IDs are canonical contiguous IDs.  Dataset-specific labels remain in
    the generic ``labels`` mapping rather than becoming schema fields.
    """

    node_ids: Tensor
    node_features: Tensor | None
    edge_index: Tensor
    edge_type: Tensor
    edge_weight: Tensor | None
    labels: dict[str, Tensor] = field(default_factory=dict)
    relation_schema: dict[int, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def num_nodes(self) -> int:
        return int(self.node_ids.shape[0])

    @property
    def num_edges(self) -> int:
        return int(self.edge_index.shape[1])

    @property
    def num_features(self) -> int | None:
        return None if self.node_features is None else int(self.node_features.shape[1])
