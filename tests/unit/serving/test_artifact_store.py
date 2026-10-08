import json

import pytest
import torch

from src.data import CanonicalGraph
from src.graph import GraphView
from src.serving import ActiveGraphRegistry, LocalArtifactStore, ServingGraphIndex


def _objects(*, directed: bool = True):
    node_ids = torch.tensor([10, 20, 30, 40])
    canonical = CanonicalGraph(
        node_ids=node_ids,
        node_features=torch.tensor([[1.0], [2.0], [3.0], [4.0]]),
        edge_index=torch.tensor([[0, 1, 2], [1, 2, 3]]),
        edge_type=torch.tensor([1, 1, 1]),
        edge_weight=torch.tensor([1.0, 1.0, 1.0]),
        labels={"example": torch.tensor([0, 1, 0, 1])},
        relation_schema={1: {"name": "friend", "directed": True}},
        metadata={"source": "unit-fixture"},
    )
    edges = torch.tensor([[0, 1, 2], [1, 2, 3]])
    view = GraphView(node_ids=node_ids, edge_index=edges, directed=directed)
    return canonical, view, ServingGraphIndex.from_graph_view(view)


def _save(store: LocalArtifactStore, version: str, *, directed: bool = True):
    canonical, view, index = _objects(directed=directed)
    return store.save_version(
        version,
        canonical,
        view,
        index,
        dataset_id="fixture-dataset",
        build_config={"seed": 42, "retrieval": {"candidate_cap": 5_000}},
    )


def test_save_load_round_trip_and_idempotent_reload(tmp_path):
    store = LocalArtifactStore(tmp_path / "artifacts")

    saved = _save(store, "graph-v1")
    first = store.load_version("graph-v1")
    second = store.load_version("graph-v1")

    assert saved.graph_version == "graph-v1"
    assert store.list_versions() == ("graph-v1",)
    assert first.manifest["dataset_id"] == "fixture-dataset"
    assert first.manifest["graph_semantics"] == "directed"
    assert first.serving_index.neighbors(10) == (20,)
    assert torch.equal(first.graph_view.edge_index, second.graph_view.edge_index)
    assert first.serving_index._adjacency == second.serving_index._adjacency
    with pytest.raises(FileExistsError):
        _save(store, "graph-v1")


@pytest.mark.parametrize("directed, expected", [(True, "directed"), (False, "mutual")])
def test_manifest_preserves_graph_semantics(tmp_path, directed, expected):
    store = LocalArtifactStore(tmp_path)

    bundle = _save(store, f"version-{expected}", directed=directed)

    assert bundle.manifest["graph_semantics"] == expected
    assert bundle.manifest["num_nodes"] == 4
    assert bundle.manifest["num_edges"] == 3


def test_missing_version_and_invalid_manifest_are_rejected(tmp_path):
    store = LocalArtifactStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.load_version("missing")
    _save(store, "bad-manifest")
    (store.version_path("bad-manifest") / "manifest.json").write_text("not json", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON"):
        store.validate_version("bad-manifest")

    _save(store, "missing-field")
    manifest_path = store.version_path("missing-field") / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["checksum"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required"):
        store.validate_version("missing-field")


def test_corrupted_artifact_and_incorrect_checksum_are_rejected(tmp_path):
    store = LocalArtifactStore(tmp_path)
    _save(store, "corrupt-data")
    (store.version_path("corrupt-data") / "canonical" / "tensors.pt").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="size mismatch|checksum"):
        store.load_version("corrupt-data")

    _save(store, "bad-checksum")
    manifest_path = store.version_path("bad-checksum") / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checksums"]["serving_index/tensors.pt"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        store.load_version("bad-checksum")


def test_missing_artifact_is_rejected(tmp_path):
    store = LocalArtifactStore(tmp_path)
    _save(store, "missing-file")
    (store.version_path("missing-file") / "serving_index" / "tensors.pt").unlink()

    with pytest.raises(ValueError, match="missing"):
        store.validate_version("missing-file")


def test_registry_activation_switch_and_failed_activation_preserves_old_version(tmp_path):
    store = LocalArtifactStore(tmp_path / "artifacts")
    registry = ActiveGraphRegistry(store, tmp_path / "registry")
    _save(store, "graph-n")
    _save(store, "graph-n-plus-1", directed=False)
    assert store.list_versions() == ("graph-n", "graph-n-plus-1")

    assert registry.get_active_version() is None
    registry.activate("graph-n")
    assert registry.get_active_version() == "graph-n"
    registry.activate("graph-n-plus-1")
    assert registry.get_active_version() == "graph-n-plus-1"
    assert store.load_version(registry.get_active_version()).manifest["graph_semantics"] == "mutual"

    _save(store, "invalid-next")
    (store.version_path("invalid-next") / "graph_view" / "tensors.pt").write_bytes(b"bad")
    with pytest.raises(ValueError):
        registry.activate("invalid-next")
    assert registry.get_active_version() == "graph-n-plus-1"


def test_registry_rejects_invalid_pointer_without_mutating_versions(tmp_path):
    store = LocalArtifactStore(tmp_path / "artifacts")
    registry = ActiveGraphRegistry(store, tmp_path / "registry")
    _save(store, "graph-v1")
    registry.registry_root.mkdir(parents=True)
    registry.pointer_path.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError, match="graph_version"):
        registry.get_active_version()
    assert store.list_versions() == ("graph-v1",)
