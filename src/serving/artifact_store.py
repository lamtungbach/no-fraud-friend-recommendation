"""Immutable local/PVC graph artifact storage.

Only tensor dictionaries and JSON metadata are persisted.  Artifact loading
uses ``torch.load(..., weights_only=True)`` so this store never unpickles an
arbitrary Python object from an untrusted artifact directory.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import torch

from src.data import CanonicalGraph
from src.graph import GraphView
from src.serving.graph_index import ServingGraphIndex

MANIFEST_SCHEMA_VERSION = "1"
INDEX_SCHEMA_VERSION = "1"
_FINALIZED_MARKER = ".finalized"
_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_ARTIFACT_FILES = (
    "canonical/tensors.pt",
    "canonical/metadata.json",
    "graph_view/tensors.pt",
    "graph_view/metadata.json",
    "serving_index/tensors.pt",
)


@dataclass(frozen=True)
class ArtifactBundle:
    """Loaded, validated objects belonging to one immutable graph version."""

    graph_version: str
    canonical_graph: CanonicalGraph
    graph_view: GraphView
    serving_index: ServingGraphIndex
    manifest: dict[str, object]


class ArtifactStore(ABC):
    """Storage boundary that future PVC/object-store backends can implement."""

    @abstractmethod
    def save_version(
        self,
        graph_version: str,
        canonical_graph: CanonicalGraph,
        graph_view: GraphView,
        serving_index: ServingGraphIndex,
        *,
        dataset_id: str,
        build_config: Mapping[str, object] | None = None,
    ) -> ArtifactBundle:
        raise NotImplementedError

    @abstractmethod
    def load_version(self, graph_version: str) -> ArtifactBundle:
        raise NotImplementedError

    @abstractmethod
    def validate_version(self, graph_version: str) -> ArtifactBundle:
        raise NotImplementedError

    @abstractmethod
    def list_versions(self) -> tuple[str, ...]:
        raise NotImplementedError


class LocalArtifactStore(ArtifactStore):
    """Filesystem artifact store usable on a local disk or a mounted PVC.

    Each finalized directory is logically immutable: ``save_version`` refuses
    an existing version ID.  A version is written to a sibling staging
    directory, validated, marked finalized, then renamed into place.  Directory
    rename is atomic when source and destination share one filesystem on both
    Windows and POSIX filesystems.  It is not a distributed-filesystem lock;
    concurrent writers must use different version IDs or external coordination.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.versions_root = self.root / "graph"

    def save_version(
        self,
        graph_version: str,
        canonical_graph: CanonicalGraph,
        graph_view: GraphView,
        serving_index: ServingGraphIndex,
        *,
        dataset_id: str,
        build_config: Mapping[str, object] | None = None,
    ) -> ArtifactBundle:
        """Validate, persist, finalize, and return one immutable version."""

        self._validate_version_id(graph_version)
        if not dataset_id:
            raise ValueError("dataset_id must be non-empty")
        self._validate_objects(canonical_graph, graph_view, serving_index)
        self.versions_root.mkdir(parents=True, exist_ok=True)
        final_path = self._version_path(graph_version)
        if final_path.exists():
            raise FileExistsError(f"Artifact version already finalized: {graph_version}")
        staging = self.versions_root / f".staging-{graph_version}-{uuid.uuid4().hex}"
        try:
            self._write_artifacts(staging, canonical_graph, graph_view, serving_index)
            manifest = self._build_manifest(
                staging,
                graph_version,
                dataset_id,
                graph_view,
                canonical_graph,
                build_config or {},
            )
            self._write_json(staging / "manifest.json", manifest)
            self._validate_directory(
                staging, require_finalized=False, expected_version=graph_version
            )
            self._write_json(staging / _FINALIZED_MARKER, {"graph_version": graph_version})
            # ``rename`` refuses an existing target directory, preventing an
            # accidental overwrite of a finalized version on Windows/Linux.
            staging.rename(final_path)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise
        return self.load_version(graph_version)

    def load_version(self, graph_version: str) -> ArtifactBundle:
        """Load only a version that passes all integrity and smoke checks."""

        return self.validate_version(graph_version)

    def validate_version(self, graph_version: str) -> ArtifactBundle:
        """Validate manifest, checksums, schemas, index parity, and smoke query."""

        self._validate_version_id(graph_version)
        path = self._version_path(graph_version)
        if not path.is_dir():
            raise FileNotFoundError(f"Artifact version does not exist: {graph_version}")
        return self._validate_directory(path, require_finalized=True)

    def list_versions(self) -> tuple[str, ...]:
        """Return only finalized version IDs in deterministic lexical order."""

        if not self.versions_root.is_dir():
            return ()
        return tuple(
            sorted(
                path.name
                for path in self.versions_root.iterdir()
                if path.is_dir() and (path / _FINALIZED_MARKER).is_file()
            )
        )

    def version_path(self, graph_version: str) -> Path:
        """Expose the finalized path for diagnostics; never for mutation."""

        self._validate_version_id(graph_version)
        return self._version_path(graph_version)

    def _version_path(self, graph_version: str) -> Path:
        return self.versions_root / graph_version

    @staticmethod
    def _validate_version_id(graph_version: str) -> None:
        if not isinstance(graph_version, str) or not _VERSION_PATTERN.fullmatch(graph_version):
            raise ValueError("graph_version must be 1-128 safe filename characters")

    def _write_artifacts(
        self,
        path: Path,
        canonical_graph: CanonicalGraph,
        graph_view: GraphView,
        serving_index: ServingGraphIndex,
    ) -> None:
        (path / "canonical").mkdir(parents=True)
        (path / "graph_view").mkdir()
        (path / "serving_index").mkdir()
        self._write_tensors(
            path / "canonical" / "tensors.pt",
            {
                "node_ids": canonical_graph.node_ids,
                "edge_index": canonical_graph.edge_index,
                "edge_type": canonical_graph.edge_type,
                "node_features": canonical_graph.node_features,
                "edge_weight": canonical_graph.edge_weight,
                "labels": canonical_graph.labels,
            },
        )
        self._write_json(
            path / "canonical" / "metadata.json",
            {
                "relation_schema": [
                    {"relation_id": relation_id, "schema": schema}
                    for relation_id, schema in sorted(canonical_graph.relation_schema.items())
                ],
                "metadata": canonical_graph.metadata,
            },
        )
        self._write_tensors(
            path / "graph_view" / "tensors.pt",
            {"node_ids": graph_view.node_ids, "edge_index": graph_view.edge_index},
        )
        self._write_json(path / "graph_view" / "metadata.json", {"directed": graph_view.directed})
        self._write_tensors(
            path / "serving_index" / "tensors.pt",
            {
                "offsets": torch.tensor(serving_index._offsets, dtype=torch.long),
                "adjacency": torch.tensor(serving_index._adjacency, dtype=torch.long),
            },
        )

    def _build_manifest(
        self,
        path: Path,
        graph_version: str,
        dataset_id: str,
        graph_view: GraphView,
        canonical_graph: CanonicalGraph,
        build_config: Mapping[str, object],
    ) -> dict[str, object]:
        # JSON conversion is deliberately strict: arbitrary Python metadata is
        # not a portable or safe artifact format.
        try:
            build_config_json = json.loads(json.dumps(dict(build_config), sort_keys=True))
        except TypeError as error:
            raise ValueError("build_config must contain JSON-compatible values") from error
        checksums = {relative: self._sha256(path / relative) for relative in _ARTIFACT_FILES}
        sizes = {relative: (path / relative).stat().st_size for relative in _ARTIFACT_FILES}
        aggregate = self._aggregate_checksum(checksums)
        return {
            "artifact_store_schema_version": MANIFEST_SCHEMA_VERSION,
            "graph_version": graph_version,
            "dataset_id": dataset_id,
            "created_at": datetime.now(UTC).isoformat(),
            "graph_semantics": "directed" if graph_view.directed else "mutual",
            "num_nodes": graph_view.num_nodes,
            "num_edges": graph_view.num_edges,
            "canonical_num_edges": canonical_graph.num_edges,
            "index_schema_version": INDEX_SCHEMA_VERSION,
            "build_config": build_config_json,
            "checksums": checksums,
            "artifact_sizes": sizes,
            "checksum": aggregate,
        }

    def _validate_directory(
        self,
        path: Path,
        *,
        require_finalized: bool,
        expected_version: str | None = None,
    ) -> ArtifactBundle:
        manifest_path = path / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError("Artifact manifest is missing")
        manifest = self._read_json(manifest_path)
        self._validate_manifest(manifest, expected_version or path.name)
        if require_finalized:
            marker = self._read_json(path / _FINALIZED_MARKER)
            if marker.get("graph_version") != manifest["graph_version"]:
                raise ValueError("Finalization marker does not match manifest")
        checksums = manifest["checksums"]
        for relative in _ARTIFACT_FILES:
            artifact = path / relative
            if not artifact.is_file():
                raise ValueError(f"Artifact is missing: {relative}")
            if artifact.stat().st_size != manifest["artifact_sizes"][relative]:
                raise ValueError(f"Artifact size mismatch: {relative}")
            if self._sha256(artifact) != checksums[relative]:
                raise ValueError(f"Artifact checksum mismatch: {relative}")
        if self._aggregate_checksum(checksums) != manifest["checksum"]:
            raise ValueError("Manifest aggregate checksum mismatch")
        bundle = self._load_bundle(path, manifest)
        self._validate_objects(
            bundle.canonical_graph, bundle.graph_view, bundle.serving_index
        )
        if bundle.graph_view.directed != (manifest["graph_semantics"] == "directed"):
            raise ValueError("Manifest graph semantics does not match graph view")
        if bundle.graph_view.num_nodes != manifest["num_nodes"] or bundle.graph_view.num_edges != manifest["num_edges"]:
            raise ValueError("Manifest node/edge counts do not match graph view")
        if bundle.canonical_graph.num_edges != manifest["canonical_num_edges"]:
            raise ValueError("Manifest canonical edge count does not match artifact")
        if bundle.serving_index.num_nodes() > 0:
            first_id = bundle.graph_view.node_ids[0].item()
            bundle.serving_index.neighbors(first_id)
            bundle.serving_index.degree(first_id)
        return bundle

    def _load_bundle(self, path: Path, manifest: dict[str, object]) -> ArtifactBundle:
        canonical_tensors = self._read_tensors(path / "canonical" / "tensors.pt")
        canonical_metadata = self._read_json(path / "canonical" / "metadata.json")
        relation_schema = {
            int(entry["relation_id"]): entry["schema"]
            for entry in canonical_metadata["relation_schema"]
        }
        canonical = CanonicalGraph(
            node_ids=canonical_tensors["node_ids"],
            node_features=canonical_tensors.get("node_features"),
            edge_index=canonical_tensors["edge_index"],
            edge_type=canonical_tensors["edge_type"],
            edge_weight=canonical_tensors.get("edge_weight"),
            labels=canonical_tensors.get("labels", {}),
            relation_schema=relation_schema,
            metadata=canonical_metadata["metadata"],
        )
        view_tensors = self._read_tensors(path / "graph_view" / "tensors.pt")
        view_metadata = self._read_json(path / "graph_view" / "metadata.json")
        view = GraphView(
            node_ids=view_tensors["node_ids"],
            edge_index=view_tensors["edge_index"],
            directed=view_metadata["directed"],
        )
        index = ServingGraphIndex.from_graph_view(view)
        stored_index = self._read_tensors(path / "serving_index" / "tensors.pt")
        expected_offsets = torch.tensor(index._offsets, dtype=torch.long)
        expected_adjacency = torch.tensor(index._adjacency, dtype=torch.long)
        if not torch.equal(stored_index["offsets"], expected_offsets) or not torch.equal(
            stored_index["adjacency"], expected_adjacency
        ):
            raise ValueError("Stored index tensors do not match graph view")
        return ArtifactBundle(
            graph_version=str(manifest["graph_version"]),
            canonical_graph=canonical,
            graph_view=view,
            serving_index=index,
            manifest=manifest,
        )

    @staticmethod
    def _validate_objects(
        canonical_graph: CanonicalGraph,
        graph_view: GraphView,
        serving_index: ServingGraphIndex,
    ) -> None:
        if not torch.equal(canonical_graph.node_ids, graph_view.node_ids):
            raise ValueError("CanonicalGraph and GraphView node_ids differ")
        rebuilt_index = ServingGraphIndex.from_graph_view(graph_view)
        if (
            serving_index._internal_to_external != rebuilt_index._internal_to_external
            or serving_index._offsets != rebuilt_index._offsets
            or serving_index._adjacency != rebuilt_index._adjacency
            or serving_index.num_edges() != rebuilt_index.num_edges()
        ):
            raise ValueError("ServingGraphIndex is incompatible with GraphView")

    @staticmethod
    def _validate_manifest(manifest: object, expected_version: str) -> None:
        if not isinstance(manifest, dict):
            raise TypeError("Manifest must be a JSON object")
        required = {
            "artifact_store_schema_version",
            "graph_version",
            "dataset_id",
            "created_at",
            "graph_semantics",
            "num_nodes",
            "num_edges",
            "canonical_num_edges",
            "index_schema_version",
            "build_config",
            "checksums",
            "artifact_sizes",
            "checksum",
        }
        missing = required - manifest.keys()
        if missing:
            raise ValueError(f"Manifest is missing required fields: {sorted(missing)}")
        if manifest["artifact_store_schema_version"] != MANIFEST_SCHEMA_VERSION:
            raise ValueError("Unsupported artifact store schema")
        if manifest["index_schema_version"] != INDEX_SCHEMA_VERSION:
            raise ValueError("Unsupported index schema")
        if manifest["graph_version"] != expected_version:
            raise ValueError("Manifest graph_version does not match directory")
        if manifest["graph_semantics"] not in {"directed", "mutual"}:
            raise ValueError("Manifest graph_semantics is invalid")
        if not isinstance(manifest["num_nodes"], int) or not isinstance(manifest["num_edges"], int):
            raise TypeError("Manifest counts must be integers")
        if set(manifest["checksums"]) != set(_ARTIFACT_FILES) or set(
            manifest["artifact_sizes"]
        ) != set(_ARTIFACT_FILES):
            raise ValueError("Manifest artifact file set is invalid")

    @staticmethod
    def _write_tensors(path: Path, tensors: dict[str, object]) -> None:
        torch.save(tensors, path)

    @staticmethod
    def _read_tensors(path: Path) -> dict[str, object]:
        try:
            value = torch.load(path, map_location="cpu", weights_only=True)
        except Exception as error:
            raise ValueError(f"Unable to safely load tensor artifact: {path.name}") from error
        if not isinstance(value, dict):
            raise TypeError(f"Tensor artifact must contain a dictionary: {path.name}")
        return value

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def _read_json(path: Path) -> dict[str, object]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Unable to read JSON artifact: {path.name}") from error
        if not isinstance(value, dict):
            raise TypeError(f"JSON artifact must be an object: {path.name}")
        return value

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _aggregate_checksum(checksums: Mapping[str, object]) -> str:
        encoded = json.dumps(dict(checksums), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
