from scripts.benchmark_quality_speed import _bucket, _heavy_tail_edges, _recommended_row


def test_degree_buckets_cover_the_required_boundaries():
    values = (0, 10, 11, 50, 51, 100, 101, 500, 501, 1_000, 1_001)
    assert [_bucket(value) for value in values] == ["0-10", "0-10", "11-50", "11-50", "51-100", "51-100", "101-500", "101-500", "501-1000", "501-1000", ">1000"]


def test_recommendation_prefers_quality_parity_then_lower_latency():
    rows = [{"semantics": "directed", "candidate_cap": "1000", "candidate_coverage": 0.8, "recall_at_10": 0.2, "p95_latency_ms": 1.0}, {"semantics": "directed", "candidate_cap": "5000", "candidate_coverage": 0.9, "recall_at_10": 0.2, "p95_latency_ms": 2.0}, {"semantics": "directed", "candidate_cap": "unlimited", "candidate_coverage": 0.9, "recall_at_10": 0.2, "p95_latency_ms": 3.0}]
    assert _recommended_row(rows, "directed")["candidate_cap"] == "5000"


def test_heavy_tail_generator_is_deterministic_and_has_no_self_loops():
    first = _heavy_tail_edges(100, 300, 42)
    assert first == _heavy_tail_edges(100, 300, 42)
    assert len(first) == 300
    assert all(source != destination for source, destination in first)
