-- Phase 08: metadata and transactional outbox only.  Graph adjacency and
-- tensor/index content remain immutable artifacts outside PostgreSQL.
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id TEXT PRIMARY KEY,
    source_identity TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pipeline_jobs (
    job_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
    graph_version TEXT NOT NULL UNIQUE,
    graph_semantics TEXT NOT NULL CHECK (graph_semantics IN ('directed', 'mutual')),
    build_config JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING','RUNNING','VALIDATING','PERSISTING','READY','FAILED')),
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS graph_versions (
    graph_version TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
    job_id TEXT NOT NULL UNIQUE REFERENCES pipeline_jobs(job_id),
    graph_semantics TEXT NOT NULL CHECK (graph_semantics IN ('directed', 'mutual')),
    node_count BIGINT NOT NULL CHECK (node_count >= 0),
    edge_count BIGINT NOT NULL CHECK (edge_count >= 0),
    artifact_location TEXT NOT NULL,
    checksum TEXT NOT NULL,
    build_config JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    activated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS active_versions (
    singleton BOOLEAN PRIMARY KEY DEFAULT true CHECK (singleton),
    graph_version TEXT REFERENCES graph_versions(graph_version),
    activated_at TIMESTAMPTZ
);
INSERT INTO active_versions(singleton, graph_version, activated_at) VALUES (true, NULL, NULL)
ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS graph_index_outbox (
    event_id TEXT PRIMARY KEY,
    graph_version TEXT NOT NULL REFERENCES graph_versions(graph_version),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS graph_index_outbox_pending_idx ON graph_index_outbox(created_at) WHERE published_at IS NULL;
