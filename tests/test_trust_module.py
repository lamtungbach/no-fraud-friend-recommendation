from pathlib import Path
import pytest

pytest.importorskip("pydantic")

import torch  # noqa: E402

from src.trust.schemas import (  # noqa: E402
    CandidateReRankInput,
    PillarScores,
    RecommendationTier,
    TrustProfileResponse,
)
from src.trust.scoring import (  # noqa: E402
    calculate_dyadic_safety_score,
    calculate_final_ranking_score,
    calculate_trust_score,
    classify_trust_tier,
    evaluate_candidate_admission,
    get_decision_meta,
)
from src.trust.models import FraudDetectionRGCN  # noqa: E402
from src.trust.service import TrustService  # noqa: E402
from src.trust.agent import TrustAgent  # noqa: E402


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


def test_final_ranking_score_formula():
    # Final = pymk * (trust / 100) * dyadic
    # 0.80 * 0.80 * 1.0 = 0.64
    score1 = calculate_final_ranking_score(0.8, 80.0, 1.0)
    assert abs(score1 - 0.64) < 1e-6

    # Zero trust -> 0.0
    score_zero = calculate_final_ranking_score(0.95, 0.0, 1.0)
    assert score_zero == 0.0

    # Clamping
    score_clamped = calculate_final_ranking_score(-0.5, 150.0, 1.5)
    assert score_clamped == 0.0


def test_evaluate_candidate_admission_policy():
    # Tier 1 -> Always Allowed
    ok1, _ = evaluate_candidate_admission(RecommendationTier.TIER_1_VERIFIED)
    assert ok1 is True

    # Tier 2 -> Always Allowed
    ok2, _ = evaluate_candidate_admission(RecommendationTier.TIER_2_STANDARD)
    assert ok2 is True

    # Tier 3 with insufficient mutual Tier 1 -> Blocked
    ok3_block, msg3_block = evaluate_candidate_admission(
        RecommendationTier.TIER_3_RESTRICTED, mutual_tier1_count=2, tier3_threshold=5
    )
    assert ok3_block is False
    assert "[AN]" in msg3_block

    # Tier 3 with sufficient mutual Tier 1 (>= 5) -> Allowed
    ok3_pass, msg3_pass = evaluate_candidate_admission(
        RecommendationTier.TIER_3_RESTRICTED, mutual_tier1_count=5, tier3_threshold=5
    )
    assert ok3_pass is True
    assert "[CUU XET]" in msg3_pass

    # Tier 4 -> Always Blocked
    ok4, msg4 = evaluate_candidate_admission(RecommendationTier.TIER_4_FRAUD, mutual_tier1_count=20)
    assert ok4 is False
    assert "[CACH LY]" in msg4


def test_rerank_candidates_logic_and_sorting():
    service = TrustService("/mock/non_existent.csv")
    service.cache = {
        10: TrustProfileResponse(
            user_id=10,
            ground_truth_label="Human (Nguoi that)",
            p_bot=0.02,
            trust_score=90.0,
            recommendation_tier=RecommendationTier.TIER_1_VERIFIED,
            decision="[OK]",
            is_recommendable=True,
            pillars=PillarScores(identity_auth=0.9, interaction_health=0.9, network_hygiene=0.9, content_safety=0.9),
        ),
        20: TrustProfileResponse(
            user_id=20,
            ground_truth_label="Human (Nguoi that)",
            p_bot=0.15,
            trust_score=70.0,
            recommendation_tier=RecommendationTier.TIER_2_STANDARD,
            decision="[OK]",
            is_recommendable=True,
            pillars=PillarScores(identity_auth=0.7, interaction_health=0.7, network_hygiene=0.7, content_safety=0.7),
        ),
        30: TrustProfileResponse(
            user_id=30,
            ground_truth_label="Human (Nguoi that)",
            p_bot=0.25,
            trust_score=50.0,
            recommendation_tier=RecommendationTier.TIER_3_RESTRICTED,
            decision="[CANH GIAC]",
            is_recommendable=False,
            pillars=PillarScores(identity_auth=0.5, interaction_health=0.5, network_hygiene=0.5, content_safety=0.5),
        ),
        40: TrustProfileResponse(
            user_id=40,
            ground_truth_label="Bot (Tai khoan ao)",
            p_bot=0.95,
            trust_score=15.0,
            recommendation_tier=RecommendationTier.TIER_4_FRAUD,
            decision="[CACH LY]",
            is_recommendable=False,
            pillars=PillarScores(identity_auth=0.1, interaction_health=0.1, network_hygiene=0.1, content_safety=0.1),
        ),
    }
    service.is_loaded = True

    inputs = [
        # Candidate 10: pymk=0.50, trust=90.0 -> final = 0.45 (Tier 1)
        CandidateReRankInput(candidate_id=10, pymk_score=0.50, mutual_tier1_count=0),
        # Candidate 20: pymk=0.50, trust=70.0 -> final = 0.35 (Tier 2)
        CandidateReRankInput(candidate_id=20, pymk_score=0.50, mutual_tier1_count=0),
        # Candidate 30: pymk=0.80, trust=50.0 -> final = 0.40, mutual=5 (Tier 3 rescued!)
        CandidateReRankInput(candidate_id=30, pymk_score=0.80, mutual_tier1_count=5),
        # Candidate 40: pymk=0.99, trust=15.0 -> final = 0.1485 (Tier 4 blocked 100%)
        CandidateReRankInput(candidate_id=40, pymk_score=0.99, mutual_tier1_count=10),
    ]

    res = service.rerank_candidates(target_user_id=100, candidates=inputs, tier3_threshold=5)
    assert res.total_candidates == 4
    assert res.passed_count == 3
    assert res.blocked_count == 1

    # Check rank order: 10 (final 0.45) > 30 (final 0.40) > 20 (final 0.35)
    assert res.ranked_candidates[0].candidate_id == 10
    assert res.ranked_candidates[1].candidate_id == 30
    assert res.ranked_candidates[2].candidate_id == 20

    # Candidate 40 must be in blocked list
    assert res.blocked_candidates[0].candidate_id == 40
    assert res.blocked_candidates[0].is_allowed is False


