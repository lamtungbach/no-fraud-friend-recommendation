"""Create clean, mentor-facing visuals for the four Sprint 1 PYMK tasks."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.baselines import CommonNeighborsScorer
from src.candidates import TwoHopCandidateGenerator
from src.candidates.base import NeighborIndex
from src.data.adapters import MGTABAdapter
from src.split import build_observed_graph, split_positive_links
from src.tasks import MutualConnectionTask

OUT = ROOT / "results" / "sprint_1_demo"
COLORS = {"ink": "#172033", "muted": "#64748b", "line": "#cbd5e1", "teal": "#0f766e", "blue": "#2563eb", "amber": "#d97706", "green": "#16a34a", "red": "#dc2626", "soft": "#eff6ff"}


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(OUT / name, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def box(ax, x, y, width, height, title, subtitle, color):
    patch = FancyBboxPatch((x, y), width, height, boxstyle="round,pad=0.02,rounding_size=0.04", facecolor=color, edgecolor="none")
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height * 0.62, title, ha="center", va="center", color="white", fontsize=12, fontweight="bold")
    ax.text(x + width / 2, y + height * 0.30, subtitle, ha="center", va="center", color="white", fontsize=9)


def arrow(ax, start, end, label=""):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=15, linewidth=1.8, color=COLORS["muted"]))
    if label:
        ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.08, label, ha="center", color=COLORS["muted"], fontsize=8)


def task1_schema() -> None:
    fig, ax = plt.subplots(figsize=(13, 4))
    ax.set_xlim(0, 13); ax.set_ylim(0, 4); ax.axis("off")
    items = [
        (0.3, "Raw MGTAB", "6 .pt tensors", COLORS["muted"]),
        (3.2, "MGTABAdapter", "dataset-specific transform", COLORS["blue"]),
        (6.1, "CanonicalGraph", "standard input contract", COLORS["teal"]),
        (9.0, "PYMK engine", "task / candidate / scorer", COLORS["amber"]),
    ]
    for x, title, subtitle, color in items:
        box(ax, x, 1.55, 2.2, 1.0, title, subtitle, color)
    for x in (2.5, 5.4, 8.3):
        arrow(ax, (x, 2.05), (x + 0.65, 2.05))
    ax.text(6.5, 3.45, "Task 1 — Dataset is isolated behind a reusable schema", ha="center", fontsize=16, fontweight="bold", color=COLORS["ink"])
    ax.text(6.5, 0.65, "10,199 nodes  •  1,700,108 edges  •  788 features  •  7 relation types", ha="center", fontsize=11, color=COLORS["muted"])
    save(fig, "01_task1_schema_pipeline.png")


def task2_split() -> None:
    stats = json.loads((ROOT / "results" / "task_stats" / "split_stats.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), gridspec_kw={"width_ratios": [1.05, 1]})
    ax = axes[0]
    labels = ["Directed", "Mutual"]
    keys = ["directed", "mutual"]
    split_colors = [COLORS["teal"], COLORS["amber"], COLORS["red"]]
    split_names = ["train 70%", "validation 15%", "test 15% (hidden)"]
    for index, key in enumerate(keys):
        total = sum(stats[key][name] for name in ("train_size", "val_size", "test_size"))
        left = 0
        for part, color, name in zip(("train_size", "val_size", "test_size"), split_colors, split_names):
            value = stats[key][part] / total * 100
            ax.barh(index, value, left=left, color=color, height=0.48)
            if value > 11:
                ax.text(left + value / 2, index, f"{value:.0f}%", ha="center", va="center", color="white", fontweight="bold")
            left += value
    ax.set_xlim(0, 100); ax.set_yticks(range(2), labels); ax.set_xlabel("Positive links / pairs (%)")
    ax.set_title("Deterministic 70/15/15 split (seed 42)", loc="left", fontweight="bold", color=COLORS["ink"])
    ax.spines[["top", "right", "left"]].set_visible(False); ax.grid(axis="x", color=COLORS["line"], alpha=0.6); ax.set_axisbelow(True)
    ax.legend(handles=[Line2D([0], [0], color=c, lw=8, label=n) for c, n in zip(split_colors, split_names)], loc="lower center", bbox_to_anchor=(0.5, -0.32), ncol=3, frameon=False)

    ax = axes[1]; ax.axis("off")
    rows = [("Directed", stats["directed"]), ("Mutual", stats["mutual"])]
    ax.text(0, 1.03, "Leakage-safe observed graph", fontsize=14, fontweight="bold", color=COLORS["ink"], transform=ax.transAxes)
    ax.text(0, 0.89, "Validation + test positives are removed before scoring.", fontsize=10, color=COLORS["muted"], transform=ax.transAxes)
    for index, (label, row) in enumerate(rows):
        y = 0.58 - index * 0.35
        ax.text(0, y + 0.12, label, fontsize=11, fontweight="bold", color=COLORS["ink"], transform=ax.transAxes)
        ax.text(0, y, f"hidden positives: {row['hidden_positive_count']:,}", fontsize=10, transform=ax.transAxes)
        ax.text(0, y - 0.10, f"edge rows masked: {row['edges_removed_by_leakage_mask']:,}", fontsize=10, transform=ax.transAxes)
        ax.text(0.58, y, f"isolated after split: {row['isolated_nodes_after_split']:,}", fontsize=10, transform=ax.transAxes)
    fig.suptitle("Task 2 — Define the prediction target and prevent leakage", x=0.06, ha="left", fontsize=16, fontweight="bold", color=COLORS["ink"])
    fig.tight_layout()
    save(fig, "02_task2_split_and_leakage.png")


def select_top5_demo(observed, test_positives):
    generator = TwoHopCandidateGenerator(observed)
    scorer = CommonNeighborsScorer(observed)
    fallback = None
    for u, v in test_positives.tolist():
        for source, target in ((int(u), int(v)), (int(v), int(u))):
            pool = generator.generate(source)
            if target not in pool:
                continue
            ranked = sorted(pool, key=lambda node: (-scorer.score(source, node), node))
            item = (source, target, ranked[:5], scorer, pool)
            if target in ranked[:5]:
                return item
            fallback = fallback or item
    if fallback is None:
        raise RuntimeError("No retrievable held-out positive exists for the demo")
    return fallback


def task3_two_hop() -> None:
    canonical = MGTABAdapter(ROOT / "data" / "raw" / "MGTAB").transform()
    task = MutualConnectionTask(canonical, "friend").build()
    split = split_positive_links(task.positive_edges, seed=42)
    observed = build_observed_graph(task, torch.cat([split.val_pos, split.test_pos]))
    source, target, candidates, scorer, pool = select_top5_demo(observed, split.test_pos)
    neighbors = NeighborIndex(observed).neighbors

    candidate_bridges = {candidate: sorted(neighbors(source) & neighbors(candidate)) for candidate in candidates}
    bridge_priority = sorted(set().union(*candidate_bridges.values()))
    bridges = bridge_priority[:6]
    positions = {source: (0, 0)}
    for index, bridge in enumerate(bridges):
        positions[bridge] = (1.25, 2.3 - index * 0.9)
    for index, candidate in enumerate(candidates):
        positions[candidate] = (3.1, 2.0 - index * 1.0)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.axis("off"); ax.set_xlim(-0.55, 4.8); ax.set_ylim(-3.0, 3.0)
    for bridge in bridges:
        ax.plot([positions[source][0], positions[bridge][0]], [positions[source][1], positions[bridge][1]], color=COLORS["line"], linewidth=2, zorder=1)
    for candidate in candidates:
        for bridge in set(bridges) & set(candidate_bridges[candidate]):
            ax.plot([positions[bridge][0], positions[candidate][0]], [positions[bridge][1], positions[candidate][1]], color=COLORS["blue"], linewidth=2.3, zorder=1)
    ax.scatter(*positions[source], s=1700, color=COLORS["teal"], zorder=3)
    ax.text(-0.03, -0.05, f"Query\n{source}", color="white", ha="center", va="center", fontweight="bold", fontsize=10, zorder=4)
    for bridge in bridges:
        ax.scatter(*positions[bridge], s=720, color=COLORS["muted"], zorder=3)
        ax.text(*positions[bridge], f"Bridge\n{bridge}", color="white", ha="center", va="center", fontsize=8, zorder=4)
    for rank, candidate in enumerate(candidates, start=1):
        is_truth = candidate == target
        color = COLORS["green"] if is_truth else COLORS["amber"]
        ax.scatter(*positions[candidate], s=1200, color=color, zorder=3)
        label = f"#{rank}  {candidate}\nCN score = {scorer.score(source, candidate):.0f}"
        if is_truth:
            label += "\nheld-out positive"
        ax.text(positions[candidate][0] + 0.18, positions[candidate][1], label, va="center", fontsize=9, color=COLORS["ink"], fontweight="bold" if is_truth else "normal")
    ax.text(0, 2.75, "Query user", color=COLORS["teal"], fontweight="bold", fontsize=10)
    ax.text(1.25, 2.75, "Observed mutual bridges", color=COLORS["muted"], ha="center", fontweight="bold", fontsize=10)
    ax.text(3.1, 2.75, "Two-hop candidates ranked by Common Neighbors", color=COLORS["amber"], ha="center", fontweight="bold", fontsize=10)
    ax.set_title(f"Task 3 — Two-hop PYMK example: {len(pool):,} candidates, showing only the 6 strongest bridges", loc="left", fontsize=15, fontweight="bold", color=COLORS["ink"], pad=16)
    save(fig, "03_task3_two_hop_recommendation.png")


def task4_performance() -> None:
    frame = pd.read_csv(ROOT / "results" / "classical_baselines" / "results.csv")
    subset = frame[(frame.task == "mutual") & (frame.negative_mode == "hard")].copy()
    subset = subset.sort_values("ndcg_at_10")
    metrics = [("roc_auc", "ROC-AUC"), ("average_precision", "Average Precision"), ("ndcg_at_10", "NDCG@10")]
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), sharey=True)
    for ax, (column, title) in zip(axes, metrics):
        bars = ax.barh(subset.scorer, subset[column], color=[COLORS["teal"] if name == "adamic_adar" else COLORS["muted"] for name in subset.scorer])
        ax.set_xlim(0, 1); ax.set_title(title, fontweight="bold", color=COLORS["ink"])
        ax.grid(axis="x", color=COLORS["line"], alpha=0.6); ax.set_axisbelow(True); ax.spines[["top", "right", "left"]].set_visible(False)
        for bar, value in zip(bars, subset[column]):
            ax.text(min(value + 0.02, 0.98), bar.get_y() + bar.get_height() / 2, f"{value:.3f}", va="center", fontsize=9)
    fig.suptitle("Task 4 — Mutual task with hard two-hop negatives (most realistic benchmark)", x=0.05, ha="left", fontsize=16, fontweight="bold", color=COLORS["ink"])
    fig.text(0.05, 0.02, "Teal = Adamic-Adar. It leads AUC; Common Neighbors leads NDCG@10. NDCG@10 evaluates ordering quality in the shown top-10 recommendations.", color=COLORS["muted"], fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 0.91))
    save(fig, "04_task4_hard_negative_benchmark.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    task1_schema()
    task2_split()
    task3_two_hop()
    task4_performance()
    print(f"Saved Sprint 1 visuals to {OUT}")


if __name__ == "__main__":
    main()
