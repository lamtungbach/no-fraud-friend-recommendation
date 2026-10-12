# Phase 08 local guide

Phase 08 owns the offline DatasetAdapter-to-immutable-graph/index lifecycle.
It does not change the Trust/R-GCN algorithm, Phase 07's fail-closed Trust
boundary, or the raw-PYMK-only cache rule.

## Metadata database

PostgreSQL stores metadata only: dataset identity, jobs, graph-version facts,
the active version pointer, and the transactional event outbox. It never stores
graph adjacency/tensors for request-time retrieval. Apply the migration before
constructing `PostgresMetadataRepository`:

```powershell
psql $env:POSTGRES_DSN -f migrations/0001_phase08_metadata.sql
```

Install a PostgreSQL DB-API driver explicitly in deployments (for example,
`psycopg[binary]`), then construct `PostgresMetadataRepository.from_dsn(...)`.
There is deliberately no production fallback to in-memory metadata. Tests pass
`InMemoryMetadataRepository` and `InMemoryEventPublisher` explicitly.

For a local Docker-backed verification, start PostgreSQL and wait until it
accepts connections. Use a local-only password; never commit it or place it in
source code:

```powershell
docker run -d --name pymk-postgres --restart unless-stopped `
  -e POSTGRES_DB=pymk -e POSTGRES_USER=pymk -e POSTGRES_PASSWORD=<local-password> `
  -p 127.0.0.1:5432:5432 postgres:16-alpine
docker exec pymk-postgres pg_isready -U pymk -d pymk
Get-Content migrations/0001_phase08_metadata.sql -Raw |
  docker exec -i pymk-postgres psql -v ON_ERROR_STOP=1 -U pymk -d pymk
```

## Lifecycle and recovery

`BatchOrchestrator` moves jobs through `PENDING -> RUNNING -> VALIDATING ->
PERSISTING -> READY`, or to `FAILED` from any non-terminal state. It validates
the canonical graph, writes and revalidates an immutable artifact, records
metadata, then transactionally updates `active_versions` and inserts an outbox
event. If publishing fails, the version remains active and
`retry_pending_events()` republishes the identical `event_id` safely.

`ServingIndexReloader` independently loads/checks the immutable artifact,
warms it, and only then replaces `ActiveIndexHolder`. Consumers deduplicate by
event ID after a successful reload; a corrupt artifact therefore leaves the
previous in-memory index untouched.

`ApiRuntime` owns that holder and passes it to `RecommendationEngine`, so a
consumer calling `runtime.consume_graph_index_ready(event)` now performs the
actual serving handover: validate/warm → atomically replace the in-memory
snapshot → update the durable local registry. On startup,
`runtime.warm_active_index()` reconstructs the holder from that registry.
For local integration, explicitly connect `InMemoryEventPublisher.subscribe(
runtime.consume_graph_index_ready)`; a production broker adapter must invoke
the same runtime entry point after deserializing the event. Pass the metadata
repository's `active_version` method as `active_version_provider` when building
the runtime; this rejects an out-of-order event whose version is no longer
authoritative.

The existing Prometheus endpoint also exposes low-cardinality
`pipeline_job_transitions_total` and `graph_index_reloads_total` counters. They
contain only statuses/outcomes, never IDs, raw datasets, adjacency, or candidate
lists.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/pipeline -q
.\.venv\Scripts\python.exe -m ruff check src/pipeline tests/unit/pipeline
```

PostgreSQL integration is deliberately opt-in, so the normal unit suite uses
the clearly injected metadata/event test doubles. After provisioning PostgreSQL
and applying the migration, run:

```powershell
$env:POSTGRES_DSN = 'postgresql://...'
$env:RUN_POSTGRES_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_postgres_metadata.py -q
```

The PostgreSQL integration suite covers both the repository round-trip and the
full `PENDING -> ... -> READY` batch/artifact/outbox lifecycle. It is opt-in so
normal contributors can run unit tests without a database.