def test_rerank_deterministic_tie_breaker():
    service = TrustService("/mock/non_existent.csv")
    service.cache = {
        5: TrustProfileResponse(
            user_id=5,
            ground_truth_label="Human",
            p_bot=0.05,
            trust_score=80.0,
            recommendation_tier=RecommendationTier.TIER_1_VERIFIED,
            decision="[OK]",
            is_recommendable=True,
            pillars=PillarScores(identity_auth=0.8, interaction_health=0.8, network_hygiene=0.8, content_safety=0.8),
        ),
        15: TrustProfileResponse(
            user_id=15,
            ground_truth_label="Human",
            p_bot=0.05,
            trust_score=80.0,
            recommendation_tier=RecommendationTier.TIER_1_VERIFIED,
            decision="[OK]",
            is_recommendable=True,
            pillars=PillarScores(identity_auth=0.8, interaction_health=0.8, network_hygiene=0.8, content_safety=0.8),
        ),
    }
    service.is_loaded = True

    # Both have pymk=0.5 and trust=80.0 -> identical final_ranking_score = 0.40
    inputs = [
        CandidateReRankInput(candidate_id=15, pymk_score=0.5, mutual_tier1_count=0),
        CandidateReRankInput(candidate_id=5, pymk_score=0.5, mutual_tier1_count=0),
    ]

    res = service.rerank_candidates(target_user_id=1, candidates=inputs)
    # Tie break: candidate 5 must come before candidate 15
    assert res.ranked_candidates[0].candidate_id == 5
    assert res.ranked_candidates[1].candidate_id == 15


def test_calculate_dyadic_safety_score_logic():
    # 1. Bạn chung sạch 100% Tier 1 (5/5) -> dyadic = 1.0
    score_clean = calculate_dyadic_safety_score(mutual_total_count=5, mutual_tier1_count=5)
    assert abs(score_clean - 1.0) < 1e-6

    # 2. Bẫy bạn chung: 10 bạn chung nhưng chỉ 1 bạn Tier 1 (1/10)
    # alpha = 0.20 -> purity = 0.20 + 0.80 * 0.10 = 0.28
    score_trap = calculate_dyadic_safety_score(mutual_total_count=10, mutual_tier1_count=1)
    assert abs(score_trap - 0.28) < 1e-6

    # 3. Bẫy bạn chung cực đoan: 10 bạn chung nhưng 0 bạn Tier 1
    # purity = 0.20 + 0.80 * 0.0 = 0.20
    score_extreme_trap = calculate_dyadic_safety_score(mutual_total_count=10, mutual_tier1_count=0)
    assert abs(score_extreme_trap - 0.20) < 1e-6

    # 4. Spam tương tác bất đối xứng (asymmetry penalty = 0.5)
    score_spam = calculate_dyadic_safety_score(
        mutual_total_count=5, mutual_tier1_count=5, asymmetry_penalty=0.5
    )
    assert abs(score_spam - 0.50) < 1e-6

    # 5. Spam nặng (penalty = 1.0) -> dyadic = 0.0
    score_heavy_spam = calculate_dyadic_safety_score(
        mutual_total_count=5, mutual_tier1_count=5, asymmetry_penalty=1.0
    )
    assert score_heavy_spam == 0.0

    # 6. Không có bạn chung (mutual_total = 0) -> không phạt bẫy bạn chung (dyadic = 1.0)
    score_no_mutual = calculate_dyadic_safety_score(mutual_total_count=0, mutual_tier1_count=0)
    assert abs(score_no_mutual - 1.0) < 1e-6

    # 7. Clamping & boundary checks
    score_overflow = calculate_dyadic_safety_score(
        mutual_total_count=5, mutual_tier1_count=10, asymmetry_penalty=-0.5
    )
    assert abs(score_overflow - 1.0) < 1e-6


