from pathlib import Path

import torch

from src.data.adapters import MGTABAdapter


DATASET_DIR = Path(__file__).parents[1] / "data" / "raw" / "MGTAB"


def test_mgtab_transform_preserves_shapes_and_relation_distribution():
    adapter = MGTABAdapter(DATASET_DIR)
    raw = adapter.load_raw()
    graph = adapter.transform()
    assert graph.num_nodes == raw["features"].shape[0]
    assert graph.num_edges == raw["edge_index"].shape[1]
    assert torch.equal(torch.bincount(raw["edge_type"].long()), torch.bincount(graph.edge_type))
    assert set(graph.labels) == {"bot", "stance"}


def test_mgtab_transform_does_not_mutate_raw_files():
    before = {path.name: path.stat().st_mtime_ns for path in DATASET_DIR.glob("*.pt")}
    MGTABAdapter(DATASET_DIR).transform()
    after = {path.name: path.stat().st_mtime_ns for path in DATASET_DIR.glob("*.pt")}
    assert before == after
