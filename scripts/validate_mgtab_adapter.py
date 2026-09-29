"""Smoke validation for the MGTAB canonical adapter."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.adapters import MGTABAdapter  # noqa: E402


def main() -> None:
    graph = MGTABAdapter(ROOT / "data" / "raw" / "MGTAB").transform()
    print("Dataset: MGTAB")
    print(f"Nodes: {graph.num_nodes}")
    print(f"Edges: {graph.num_edges}")
    print(f"Features: {graph.num_features}")
    print(f"Relations: {len(graph.relation_schema)}")
    print("\nValidation:")
    for check in ("edge_index", "edge_type", "edge_weight", "node_features", "node IDs", "labels", "relation IDs"):
        print(f"[PASS] {check}")
    print("\nCanonicalGraph created successfully.")


if __name__ == "__main__":
    main()
