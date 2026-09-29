"""Directed connection task."""

from __future__ import annotations

import torch

from .base_link_task import BaseLinkTask, TaskGraph


class DirectedConnectionTask(BaseLinkTask):
    """Predict ordered target-relation edges ``u -> v``."""

    def build(self) -> TaskGraph:
        observed_edges, observed_types = self._task_edges()
        target_mask = observed_types == self.target_relation_id
        positives = observed_edges[:, target_mask].t().contiguous()
        metadata = self._base_metadata()
        metadata.update({"num_directed_target_edges": int(positives.shape[0])})
        return TaskGraph(
            num_nodes=self.graph.num_nodes,
            observed_edge_index=observed_edges,
            observed_edge_type=observed_types,
            positive_edges=positives,
            directed=True,
            task_name="directed_connection",
            metadata=metadata,
        )
