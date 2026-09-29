"""Shared interface for classical topology-only link scorers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.candidates.base import NeighborIndex
from src.tasks.base_link_task import TaskGraph


class LinkScorer(ABC):
    def __init__(self, graph: TaskGraph):
        self.graph = graph
        self.index = NeighborIndex(graph)
        self.directed_strategy = "out" if graph.directed else "undirected"

    @abstractmethod
    def score(self, u: int, v: int) -> float:
        raise NotImplementedError

    def score_pairs(self, pairs):
        return [self.score(int(u), int(v)) for u, v in pairs]

    def _neighbors(self, node: int) -> set[int]:
        return self.index.neighbors(node)
