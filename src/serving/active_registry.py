"""Atomic active-version pointer for local/PVC graph artifacts."""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.serving.artifact_store import ArtifactStore


class ActiveGraphRegistry:
    """Maintain an atomically replaced pointer to a validated graph version.

    ``activate`` validates before writing.  The pointer is written to a unique
    temporary file in the same directory and swapped with ``os.replace``.
    Same-directory file replacement is atomically visible on standard Windows
    and POSIX local filesystems, so a failed validation or write leaves the
    previous pointer intact. The file is fsynced before replacement, but this
    is not a distributed lock or a full power-loss durability protocol.
    """

    def __init__(self, store: ArtifactStore, registry_root: str | Path):
        self.store = store
        self.registry_root = Path(registry_root)
        self.pointer_path = self.registry_root / "active.json"

    def get_active_version(self) -> str | None:
        """Return the active version ID, or ``None`` before first activation."""

        if not self.pointer_path.is_file():
            return None
        try:
            pointer = json.loads(self.pointer_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Active graph registry pointer is invalid") from error
        version = pointer.get("graph_version") if isinstance(pointer, dict) else None
        if not isinstance(version, str):
            raise TypeError("Active graph registry has no graph_version")
        return version

    def activate(self, graph_version: str) -> None:
        """Validate an immutable version, then atomically point the registry to it."""

        self.store.validate_version(graph_version)
        self.registry_root.mkdir(parents=True, exist_ok=True)
        temporary = self.registry_root / f".active-{uuid.uuid4().hex}.tmp"
        payload = {
            "registry_schema_version": "1",
            "graph_version": graph_version,
            "activated_at": datetime.now(UTC).isoformat(),
        }
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.pointer_path)
        finally:
            if temporary.exists():
                temporary.unlink()
