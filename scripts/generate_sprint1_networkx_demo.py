"""Render a small, real leakage-safe PYMK example for the Sprint 1 demo."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib
import networkx as nx
import torch

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.baselines import CommonNeighborsScorer
from src.candidates import TwoHopCandidateGenerator
from src.candidates.base import NeighborIndex
from src.data.adapters import MGTABAdapter
from src.split import build_observed_graph, split_positive_links
from src.tasks import MutualConnectionTask

SEED = 42
MAX_RECOMMENDATIONS = 5
MAX_BRIDGES = 6


def find_demo_query(test_positives, generator, scorer):
    """Pick a recoverable held-out positive that is visible in the shown top-K."""
    fallback = None
    for u, v in test_positives.tolist():
        for source, target in ((int(u), int(v)), (int(v), int(u))):
            pool = generator.generate(source)
            if target not in pool:
                continue
            ranked = sorted(pool, key=lambda node: (-scorer.score(source, node), node))
            target_rank = ranked.index(target) + 1
            candidate = (source, target, ranked, target_rank)
            if target_rank <= MAX_RECOMMENDATIONS:
                return candidate
            fallback = fallback or candidate
    if fallback is None:
        raise RuntimeError("No held-out mutual positive was found in the two-hop candidate pool")
    return fallback


def main() -> None:
    output_dir = ROOT / "results" / "sprint_1_demo"
    output_dir.mkdir(parents=True, exist_ok=True)

    canonical = MGTABAdapter(ROOT / "data" / "raw" / "MGTAB").transform()
    task = MutualConnectionTask(canonical, "friend").build()
    split = split_positive_links(task.positive_edges, seed=SEED)
    observed = build_observed_graph(task, torch.cat([split.val_pos, split.test_pos]))
    generator = TwoHopCandidateGenerator(observed)
    scorer = CommonNeighborsScorer(observed)
    source, held_out_target, ranked, held_out_rank = find_demo_query(split.test_pos, generator, scorer)
    pool = generator.generate(source)
    recommendations = ranked[:MAX_RECOMMENDATIONS]

    neighbors = NeighborIndex(observed).neighbors
    bridge_scores = {
        bridge: sum(bridge in neighbors(candidate) for candidate in recommendations)
        for bridge in neighbors(source)
    }
    bridges = sorted(bridge_scores, key=lambda node: (-bridge_scores[node], node))[:MAX_BRIDGES]

    graph = nx.Graph()
    graph.add_node(source, role="source")
    for bridge in bridges:
        graph.add_node(bridge, role="bridge")
        graph.add_edge(source, bridge)
    for candidate in recommendations:
        role = "held_out_positive" if candidate == held_out_target else "recommendation"
        graph.add_node(candidate, role=role, score=scorer.score(source, candidate))
        for bridge in bridges:
            if bridge in neighbors(candidate):
                graph.add_edge(bridge, candidate)

    # Fixed three-column layout is intentionally used instead of a force layout:
    # it makes the two-hop explanation readable in a mentor report.
    def vertical_positions(count: int, extent: float) -> list[float]:
        if count == 1:
            return [0.0]
        return [extent - index * (2 * extent / (count - 1)) for index in range(count)]

    positions = {source: (0.0, 0.0)}
    positions.update({bridge: (3.1, y) for bridge, y in zip(bridges, vertical_positions(len(bridges), 2.7))})
    positions.update({candidate: (6.8, y) for candidate, y in zip(recommendations, vertical_positions(len(recommendations), 2.25))})

    figure, axis = plt.subplots(figsize=(15, 8.5))
    source_edges = [(source, bridge) for bridge in bridges]
    candidate_edges = [(bridge, candidate) for bridge, candidate in graph.edges() if bridge != source and candidate != source]
    nx.draw_networkx_edges(graph, positions, edgelist=source_edges, edge_color="#cbd5e1", width=2.3, alpha=0.95, ax=axis)
    nx.draw_networkx_edges(graph, positions, edgelist=candidate_edges, edge_color="#2563eb", width=2.0, alpha=0.72, ax=axis)

    nx.draw_networkx_nodes(graph, positions, nodelist=[source], node_color="#0f766e", node_size=2300, edgecolors="white", linewidths=2.2, ax=axis)
    nx.draw_networkx_nodes(graph, positions, nodelist=bridges, node_color="#64748b", node_size=1150, edgecolors="white", linewidths=1.8, ax=axis)
    standard_recommendations = [candidate for candidate in recommendations if candidate != held_out_target]
    nx.draw_networkx_nodes(graph, positions, nodelist=standard_recommendations, node_color="#d97706", node_size=1550, edgecolors="white", linewidths=2.2, ax=axis)
    if held_out_target in recommendations:
        nx.draw_networkx_nodes(graph, positions, nodelist=[held_out_target], node_color="#16a34a", node_size=1750, edgecolors="white", linewidths=2.5, ax=axis)

    # Keep labels outside circles: Vietnamese text stays legible in the exported PNG.
    axis.text(-0.38, 0.0, "Người dùng\ncần gợi ý", va="center", ha="right", fontsize=11, fontweight="bold", color="#0f766e")
    for index, bridge in enumerate(bridges, start=1):
        x, y = positions[bridge]
        axis.text(x, y - 0.43, f"Bạn chung {index}", va="top", ha="center", fontsize=9, color="#475569")
    for rank, candidate in enumerate(recommendations, start=1):
        x, y = positions[candidate]
        score = scorer.score(source, candidate)
        if candidate == held_out_target:
            label = f"Kết nối thật đã ẩn\nHạng #{rank}  •  CN = {score:.0f}"
            weight = "bold"
        else:
            label = f"Gợi ý #{rank}\nCN = {score:.0f}"
            weight = "normal"
        axis.text(x + 0.34, y, label, va="center", ha="left", fontsize=11, fontweight=weight, color="#172033")

    axis.text(0.0, 3.35, "Người dùng truy vấn", ha="center", fontsize=12, fontweight="bold", color="#0f766e")
    axis.text(3.1, 3.35, "Bạn chung đã quan sát", ha="center", fontsize=12, fontweight="bold", color="#64748b")
    axis.text(6.8, 3.35, "Ứng viên gợi ý hai bước", ha="center", fontsize=12, fontweight="bold", color="#c66a00")
    legend_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#0f766e", markersize=12, label="Người dùng cần gợi ý"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#64748b", markersize=12, label="Bạn chung đã quan sát"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#d97706", markersize=12, label="Ứng viên trong top 5"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#16a34a", markersize=12, label="Kết nối thật đã ẩn (nhãn đúng)"),
    ]
    axis.legend(handles=legend_handles, loc="lower center", bbox_to_anchor=(0.5, -0.13), ncol=2, frameon=False, fontsize=10)
    axis.set_title("Ví dụ gợi ý kết bạn hai bước, an toàn khỏi rò rỉ dữ liệu (MGTAB)", fontsize=17, fontweight="bold", pad=28)
    axis.text(0.5, 1.01, "Chỉ hiển thị 6 bạn chung có liên kết mạnh nhất và 5 ứng viên xếp hạng đầu. CN = số bạn chung.", transform=axis.transAxes, ha="center", fontsize=10, color="#475569")
    axis.set_xlim(-1.3, 10.1)
    axis.set_ylim(-3.25, 3.75)
    axis.axis("off")
    figure.tight_layout()
    image_path = output_dir / "networkx_mutual_pymk_example.png"
    plt.savefig(image_path, dpi=180, bbox_inches="tight")
    plt.close()

    summary = {
        "seed": SEED,
        "task": "mutual_connection",
        "source_user": source,
        "held_out_positive": held_out_target,
        "held_out_positive_rank": held_out_rank,
        "two_hop_candidate_count": len(pool),
        "shown_bridges": bridges,
        "recommendations": [
            {"rank": rank, "node_id": node, "common_neighbors_score": scorer.score(source, node), "is_held_out_positive": node == held_out_target}
            for rank, node in enumerate(recommendations, start=1)
        ],
        "image": image_path.relative_to(ROOT).as_posix(),
    }
    summary_path = output_dir / "networkx_mutual_pymk_example.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Saved NetworkX graph: {image_path}")
    print(f"Saved demo metadata: {summary_path}")


if __name__ == "__main__":
    main()
