"""Unit coverage for the transport-independent Phase 5 PYMK engine."""

from __future__ import annotations

import json

import pytest
import torch

from src.data import CanonicalGraph
from src.graph import GraphView
from src.ranking import RankingConfig
from src.retrieval import RetrievalConfig
from src.serving import (
    ActiveGraphRegistry,
    CacheUnavailableError,
    InMemoryRecommendationCache,
    LocalArtifactStore,
    RecommendationCache,
    RecommendationEngine,
    ServingGraphIndex,
)
from src.serving.recommendation_cache import RedisRecommendationCache


def _graph_objects(*, extra_candidate: bool = False):
    node_ids = torch.arange(7)
    edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 1), (3, 2), (4, 1)]
    if extra_candidate:
        edges.extend([(1, 5), (2, 5), (5, 1), (5, 2)])
    edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
    canonical = CanonicalGraph(
        node_ids=node_ids,
        node_features=None,
        edge_index=edge_index,
        edge_type=torch.ones(edge_index.shape[1], dtype=torch.long),
        edge_weight=None,
        relation_schema={1: {"name": "connection", "directed": True}},
        metadata={"source": "phase5-unit"},
    )
    view = GraphView(node_ids=node_ids, edge_index=edge_index, directed=True)
    return canonical, view, ServingGraphIndex.from_graph_view(view)


def _save(store: LocalArtifactStore, version: str, *, extra_candidate: bool = False) -> None:
    canonical, view, index = _graph_objects(extra_candidate=extra_candidate)
    store.save_version(
        version,
        canonical,
        view,
        index,
        dataset_id="phase5-fixture",
        build_config={"graph_semantics": "directed"},
    )


@pytest.fixture
def active_store(tmp_path):
    store = LocalArtifactStore(tmp_path / "artifacts")
    registry = ActiveGraphRegistry(store, tmp_path / "registry")
    _save(store, "graph-v1")
    registry.activate("graph-v1")
    return store, registry


def _engine(store, registry, *, cache=None, retrieval=None, ranking=None, ttl=60.0):
    return RecommendationEngine(
        store,
        registry,
        retrieval_config=retrieval or RetrievalConfig(candidate_cap=10),
        ranking_config=ranking or RankingConfig("cn", top_m=4),
        cache=cache,
        cache_ttl_seconds=ttl,
    )


def test_cache_miss_computes_then_cache_hit_reuses_raw_top_m(active_store, monkeypatch):
    store, registry = active_store
    cache = InMemoryRecommendationCache()
    engine = _engine(store, registry, cache=cache)
    calls = 0

    from src.serving import recommendation_engine

    original = recommendation_engine.retrieve_bounded_two_hop_candidates

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(recommendation_engine, "retrieve_bounded_two_hop_candidates", counted)
    first = engine.recommend(0, top_k=2)
    second = engine.recommend(0, top_k=2)

    assert calls == 1
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert first.recommendations == second.recommendations
    assert first.retrieval_stats is not None
    assert second.retrieval_stats is None
    assert [item.candidate_id for item in first.recommendations] == [3, 4]
    assert [item.rank for item in first.recommendations] == [1, 2]


def test_deterministic_cached_and_uncached_outputs_match(active_store):
    store, registry = active_store
    uncached = _engine(store, registry)
    cached = _engine(store, registry, cache=InMemoryRecommendationCache())

    expected = uncached.recommend(0, top_k=2)
    first = cached.recommend(0, top_k=2)
    second = cached.recommend(0, top_k=2)

    assert expected.recommendations == first.recommendations == second.recommendations
    assert first.cache_hit is False
    assert second.cache_hit is True


def test_cache_keys_isolate_version_configuration_user_and_top_m(active_store):
    store, registry = active_store
    cache = InMemoryRecommendationCache()
    first = _engine(store, registry, cache=cache)
    changed_retrieval = _engine(
        store,
        registry,
        cache=cache,
        retrieval=RetrievalConfig(candidate_cap=3),
    )
    changed_ranking = _engine(
        store,
        registry,
        cache=cache,
        ranking=RankingConfig("jaccard", top_m=4),
    )

    baseline_key = first.build_cache_key("graph-v1", 0, 4)
    assert baseline_key != first.build_cache_key("graph-v2", 0, 4)
    assert baseline_key != first.build_cache_key("graph-v1", 6, 4)
    assert baseline_key != first.build_cache_key("graph-v1", 0, 3)
    assert baseline_key != changed_retrieval.build_cache_key("graph-v1", 0, 4)
    assert baseline_key != changed_ranking.build_cache_key("graph-v1", 0, 4)


