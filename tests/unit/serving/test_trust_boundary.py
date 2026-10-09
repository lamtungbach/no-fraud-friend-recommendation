"""Phase 06 boundary tests: policy merge, adapter contracts, and raw cache isolation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

from src.data import CanonicalGraph
from src.graph import GraphView
from src.ranking import RankingConfig
from src.retrieval import RetrievalConfig
from src.serving import (
    ActiveGraphRegistry,
    AllowAllTrustProvider,
    Eligibility,
    InMemoryRecommendationCache,
    LocalArtifactStore,
    MockTrustProvider,
    Recommendation,
    RecommendationEngine,
    ServingGraphIndex,
    TrustAction,
    TrustBatchResult,
    TrustCandidateResult,
    TrustPolicy,
    TrustServiceEligibilityProvider,
)
from src.serving.recommendation_engine import LatencyBreakdown, RecommendationResult
from src.serving.trust_boundary import SafeTopKMerger


def _raw(ids=(10, 20, 30)):
    return RecommendationResult(
        user_id=1,
        recommendations=tuple(
            Recommendation(candidate_id=candidate_id, score=1.0 - rank / 10, rank=rank)
            for rank, candidate_id in enumerate(ids, start=1)
        ),
        graph_version="graph-test-v1",
        ranking_method="cn",
        retrieval_config_hash="retrieval",
        ranking_config_hash="ranking",
        cache_hit=False,
        retrieval_stats=None,
        latency=LatencyBreakdown(0.0, 0.0, 0.0, 0.0),
    )


def _batch(*decisions, version="trust-test-v1"):
    return TrustBatchResult(candidates=tuple(decisions), trust_version=version)


def _decision(candidate_id, eligibility, reason=None):
    return TrustCandidateResult(candidate_id, eligibility, risk_score=0.1, reason_code=reason)


def test_allow_all_keeps_raw_pymk_order_and_metadata():
    result = SafeTopKMerger().merge(_raw(), 3, AllowAllTrustProvider("allow-v9"))

    assert [item.candidate_id for item in result.recommendations] == [10, 20, 30]
    assert result.graph_version == "graph-test-v1"
    assert result.trust_version == "allow-v9"


def test_blocked_unknown_and_missing_profile_follow_explicit_default_policy():
    provider = MockTrustProvider(
        _batch(
            _decision(10, Eligibility.BLOCKED),
            _decision(20, Eligibility.UNKNOWN),
            _decision(30, Eligibility.UNKNOWN, "TRUST_PROFILE_MISSING"),
        )
    )

    result = SafeTopKMerger().merge(_raw(), 3, provider)

    assert result.recommendations == ()


def test_suspicious_is_dropped_by_the_fail_safe_default_policy():
    provider = MockTrustProvider(
        _batch(
            _decision(10, Eligibility.SUSPICIOUS),
            _decision(20, Eligibility.ELIGIBLE),
            _decision(30, Eligibility.SUSPICIOUS),
        )
    )

    result = SafeTopKMerger().merge(_raw(), 3, provider)

    assert [item.candidate_id for item in result.recommendations] == [20]


def test_suspicious_is_deterministically_downranked_when_configured():
    provider = MockTrustProvider(
        _batch(
            _decision(10, Eligibility.SUSPICIOUS),
            _decision(20, Eligibility.ELIGIBLE),
            _decision(30, Eligibility.SUSPICIOUS),
        )
    )

    result = SafeTopKMerger(TrustPolicy(suspicious_action=TrustAction.DOWNRANK)).merge(
        _raw(), 3, provider
    )

    assert [item.candidate_id for item in result.recommendations] == [20, 10, 30]
    assert [item.rank for item in result.recommendations] == [2, 1, 3]


def test_unknown_can_be_configured_to_keep():
    policy = TrustPolicy(unknown_action=TrustAction.KEEP, version="mentor-choice-v1")
    result = SafeTopKMerger(policy).merge(
        _raw(), 3, MockTrustProvider(_batch(_decision(10, Eligibility.UNKNOWN)))
    )

    assert [item.candidate_id for item in result.recommendations] == [10]
    assert result.trust_policy_version == "mentor-choice-v1"


@pytest.mark.parametrize("error", [TimeoutError("deadline"), RuntimeError("transport")])
def test_timeout_or_provider_error_fails_safe_without_eligible_fallback(error):
    result = SafeTopKMerger().merge(_raw(), 3, MockTrustProvider(error=error))

    assert result.recommendations == ()
    assert result.trust_version == "unavailable"


def test_partial_duplicate_extra_and_invalid_results_are_never_reintroduced():
    provider = MockTrustProvider(
        _batch(
            _decision(10, Eligibility.ELIGIBLE),
            _decision(10, Eligibility.BLOCKED),  # first result wins deterministically
            _decision(999, Eligibility.ELIGIBLE),  # ignored: not raw PYMK
            TrustCandidateResult(20, Eligibility.ELIGIBLE, risk_score=float("nan")),
            # candidate 30 is missing from the Trust batch
        )
    )

    result = SafeTopKMerger().merge(_raw((10, 10, 20, 30)), 10, provider)

    assert [item.candidate_id for item in result.recommendations] == [10]
    assert len({item.candidate_id for item in result.recommendations}) == 1


def test_trust_version_propagates_from_provider():
    result = SafeTopKMerger().merge(
        _raw((10,)), 1, MockTrustProvider(_batch(_decision(10, Eligibility.ELIGIBLE), version="rgcn-42"))
    )

    assert result.trust_version == "rgcn-42"


class _NoMutualCount:
    def batch_count(self, user_id, candidate_ids):
        del user_id, candidate_ids
        return {}


class _FakeTrustService:
    def __init__(self):
        self.rerank_calls = 0
        self.profiles = {
            10: SimpleNamespace(
                recommendation_tier=SimpleNamespace(value="TIER_1_VERIFIED_SAFE"), p_bot=0.02
            ),
            30: SimpleNamespace(
                recommendation_tier=SimpleNamespace(value="TIER_3_RESTRICTED_CAUTION"), p_bot=0.2
            ),
        }

    def get_user_profile(self, candidate_id):
        return self.profiles.get(candidate_id)

    def rerank_candidates(self, target_user_id, candidates, tier3_threshold):
        del target_user_id, tier3_threshold
        self.rerank_calls += 1
        items = [
            SimpleNamespace(
                candidate_id=item.candidate_id,
                trust_score=90.0,
                is_allowed=True,
                reason="TRUST_SERVICE_ALLOWED",
            )
            for item in candidates
        ]
        return SimpleNamespace(ranked_candidates=items, blocked_candidates=[])


def test_trust_service_adapter_validates_generic_ids_and_never_invents_tier3_count():
    service = _FakeTrustService()
    provider = TrustServiceEligibilityProvider(
        service, mutual_tier1_counts=_NoMutualCount(), trust_version="linh-v2"
    )

    result = provider.batch_check(1, [10, "opaque-id", 20, 30], pymk_scores={10: 0.9})
    by_id = {item.candidate_id: item for item in result.candidates}

    assert by_id[10].eligibility is Eligibility.ELIGIBLE
    assert by_id["opaque-id"].reason_code == "INVALID_TRUST_CANDIDATE_ID"
    assert by_id[20].reason_code == "TRUST_PROFILE_MISSING"
    assert by_id[30].reason_code == "MUTUAL_TIER1_COUNT_UNAVAILABLE"
    assert service.rerank_calls == 1
    assert result.trust_version == "linh-v2"


def _engine_with_cache(tmp_path):
    store = LocalArtifactStore(tmp_path / "artifacts")
    registry = ActiveGraphRegistry(store, tmp_path / "registry")
    node_ids = torch.arange(7)
    edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 1), (3, 2), (4, 1)]
    edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
    canonical = CanonicalGraph(
        node_ids=node_ids,
        node_features=None,
        edge_index=edge_index,
        edge_type=torch.ones(edge_index.shape[1], dtype=torch.long),
        edge_weight=None,
        relation_schema={1: {"name": "connection", "directed": True}},
        metadata={"source": "phase06-test"},
    )
    view = GraphView(node_ids=node_ids, edge_index=edge_index, directed=True)
    store.save_version(
        "graph-v1",
        canonical,
        view,
        ServingGraphIndex.from_graph_view(view),
        dataset_id="phase06-fixture",
        build_config={"graph_semantics": "directed"},
    )
    registry.activate("graph-v1")
    return RecommendationEngine(
        store,
        registry,
        retrieval_config=RetrievalConfig(candidate_cap=10),
        ranking_config=RankingConfig("cn", top_m=4),
        cache=InMemoryRecommendationCache(),
    )


def test_safe_top_k_is_not_cached_and_raw_pymk_cache_is_independent_of_trust_state(tmp_path):
    engine = _engine_with_cache(tmp_path)
    allow = engine.recommend_safe(0, 2, top_m=4, trust_provider=AllowAllTrustProvider())
    block = engine.recommend_safe(
        0,
        2,
        top_m=4,
        trust_provider=MockTrustProvider(
            _batch(_decision(3, Eligibility.BLOCKED), _decision(4, Eligibility.BLOCKED))
        ),
    )

    assert allow.raw_cache_hit is False
    assert [item.candidate_id for item in allow.recommendations] == [3, 4]
    assert block.raw_cache_hit is True
    assert block.recommendations == ()
