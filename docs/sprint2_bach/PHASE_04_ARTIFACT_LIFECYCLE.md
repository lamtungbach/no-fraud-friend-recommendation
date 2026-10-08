# Phase 04 Artifact Lifecycle

## Local/PVC layout

`LocalArtifactStore(root)` writes one finalized version below `root/graph`:

```text
root/
  graph/
    graph-v2026-10-08/
      canonical/tensors.pt
      canonical/metadata.json
      graph_view/tensors.pt
      graph_view/metadata.json
      serving_index/tensors.pt
      manifest.json
      .finalized
  registry/
    active.json
```

`tensors.pt` files contain tensor dictionaries only. Loading uses
`torch.load(..., weights_only=True)`; the store does not unpickle arbitrary
Python objects. JSON sidecars hold portable metadata.

## Manifest example

```json
{
  "artifact_store_schema_version": "1",
  "graph_version": "graph-v2026-10-08",
  "dataset_id": "generic-social-graph",
  "created_at": "2026-10-08T00:00:00+00:00",
  "graph_semantics": "directed",
  "num_nodes": 10199,
  "num_edges": 252759,
  "canonical_num_edges": 252759,
  "index_schema_version": "1",
  "build_config": {"retrieval": {"candidate_cap": 5000}},
  "checksums": {"canonical/tensors.pt": "sha256..."},
  "artifact_sizes": {"canonical/tensors.pt": 12345},
  "checksum": "aggregate-sha256..."
}
```

The real manifest includes a SHA-256 and byte size for every persisted file:
canonical tensors/metadata, graph-view tensors/metadata, and index tensors.
The aggregate checksum covers the checksum map itself.

## Lifecycle and recovery

```text
build graph/view/index
  -> save to unique .staging-{version}-{uuid}
  -> validate manifest, checksums, schema, index parity, smoke query
  -> write .finalized marker
  -> rename staging directory to immutable version path
  -> validate version again
  -> atomically replace registry/active.json only after validation
  -> load active version
```

`save_version()` refuses an existing finalized version ID, so the public API
does not overwrite an artifact. Direct filesystem tampering is detected by
size/checksum/index validation.

`ActiveGraphRegistry.activate(version)` validates the target before it writes
the pointer. It writes a unique temporary pointer in the same directory and
uses `Path.replace()` (`os.replace`) to update `active.json` after flushing and
fsyncing the temporary pointer file. On ordinary local Windows NTFS and POSIX
filesystems, same-directory file replacement is atomically visible: a
validation or write failure leaves the old pointer in place. This improves
durability but is not a full power-loss transaction (directory/fsync semantics
vary by filesystem); startup must still validate the selected version. A crash
can leave an ignored temporary pointer.

This is a local/PVC guarantee, not a distributed lock or consensus protocol.
Multiple concurrent writers need external coordination. Checksums detect
accidental corruption, not a malicious writer who can replace both payload and
manifest. A future object-store backend can implement the same `ArtifactStore`
interface without changing graph/retrieval/ranking algorithms.
