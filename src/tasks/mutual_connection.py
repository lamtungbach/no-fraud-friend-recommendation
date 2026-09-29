"""Mutual connection proxy task."""

from __future__ import annotations

import torch

from .base_link_task import BaseLinkTask, TaskGraph


class MutualConnectionTask(BaseLinkTask):
    """Predict unordered pairs with target relation in both directions."""

    def build(self) -> TaskGraph:
        observed_edges, observed_types = self._task_edges()
        target_edges = observed_edges[:, observed_types == self.target_relation_id].t().tolist()
        directed_pairs = {(int(source), int(destination)) for source, destination in target_edges if source != destination}
        mutual_pairs = sorted({(min(source, destination), max(source, destination)) for source, destination in directed_pairs if (destination, source) in directed_pairs})
        positives = torch.tensor(mutual_pairs, dtype=torch.long) if mutual_pairs else torch.empty((0, 2), dtype=torch.long)
        directed_count = len(directed_pairs)
        metadata = self._base_metadata()
        metadata.update({
            "num_directed_target_edges": directed_count,
            "num_reciprocal_directed_pairs": len(mutual_pairs),
            "mutual_ratio": (2.0 * len(mutual_pairs) / directed_count) if directed_count else 0.0,
        })
        return TaskGraph(
            num_nodes=self.graph.num_nodes,
            observed_edge_index=observed_edges,
            observed_edge_type=observed_types,
            positive_edges=positives,
            directed=False,
            task_name="mutual_connection",
            metadata=metadata,
        )
