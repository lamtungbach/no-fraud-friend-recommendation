import os
from pathlib import Path
import pytest

pytest.importorskip("pydantic")

import torch

from src.trust.schemas import RecommendationTier
from src.trust.scoring import calculate_trust_score, classify_trust_tier, get_decision_meta
from src.trust.models import FraudDetectionRGCN
from src.trust.service import TrustService
from src.trust.agent import TrustAgent


def test_trust_scoring_formula():
    # w = [0.35, 0.25, 0.25, 0.15]
    # S = 100 * (0.35*1 + 0.25*1 + 0.25*1 + 0.15*1) = 100.0
    score_full = calculate_trust_score(1.0, 1.0, 1.0, 1.0, g_auth=1.0)
    assert score_full == 100.0

    # Test Gating g_auth = 0
    score_gated = calculate_trust_score(1.0, 1.0, 1.0, 1.0, g_auth=0.0)
    assert score_gated == 0.0

    # Test clamping
    score_clamped = calculate_trust_score(1.5, 1.5, 1.5, 1.5, g_auth=2.0)
    assert score_clamped == 100.0


def test_tier_classification():
    # Bot threshold p_bot >= 0.75 -> TIER_4
    assert classify_trust_tier(score=90.0, p_bot=0.8, s_auth=0.9) == RecommendationTier.TIER_4_FRAUD

    # S_auth low threshold < 0.20 -> TIER_4
    assert classify_trust_tier(score=90.0, p_bot=0.1, s_auth=0.15) == RecommendationTier.TIER_4_FRAUD

    # Score < 45.0 -> TIER_4
    assert classify_trust_tier(score=40.0, p_bot=0.1, s_auth=0.5) == RecommendationTier.TIER_4_FRAUD

    # Score in [45.0, 65.0) -> TIER_3
    assert classify_trust_tier(score=55.0, p_bot=0.1, s_auth=0.5) == RecommendationTier.TIER_3_RESTRICTED

    # Score in [65.0, 80.0) -> TIER_2
    assert classify_trust_tier(score=75.0, p_bot=0.1, s_auth=0.5) == RecommendationTier.TIER_2_STANDARD

    # Score >= 80.0 -> TIER_1
    assert classify_trust_tier(score=85.0, p_bot=0.05, s_auth=0.9) == RecommendationTier.TIER_1_VERIFIED


def test_get_decision_meta():
    dec1, rec1 = get_decision_meta(RecommendationTier.TIER_1_VERIFIED)
    assert rec1 is True
    assert "[OK]" in dec1

    dec2, rec2 = get_decision_meta(RecommendationTier.TIER_2_STANDARD)
    assert rec2 is True

    dec3, rec3 = get_decision_meta(RecommendationTier.TIER_3_RESTRICTED)
    assert rec3 is False

    dec4, rec4 = get_decision_meta(RecommendationTier.TIER_4_FRAUD)
    assert rec4 is False


def test_rgcn_weights_loading():
    weights_path = Path(__file__).resolve().parents[1] / "weights" / "rgcn_mgtab_best.pt"
    if weights_path.exists():
        from src.trust.models import load_checkpoint, save_checkpoint
        model = load_checkpoint(path=str(weights_path))
        assert model.conv1.self_linear.weight.shape == (64, 788)
        assert model.conv2.self_linear.weight.shape == (2, 64)

        # Test save_checkpoint
        tmp_path = Path(__file__).resolve().parents[1] / "weights" / "test_tmp.pt"
        try:
            save_checkpoint(model, path=str(tmp_path))
            assert tmp_path.exists()
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


def test_trust_service_with_csv():
    csv_path = Path(__file__).resolve().parents[1] / "data" / "mgtab_user_trust_profiles_v2.csv"
    if csv_path.exists():
        service = TrustService(str(csv_path))
        assert service.is_loaded is True
        assert len(service.cache) > 0

        # Query user 0
        p0 = service.get_user_profile(0)
        assert p0 is not None
        assert p0.user_id == 0
        assert 0.0 <= p0.p_bot <= 1.0

        # Test filtering
        cand_ids = [0, 1, 99999]  # 99999 is unknown
        res = service.filter_safe_candidates(target_user_id=100, candidate_user_ids=cand_ids)
        assert res.total_candidates == 3
        assert len(res.safe_candidates) + len(res.filtered_out_candidates) == 3


def test_trust_agent_reasoning():
    csv_path = Path(__file__).resolve().parents[1] / "data" / "mgtab_user_trust_profiles_v2.csv"
    if csv_path.exists():
        service = TrustService(str(csv_path))
        agent = TrustAgent(service)
        trace0 = agent.inspect_and_reason(0)
        assert "user_id" in trace0
        assert "reasoning_trace" in trace0
        assert len(trace0["reasoning_trace"]) > 0

        # Test user not found edge case
        trace_none = agent.inspect_and_reason(999999)
        assert trace_none["decision"] == "REJECT"
        assert trace_none["is_recommendable"] is False

        # Test tool_analyze_bot_risk branches
        assert "Cực cao" in agent.tool_analyze_bot_risk(0.85)
        assert "Trung bình" in agent.tool_analyze_bot_risk(0.55)
        assert "Thấp" in agent.tool_analyze_bot_risk(0.10)


def test_rgcn_forward_pass_synthetic():
    num_nodes = 4
    in_dim = 16
    hidden_dim = 8
    out_dim = 2
    num_relations = 7

    x = torch.randn(num_nodes, in_dim)
    pre_edges = []
    pre_weights = []
    for _ in range(num_relations):
        src = torch.tensor([0, 1], dtype=torch.long)
        dst = torch.tensor([1, 2], dtype=torch.long)
        w = torch.tensor([[1.0], [1.0]], dtype=torch.float)
        pre_edges.append((src, dst))
        pre_weights.append(w)

    model = FraudDetectionRGCN(in_dim=in_dim, hidden_dim=hidden_dim, out_dim=out_dim, dropout=0.0)
    model.eval()
    with torch.no_grad():
        out = model(x, pre_edges, pre_weights)
    assert out.shape == (num_nodes, out_dim)


def test_service_file_not_found():
    service = TrustService("/non/existent/path/profiles.csv")
    with pytest.raises(FileNotFoundError):
        service.load_profiles()
