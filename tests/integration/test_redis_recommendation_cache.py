"""Opt-in integration coverage for the local ``pymk-redis`` container."""

from __future__ import annotations

import os
import uuid

import pytest
import torch

if os.getenv("RUN_REDIS_INTEGRATION") != "1":
    pytest.skip("set RUN_REDIS_INTEGRATION=1 to run Redis integration tests", allow_module_level=True)

redis = pytest.importorskip("redis")

from src.data import CanonicalGraph
from src.graph import GraphView
from src.ranking import RankingConfig
from src.retrieval import RetrievalConfig
from src.serving import (
    ActiveGraphRegistry,
    LocalArtifactStore,
    RecommendationEngine,
    RedisRecommendationCache,
    ServingGraphIndex,
)


@pytest.fixture
def isolated_redis_cache():
    prefix = f"pymk-phase5-test-{uuid.uuid4().hex}"
    url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    cache = RedisRecommendationCache(url, key_prefix=prefix)
    client = redis.Redis.from_url(url, decode_responses=True)
    client.ping()
    try:
        yield cache, client, prefix
    finally:
        keys = list(client.scan_iter(match=f"{prefix}:*"))
        if keys:
            client.delete(*keys)


def test_redis_cache_round_trip_and_dedicated_prefix_cleanup(isolated_redis_cache):
    cache, _, _ = isolated_redis_cache
    cache.set("entry", '{"recommendations":[]}', ttl_seconds=5)

    assert cache.get("entry") == '{"recommendations":[]}'


def test_redis_cache_ttl_expiry(isolated_redis_cache):
    cache, _, _ = isolated_redis_cache
    cache.set("short-lived", "value", ttl_seconds=0.001)

    import time

    time.sleep(0.02)
    assert cache.get("short-lived") is None


def test_redis_backed_engine_returns_a_miss_then_a_hit(tmp_path, isolated_redis_cache):
    cache, _, _ = isolated_redis_cache
    node_ids = torch.tensor([0, 1, 2, 3])
    edge_index = torch.tensor([[0, 0, 1, 2, 3, 3], [1, 2, 3, 3, 1, 2]])
    canonical = CanonicalGraph(
        node_ids=node_ids,
        node_features=None,
        edge_index=edge_index,
        edge_type=torch.ones(edge_index.shape[1], dtype=torch.long),
        edge_weight=None,
    )
    view = GraphView(node_ids=node_ids, edge_index=edge_index, directed=True)
    store = LocalArtifactStore(tmp_path / "artifacts")
    store.save_version(
        "redis-integration-v1",
        canonical,
        view,
        ServingGraphIndex.from_graph_view(view),
        dataset_id="redis-integration",
    )
    registry = ActiveGraphRegistry(store, tmp_path / "registry")
    registry.activate("redis-integration-v1")
    engine = RecommendationEngine(
        store,
        registry,
        retrieval_config=RetrievalConfig(candidate_cap=10),
        ranking_config=RankingConfig("cn", top_m=3),
        cache=cache,
        cache_ttl_seconds=30,
    )

    first = engine.recommend(0, top_k=1)
    second = engine.recommend(0, top_k=1)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert first.recommendations == second.recommendations
