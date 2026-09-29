"""Run reproducible sampled Task 4 classical-baseline experiments."""

import csv
import json
from pathlib import Path
import sys
from time import perf_counter

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.baselines import AdamicAdarScorer, CommonNeighborsScorer, JaccardScorer, PreferentialAttachmentScorer, RandomScorer  # noqa: E402
from src.candidates import TwoHopCandidateGenerator  # noqa: E402
from src.data.adapters import MGTABAdapter  # noqa: E402
from src.evaluation import ClassicalEvaluator  # noqa: E402
from src.evaluation.reporting import render_comparison  # noqa: E402
from src.sampling import sample_hard_negatives, sample_random_negatives  # noqa: E402
from src.split import build_observed_graph, split_positive_links  # noqa: E402
from src.tasks import DirectedConnectionTask, MutualConnectionTask  # noqa: E402
from src.tasks.statistics import task_statistics  # noqa: E402

CONFIG = {
    "seed": 42,
    "train_ratio": 0.70,
    "val_ratio": 0.15,
    "test_ratio": 0.15,
    "negative_ratio": 1,
    "k_values": [5, 10, 20],
    "directed_strategy": "out_out",
    "max_positive_pairs": 100,
    "ranking_negatives_per_query": 30,
    "hard_negative_fallback": "skip",
}


def main() -> None:
    started = perf_counter()
    output_dir = ROOT / "results" / "classical_baselines"
    output_dir.mkdir(parents=True, exist_ok=True)
    canonical = MGTABAdapter(ROOT / "data" / "raw" / "MGTAB").transform()
    task_builders = {"directed": DirectedConnectionTask(canonical, "friend"), "mutual": MutualConnectionTask(canonical, "friend")}
    scorer_factories = {"random": lambda graph: RandomScorer(graph, CONFIG["seed"]), "common_neighbors": CommonNeighborsScorer, "jaccard": JaccardScorer, "adamic_adar": AdamicAdarScorer, "preferential_attachment": PreferentialAttachmentScorer}
    rows, comparison_stats, validation_sanity = [], {}, []
    for task_name, builder in task_builders.items():
        task = builder.build()
        split = split_positive_links(task.positive_edges, CONFIG["train_ratio"], CONFIG["val_ratio"], CONFIG["test_ratio"], CONFIG["seed"])
        observed = build_observed_graph(task, torch.cat([split.val_pos, split.test_pos]))
        positives = split.test_pos[:CONFIG["max_positive_pairs"]]
        evaluator = ClassicalEvaluator(observed, task.positive_edges, CONFIG["seed"], tuple(CONFIG["k_values"]))
        # Validation is an untuned pipeline sanity check; test results below are
        # not used to alter task semantics or scorer configuration.
        validation_pos = split.val_pos[:CONFIG["max_positive_pairs"]]
        validation_evaluator = ClassicalEvaluator(observed, task.positive_edges, CONFIG["seed"], tuple(CONFIG["k_values"]))
        for validation_mode, validation_negatives in {
            "random": sample_random_negatives(task.num_nodes, task.positive_edges, task.directed, validation_pos.shape[0], CONFIG["seed"]),
            "hard": sample_hard_negatives(observed, validation_pos, task.positive_edges, TwoHopCandidateGenerator(observed), CONFIG["negative_ratio"], CONFIG["seed"], CONFIG["hard_negative_fallback"]).pairs,
        }.items():
            validation_scorer = CommonNeighborsScorer(observed)
            validation_sanity.append({"task": task_name, "negative_mode": validation_mode, "scorer": "common_neighbors", **validation_evaluator.evaluate_binary(validation_scorer, validation_pos, validation_negatives), **validation_evaluator.evaluate_ranking(validation_scorer, validation_pos, validation_mode, CONFIG["ranking_negatives_per_query"])})
        negative_sets = {
            "random": sample_random_negatives(task.num_nodes, task.positive_edges, task.directed, positives.shape[0], CONFIG["seed"]),
            "hard": sample_hard_negatives(observed, positives, task.positive_edges, TwoHopCandidateGenerator(observed), CONFIG["negative_ratio"], CONFIG["seed"], CONFIG["hard_negative_fallback"]),
        }
        for negative_mode, negatives_data in negative_sets.items():
            negatives = negatives_data if negative_mode == "random" else negatives_data.pairs
            for scorer_name, factory in scorer_factories.items():
                scorer = factory(observed)
                binary = evaluator.evaluate_binary(scorer, positives, negatives)
                ranking = evaluator.evaluate_ranking(scorer, positives, negative_mode, CONFIG["ranking_negatives_per_query"])
                row = {
                    "task": task_name, "negative_mode": negative_mode, "scorer": scorer_name,
                    "directed_strategy": scorer.directed_strategy, "seed": CONFIG["seed"],
                    "num_queries": ranking["num_queries"], "num_positive": int(positives.shape[0]), "num_negative": int(negatives.shape[0]),
                    **binary, **ranking,
                    "hard_negative_missing_sources": 0 if negative_mode == "random" else negatives_data.sources_without_enough_candidates,
                    "runtime_seconds": binary["binary_runtime_seconds"] + ranking["ranking_runtime_seconds"],
                }
                rows.append(row)
                if scorer_name == "random" and negative_mode == "hard":
                    comparison_stats[task_name] = {
                        **task_statistics(task),
                        "train_positives": int(split.train_pos.shape[0]),
                        "val_positives": int(split.val_pos.shape[0]),
                        "test_positives": int(split.test_pos.shape[0]),
                        **{key: row[key] for key in ("candidate_coverage", "avg_candidates", "median_candidates")},
                    }
    fieldnames = list(rows[0])
    with (output_dir / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    config = {**CONFIG, "runtime_seconds": perf_counter() - started, "evaluation_stage": "test_after_validation_pipeline_check"}
    (output_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (output_dir / "validation_sanity.json").write_text(json.dumps(validation_sanity, indent=2), encoding="utf-8")
    (ROOT / "docs" / "directed_vs_mutual_experiment.md").write_text(render_comparison(rows, comparison_stats, config), encoding="utf-8")
    print(f"Saved {len(rows)} experiment rows to {output_dir / 'results.csv'}")
    print(f"Total runtime: {config['runtime_seconds']:.2f}s")


if __name__ == "__main__":
    main()
