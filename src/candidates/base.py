"""Shared adjacency views for task-specific candidate generation and scoring."""

from __future__ import annotations

from src.tasks.base_link_task import TaskGraph


class NeighborIndex:
    def __init__(self, graph: TaskGraph, directed_strategy: str = "out"):
        if directed_strategy != "out":
            raise ValueError("Only the explicit directed 'out' neighbor strategy is supported")
        self.graph = graph
        self.directed_strategy = directed_strategy
        self.out = [set() for _ in range(graph.num_nodes)]
        self.incoming = [set() for _ in range(graph.num_nodes)]
        for source, destination in graph.observed_edge_index.t().tolist():
            self.out[source].add(destination)
            self.incoming[destination].add(source)
        self.undirected = [self.out[node] | self.incoming[node] for node in range(graph.num_nodes)]

    def neighbors(self, node: int) -> set[int]:
        return self.out[node] if self.graph.directed else self.undirected[node]
