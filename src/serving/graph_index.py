"""Sorted CSR-like adjacency index for deterministic PYMK graph queries."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Hashable
from dataclasses import dataclass

from src.graph.graph_view import GraphView


@dataclass(frozen=True)
class ServingGraphIndex:
    """Dense adjacency storage with external-ID lookup at the boundary."""

    _external_to_internal: dict[Hashable, int]
    _internal_to_external: tuple[Hashable, ...]
    _offsets: tuple[int, ...]
    _adjacency: tuple[int, ...]
    _edge_count: int

    @classmethod
    def from_graph_view(cls, view: GraphView) -> ServingGraphIndex:
        external_ids = tuple(view.node_ids.detach().cpu().tolist())
        if len(set(external_ids)) != len(external_ids):
            raise ValueError("GraphView node_ids must be unique")
        adjacency_sets = [set() for _ in external_ids]
        logical_edges: set[tuple[int, int]] = set()
        for source, destination in view.edge_index.t().tolist():
            source, destination = int(source), int(destination)
            if not (
                0 <= source < len(external_ids) and 0 <= destination < len(external_ids)
            ):
                raise ValueError(
                    "GraphView edge_index contains an unknown internal node ID"
                )
            adjacency_sets[source].add(destination)
            if view.directed:
                logical_edges.add((source, destination))
            else:
                adjacency_sets[destination].add(source)
                logical_edges.add(tuple(sorted((source, destination))))
        offsets = [0]
        adjacency: list[int] = []
        for neighbors in adjacency_sets:
            adjacency.extend(sorted(neighbors))
            offsets.append(len(adjacency))
        return cls(
            {node: index for index, node in enumerate(external_ids)},
            external_ids,
            tuple(offsets),
            tuple(adjacency),
            len(logical_edges),
        )

    def _to_internal(self, user_id: Hashable) -> int:
        try:
            return self._external_to_internal[user_id]
        except KeyError as error:
            raise KeyError(f"Unknown user_id: {user_id!r}") from error

    def neighbors(self, user_id: Hashable) -> tuple[Hashable, ...]:
        node = self._to_internal(user_id)
        return tuple(
            self._internal_to_external[neighbor]
            for neighbor in self._adjacency[
                self._offsets[node] : self._offsets[node + 1]
            ]
        )

    def degree(self, user_id: Hashable) -> int:
        node = self._to_internal(user_id)
        return self._offsets[node + 1] - self._offsets[node]

    def has_edge(self, source_id: Hashable, destination_id: Hashable) -> bool:
        source = self._to_internal(source_id)
        destination = self._to_internal(destination_id)
        start, end = self._offsets[source], self._offsets[source + 1]
        position = bisect_left(self._adjacency, destination, start, end)
        return position < end and self._adjacency[position] == destination

    def num_nodes(self) -> int:
        return len(self._internal_to_external)

    def num_edges(self) -> int:
        return self._edge_count

    def external_to_internal(self, user_id: Hashable) -> int:
        return self._to_internal(user_id)

    def internal_to_external(self, node_id: int) -> Hashable:
        if node_id < 0:
            raise KeyError(f"Unknown internal node_id: {node_id!r}")
        try:
            return self._internal_to_external[node_id]
        except IndexError as error:
            raise KeyError(f"Unknown internal node_id: {node_id!r}") from error
