"""Small candidate/scorer smoke test; does not run a full benchmark."""

from pathlib import Path
import sys

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.baselines import CommonNeighborsScorer  # noqa: E402
from src.candidates import TwoHopCandidateGenerator  # noqa: E402
from src.data.adapters import MGTABAdapter  # noqa: E402
from src.split import build_observed_graph, split_positive_links  # noqa: E402
from src.tasks import DirectedConnectionTask, MutualConnectionTask  # noqa: E402


def main() -> None:
    canonical = MGTABAdapter(ROOT / "data" / "raw" / "MGTAB").transform()
    tasks = {"directed": DirectedConnectionTask(canonical, "friend").build(), "mutual": MutualConnectionTask(canonical, "friend").build()}
    for name, task in tasks.items():
        split = split_positive_links(task.positive_edges, seed=42)
        observed = build_observed_graph(task, torch.cat([split.val_pos, split.test_pos]))
        generator = TwoHopCandidateGenerator(observed)
        source = next(node for node in range(observed.num_nodes) if generator.generate(node))
        scorer = CommonNeighborsScorer(observed)
        ranked = sorted(((candidate, scorer.score(source, candidate)) for candidate in generator.generate(source)), key=lambda row: (-row[1], row[0]))[:3]
        print(f"Task: {name}")
        print(f"Source user: {source}")
        print(f"Candidates: {len(generator.generate(source))}")
        print("Top Common Neighbors:")
        for rank, (candidate, score) in enumerate(ranked, start=1):
            print(f"{rank}. {candidate} score={score:.3f}")


if __name__ == "__main__":
    main()