def test_rerank_candidates_penalizes_triadic_trap():
    """
    Kiểm tra kịch bản phòng vệ bẫy bạn chung (Triadic Infiltration Defense):
    Ứng viên A có điểm pymk_score cao (0.90) nhưng dính bẫy bạn chung (chỉ 1/10 bạn Tier 1).
    Ứng viên B có điểm pymk_score vừa phải (0.60) nhưng bạn chung sạch 100% (3/3 bạn Tier 1).
    Cả 2 đều thuộc Tier 2 (trust_score = 70.0).

    Không có Dyadic:
      A = 0.90 * 0.70 = 0.630
      B = 0.60 * 0.70 = 0.420 -> A xếp trên B!
    Có Dyadic:
      A = 0.90 * 0.70 * 0.28 = 0.1764
      B = 0.60 * 0.70 * 1.00 = 0.4200 -> B đè bẹp A và xếp trên A!
    """
    service = TrustService("/mock/non_existent.csv")
    service.cache = {
        101: TrustProfileResponse(
            user_id=101,
            ground_truth_label="Human",
            p_bot=0.10,
            trust_score=70.0,
            recommendation_tier=RecommendationTier.TIER_2_STANDARD,
            decision="[OK]",
            is_recommendable=True,
            pillars=PillarScores(identity_auth=0.7, interaction_health=0.7, network_hygiene=0.7, content_safety=0.7),
        ),
        102: TrustProfileResponse(
            user_id=102,
            ground_truth_label="Human",
            p_bot=0.10,
            trust_score=70.0,
            recommendation_tier=RecommendationTier.TIER_2_STANDARD,
            decision="[OK]",
            is_recommendable=True,
            pillars=PillarScores(identity_auth=0.7, interaction_health=0.7, network_hygiene=0.7, content_safety=0.7),
        ),
    }
    service.is_loaded = True

    inputs = [
        # Ứng viên 101: Giăng bẫy bạn chung (10 bạn chung, chỉ 1 bạn Tier 1)
        CandidateReRankInput(
            candidate_id=101,
            pymk_score=0.90,
            mutual_total_count=10,
            mutual_tier1_count=1,
            asymmetry_penalty=0.0,
        ),
        # Ứng viên 102: Bạn chung trong sạch (3 bạn chung, cả 3 bạn Tier 1)
        CandidateReRankInput(
            candidate_id=102,
            pymk_score=0.60,
            mutual_total_count=3,
            mutual_tier1_count=3,
            asymmetry_penalty=0.0,
        ),
    ]

    res = service.rerank_candidates(target_user_id=999, candidates=inputs)
    assert res.total_candidates == 2
    assert res.passed_count == 2

    # Ứng viên 102 phải vươn lên Top 1
    assert res.ranked_candidates[0].candidate_id == 102
    assert abs(res.ranked_candidates[0].dyadic_safety_score - 1.0) < 1e-6
    assert abs(res.ranked_candidates[0].final_ranking_score - 0.4200) < 1e-4

    # Ứng viên 101 bị dìm xuống vị trí thứ 2
    assert res.ranked_candidates[1].candidate_id == 101
    assert abs(res.ranked_candidates[1].dyadic_safety_score - 0.28) < 1e-6
    assert abs(res.ranked_candidates[1].final_ranking_score - 0.1764) < 1e-4

    # Kiểm tra cảnh báo bẫy bạn chung xuất hiện trong lý do
    assert "[CANH BAO BAY BAN CHUNG]" in res.ranked_candidates[1].reason
