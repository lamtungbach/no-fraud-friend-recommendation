"""Script build and activate MGTAB graph artifact."""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.adapters import MGTABAdapter  # noqa: E402
from src.graph import build_pymk_graph_view  # noqa: E402
from src.serving import (  # noqa: E402
    ActiveGraphRegistry,
    LocalArtifactStore,
    ServingGraphIndex,
)


def main() -> None:
    start_time = time.perf_counter()
    raw_dir = ROOT / "data" / "raw" / "MGTAB"
    artifact_root = ROOT / "artifacts"
    registry_root = artifact_root / "registry"
    version = "mgtab-v1"

    print(f"=== Starting build for graph artifact version: {version} ===")
    print(f"1. Loading MGTAB dataset from: {raw_dir}")
    adapter = MGTABAdapter(raw_dir)
    graph = adapter.transform()
    adapter.validate(graph)
    print(f"   -> Valid canonical graph: {graph.num_nodes} nodes, {graph.num_edges} edges")

    print("2. Building Directed Graph View & CSR Serving Index...")
    view = build_pymk_graph_view(graph, mode="directed")
    index = ServingGraphIndex.from_graph_view(view)
    print("   -> CSR Index built successfully.")

    print(f"3. Persisting Immutable Artifact: {version}...")
    store = LocalArtifactStore(artifact_root)
    bundle = store.save_version(version, graph, view, index, dataset_id="MGTAB")
    checksum = str(bundle.manifest.get("checksum", ""))[:12]
    print(f"   -> Saved successfully! Checksum: {checksum}...")

    print(f"4. Activating {version} in Active Registry...")
    registry = ActiveGraphRegistry(store, registry_root)
    registry.activate(version)
    print(f"   -> Active Graph pointer is now: {registry.get_active_version()}")

    elapsed = time.perf_counter() - start_time
    print(f"=== All done in {elapsed:.2f} seconds! ===")


if __name__ == "__main__":
    main()
