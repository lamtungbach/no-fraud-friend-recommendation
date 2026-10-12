"""Low-cardinality Phase 08 metrics; graph/user payloads are never labels."""

from prometheus_client import Counter

PIPELINE_JOB_TRANSITIONS = Counter(
    "pipeline_job_transitions_total",
    "Batch pipeline job transitions by terminal/current status.",
    ("status",),
)
GRAPH_INDEX_RELOADS = Counter(
    "graph_index_reloads_total",
    "Graph-index reload outcomes after receiving a lifecycle event.",
    ("outcome",),
)