def test_top_m_is_cached_raw_while_top_k_only_trims_response(active_store):
    store, registry = active_store
    cache = InMemoryRecommendationCache()
    engine = _engine(store, registry, cache=cache)

    first = engine.recommend(0, top_k=1, top_m=4)
    second = engine.recommend(0, top_k=2, top_m=4)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert len(first.recommendations) == 1
    assert len(second.recommendations) == 2
    with pytest.raises(ValueError, match="greater"):
        engine.recommend(0, top_k=2, top_m=1)


def test_in_memory_ttl_expiration_causes_a_miss(active_store):
    store, registry = active_store
    now = [100.0]
    cache = InMemoryRecommendationCache(clock=lambda: now[0])
    engine = _engine(store, registry, cache=cache, ttl=5.0)

    assert engine.recommend(0, top_k=1).cache_hit is False
    assert engine.recommend(0, top_k=1).cache_hit is True
    now[0] = 105.0
    assert engine.recommend(0, top_k=1).cache_hit is False


class _UnavailableCache(RecommendationCache):
    def get(self, key: str) -> str | None:
        del key
        raise CacheUnavailableError("test outage")

    def set(self, key: str, value: str, ttl_seconds: float) -> None:
        del key, value, ttl_seconds
        raise CacheUnavailableError("test outage")


def test_cache_outage_bypasses_to_graph_retrieval(active_store):
    store, registry = active_store
    result = _engine(store, registry, cache=_UnavailableCache()).recommend(0, top_k=2)

    assert result.cache_hit is False
    assert [item.candidate_id for item in result.recommendations] == [3, 4]


def test_redis_connection_failure_bypasses_both_cache_operations(active_store):
    import redis

    class FailingRedisClient:
        def get(self, key: str) -> str | None:
            del key
            raise redis.exceptions.ConnectionError("test outage")

        def set(self, key: str, value: str, px: int) -> None:
            del key, value, px
            raise redis.exceptions.ConnectionError("test outage")

    store, registry = active_store
    cache = RedisRecommendationCache("redis://127.0.0.1:6379/0")
    cache._client = FailingRedisClient()
    result = _engine(store, registry, cache=cache).recommend(0, top_k=2)

    assert result.cache_hit is False
    assert [item.candidate_id for item in result.recommendations] == [3, 4]


def test_invalid_user_and_empty_candidate_pool(active_store):
    store, registry = active_store
    engine = _engine(store, registry, cache=InMemoryRecommendationCache())

    with pytest.raises(KeyError, match="Unknown user_id"):
        engine.recommend(99, top_k=1)
    empty_first = engine.recommend(6, top_k=2)
    empty_second = engine.recommend(6, top_k=2)
    assert empty_first.recommendations == ()
    assert empty_first.cache_hit is False
    assert empty_second.cache_hit is True


def test_corrupted_and_incompatible_cache_payloads_are_cache_misses(active_store):
    store, registry = active_store
    cache = InMemoryRecommendationCache()
    engine = _engine(store, registry, cache=cache)
    key = engine.build_cache_key("graph-v1", 0, 4)

    cache.set(key, "not-json", 60)
    assert engine.recommend(0, top_k=1).cache_hit is False

    bad_identity = {
        "schema_version": 1,
        "graph_version": "wrong-version",
        "retrieval_config_hash": "wrong",
        "ranking_config_hash": "wrong",
        "user_id": 0,
        "top_m": 4,
        "ranking_method": "cn",
        "recommendations": [],
    }
    cache.set(key, json.dumps(bad_identity), 60)
    assert engine.recommend(0, top_k=1).cache_hit is False


def test_active_version_switch_uses_a_new_cache_namespace(active_store):
    store, registry = active_store
    cache = InMemoryRecommendationCache()
    engine = _engine(store, registry, cache=cache)
    assert engine.recommend(0, top_k=2).graph_version == "graph-v1"
    assert engine.recommend(0, top_k=2).cache_hit is True

    _save(store, "graph-v2", extra_candidate=True)
    registry.activate("graph-v2")
    switched = engine.recommend(0, top_k=3)

    assert switched.graph_version == "graph-v2"
    assert switched.cache_hit is False
    assert [item.candidate_id for item in switched.recommendations] == [3, 5, 4]


def test_engine_requires_an_active_version_and_valid_arguments(tmp_path):
    store = LocalArtifactStore(tmp_path / "artifacts")
    registry = ActiveGraphRegistry(store, tmp_path / "registry")
    engine = _engine(store, registry)

    with pytest.raises(RuntimeError, match="No active"):
        engine.recommend(0, top_k=1)
    with pytest.raises(ValueError, match="non-negative"):
        engine.recommend(0, top_k=-1)
