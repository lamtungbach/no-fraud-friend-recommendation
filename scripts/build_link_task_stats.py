"""Build Task 2 semantic task audit reports."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.adapters import MGTABAdapter  # noqa: E402
from src.tasks import DirectedConnectionTask, MutualConnectionTask  # noqa: E402
from src.tasks.statistics import task_statistics  # noqa: E402


def main() -> None:
    graph = MGTABAdapter(ROOT / "data" / "raw" / "MGTAB").transform()
    reports = {
        "directed": task_statistics(DirectedConnectionTask(graph, "friend").build()),
        "mutual": task_statistics(MutualConnectionTask(graph, "friend").build()),
    }
    output_dir = ROOT / "results" / "task_stats"
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, report in reports.items():
        path = output_dir / f"{name}_stats.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"{name}: {report['num_positive_edges_or_pairs']} positives -> {path}")


if __name__ == "__main__":
    main()
