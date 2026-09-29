"""Markdown report rendering for the Task 4 comparison."""

from __future__ import annotations


def render_comparison(results: list[dict], task_stats: dict, config: dict) -> str:
    lines = ["# Directed vs Mutual classical experiment", "", "## Protocol", "", "This is a reproducible leakage-safe link reconstruction / missing-link proxy, not temporal future friendship prediction.", "", f"- Seed: `{config['seed']}`", f"- Test-positive sample cap per task: `{config['max_positive_pairs']}`", f"- Ranking policy: evaluate query orientations with a hidden positive in the two-hop pool; uncovered positives count in candidate coverage but are not rankable.", "", "## Task statistics", "", "| Metric | Directed | Mutual |", "|---|---:|---:|"]
    for key, label in [("num_nodes", "Nodes"), ("num_positive_edges_or_pairs", "Positive links/pairs"), ("num_nodes_with_at_least_one_target_connection", "Active nodes"), ("average_degree", "Average degree"), ("candidate_coverage", "Candidate coverage"), ("avg_candidates", "Average candidates/query")]:
        directed = task_stats["directed"].get(key, "-")
        mutual = task_stats["mutual"].get(key, "-")
        lines.append(f"| {label} | {directed} | {mutual} |")
    lines += ["", "## Performance", "", "| Task | Negative | Method | AUC | AP | Recall@10 | NDCG@10 | Hits@10 | MRR |", "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in results:
        lines.append(f"| {row['task']} | {row['negative_mode']} | {row['scorer']} | {row['roc_auc']:.4f} | {row['average_precision']:.4f} | {row['recall_at_10']:.4f} | {row['ndcg_at_10']:.4f} | {row['hits_at_10']:.4f} | {row['mrr']:.4f} |")
    lines += ["", "## Interpretation", "", "Random negatives are generally easier than two-hop hard negatives, so a drop under hard negatives is expected rather than evidence of a bug. Mutual remains the closer app proxy for reciprocal friend/chat relationships; directed remains a useful auxiliary benchmark. The final task choice should consider sparsity, candidate coverage, and product semantics alongside metrics."]
    return "\n".join(lines) + "\n"
