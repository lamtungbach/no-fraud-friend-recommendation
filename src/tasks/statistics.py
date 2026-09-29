"""Small audit reports for link task graphs."""

from __future__ import annotations

from collections import deque

from .base_link_task import TaskGraph


def task_statistics(task: TaskGraph) -> dict:
    degrees = [0] * task.num_nodes
    adjacency = [[] for _ in range(task.num_nodes)]
    for source, destination in task.observed_edge_index.t().tolist():
        degrees[source] += 1
        degrees[destination] += 1
        adjacency[source].append(destination)
        adjacency[destination].append(source)
    components = 0
    visited = set()
    for node in range(task.num_nodes):
        if node in visited:
            continue
        components += 1
        queue = deque([node])
        visited.add(node)
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
    report = {
        "task_name": task.task_name,
        "num_nodes": task.num_nodes,
        "num_positive_edges_or_pairs": task.num_positive_edges,
        "num_nodes_with_at_least_one_target_connection": sum(degree > 0 for degree in degrees),
        "average_degree": (sum(degrees) / task.num_nodes) if task.num_nodes else 0.0,
        "isolated_nodes": sum(degree == 0 for degree in degrees),
        "connected_components": components,
        "directed": task.directed,
        **task.metadata,
    }
    return report
