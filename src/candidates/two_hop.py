"""Two-hop PYMK candidate generation."""

from __future__ import annotations

from dataclasses import dataclass

from .base import NeighborIndex
from src.tasks.base_link_task import TaskGraph


@dataclass(frozen=True)
class DirectedCandidateConfig:
    first_hop: str = "out"
    second_hop: str = "out"

    def __post_init__(self):
        if (self.first_hop, self.second_hop) != ("out", "out"):
            raise ValueError("Initial directed candidate strategy supports only explicit out -> out")


class TwoHopCandidateGenerator:
    def __init__(self, graph: TaskGraph, directed_config: DirectedCandidateConfig | None = None):
        self.graph = graph
        self.directed_config = directed_config or DirectedCandidateConfig()
        self.index = NeighborIndex(graph, directed_strategy=self.directed_config.first_hop)

    def generate(self, source_node: int) -> set[int]:
        if source_node < 0 or source_node >= self.graph.num_nodes:
            raise ValueError(f"source_node {source_node} is outside 0..{self.graph.num_nodes - 1}")
        first_hop = self.index.neighbors(source_node)
        candidates: set[int] = set()
        for middle in first_hop:
            candidates.update(self.index.neighbors(middle))
        return candidates - first_hop - {source_node}


def generate_two_hop_candidates(graph: TaskGraph, source_node: int, directed: bool | None = None, directed_config: DirectedCandidateConfig | None = None) -> set[int]:
    if directed is not None and directed != graph.directed:
        raise ValueError("directed argument must match TaskGraph.directed")
    return TwoHopCandidateGenerator(graph, directed_config).generate(source_node)
