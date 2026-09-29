"""Adapter for the tensor-file representation of MGTAB."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import torch

from ..base_adapter import DatasetAdapter
from ..canonical_graph import CanonicalGraph

LOGGER = logging.getLogger(__name__)

MGTAB_RELATION_SCHEMA: dict[int, dict[str, Any]] = {
    0: {"name": "followers", "directed": True, "description": "Follower relationship"},
    1: {"name": "friends", "directed": True, "description": "Friend relationship"},
    2: {"name": "mention", "directed": True, "description": "Mention interaction"},
    3: {"name": "reply", "directed": True, "description": "Reply interaction"},
    4: {"name": "quoted", "directed": True, "description": "Quoted interaction"},
    5: {"name": "url", "directed": True, "description": "Shared URL relationship"},
    6: {"name": "hashtag", "directed": True, "description": "Shared hashtag relationship"},
}


class MGTABAdapter(DatasetAdapter):
    """Read MGTAB's six ``.pt`` tensors and build ``CanonicalGraph``."""

    REQUIRED_FILES = ("edge_index.pt", "edge_type.pt", "edge_weight.pt", "features.pt", "labels_bot.pt", "labels_stance.pt")

    def __init__(self, dataset_dir: str | Path):
        self.dataset_dir = Path(dataset_dir)

    @staticmethod
    def _load_tensor(path: Path) -> torch.Tensor:
        try:
            return torch.load(path, map_location="cpu", weights_only=True)
        except TypeError:  # compatibility with older PyTorch
            return torch.load(path, map_location="cpu")

    def load_raw(self) -> dict[str, torch.Tensor]:
        missing = [name for name in self.REQUIRED_FILES if not (self.dataset_dir / name).is_file()]
        if missing:
            raise FileNotFoundError(f"MGTAB dataset is missing required file(s): {', '.join(missing)}")
        return {Path(name).stem: self._load_tensor(self.dataset_dir / name) for name in self.REQUIRED_FILES}

    def transform(self) -> CanonicalGraph:
        raw = self.load_raw()
        edge_index = raw["edge_index"].long()
        edge_type = raw["edge_type"].long()
        edge_weight = raw["edge_weight"].float()
        features = raw["features"].float()
        labels = {"bot": raw["labels_bot"].long(), "stance": raw["labels_stance"].long()}
        if edge_index.dtype != raw["edge_index"].dtype:
            LOGGER.info("Normalized edge_index dtype to torch.int64")
        metadata = {
            "dataset_name": "MGTAB",
            "schema_version": "1.0",
            "num_nodes": int(features.shape[0]),
            "num_edges": int(edge_index.shape[1]),
            "num_features": int(features.shape[1]),
            "source_path": self.dataset_dir.name,
        }
        graph = CanonicalGraph(
            node_ids=torch.arange(features.shape[0], dtype=torch.long),
            node_features=features,
            edge_index=edge_index,
            edge_type=edge_type,
            edge_weight=edge_weight,
            labels=labels,
            relation_schema=dict(MGTAB_RELATION_SCHEMA),
            metadata=metadata,
        )
        self.validate(graph)
        return graph
