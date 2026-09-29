"""Validate Task 2 split sizes and train-observed topology on MGTAB."""

import json
from pathlib import Path
import sys

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.adapters import MGTABAdapter  # noqa: E402
from src.split import build_observed_graph, split_positive_links  # noqa: E402
from src.tasks import DirectedConnectionTask, MutualConnectionTask  # noqa: E402


def main() -> None:
    graph = MGTABAdapter(ROOT / "data" / "raw" / "MGTAB").transform()
    reports = {}
    for name, task in {
        "directed": DirectedConnectionTask(graph, "friend").build(),
        "mutual": MutualConnectionTask(graph, "friend").build(),
    }.items():
        split = split_positive_links(task.positive_edges, seed=42)
        hidden = torch.cat([split.val_pos, split.test_pos])
        train_graph = build_observed_graph(task, hidden)
        degrees = [0] * train_graph.num_nodes
        for source, destination in train_graph.observed_edge_index.t().tolist():
            degrees[source] += 1
            degrees[destination] += 1
        reports[name] = {
            "train_size": int(split.train_pos.shape[0]),
            "val_size": int(split.val_pos.shape[0]),
            "test_size": int(split.test_pos.shape[0]),
            "hidden_positive_count": int(hidden.shape[0]),
            "edges_removed_by_leakage_mask": int(task.observed_edge_index.shape[1] - train_graph.observed_edge_index.shape[1]),
            "isolated_nodes_after_split": sum(degree == 0 for degree in degrees),
        }
    output = ROOT / "results" / "task_stats" / "split_stats.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2))
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
