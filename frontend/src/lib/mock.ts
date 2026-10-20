/**
 * Mock data adapter for demo when backend is offline.
 * Data is representative of the MGTAB dataset characteristics.
 * Clearly labelled as MOCK — not real model predictions.
 */

import type {
  TrustProfile,
  ReasoningTrace,
  SafeFilterResponse,
  SafeReRankResponse,
  RecommendationResponse,
  CandidateReRankItem,
  CandidateFilterItem,
} from '../api/types.ts'

// Fixed seed user IDs sampled from the real CSV (various tiers)
export const MOCK_USER_IDS = [42, 100, 250, 500, 750, 1000, 1500, 2000, 3000, 5000, 7500, 9999]

export const MOCK_PROFILES: Record<number, TrustProfile> = {
  42: {
    user_id: 42,
    ground_truth_label: 'Human (Nguoi that)',
    p_bot: 0.12,
    trust_score: 82.4,
    recommendation_tier: 'TIER_1_VERIFIED_SAFE',
    decision: '[OK] - Xác thực An toàn Tuyệt đối, ưu tiên gợi ý hàng đầu.',
    is_recommendable: true,
    split_set: 'train',
    pillars: { identity_auth: 0.88, interaction_health: 0.91, network_hygiene: 0.85, content_safety: 0.72 },
  },
  100: {
    user_id: 100,
    ground_truth_label: 'Human (Nguoi that)',
    p_bot: 0.28,
    trust_score: 67.3,
    recommendation_tier: 'TIER_2_STANDARD_TRUST',
    decision: '[OK] - Tín nhiệm Tiêu chuẩn, đủ điều kiện gợi ý kết bạn.',
    is_recommendable: true,
    split_set: 'val',
    pillars: { identity_auth: 0.73, interaction_health: 0.68, network_hygiene: 0.71, content_safety: 0.54 },
  },
  250: {
    user_id: 250,
    ground_truth_label: 'Human (Nguoi that)',
    p_bot: 0.55,
    trust_score: 52.1,
    recommendation_tier: 'TIER_3_RESTRICTED_CAUTION',
    decision: '[CANH GIAC] - Hạn chế, ẩn khỏi người lạ, cần thêm bạn chung.',
    is_recommendable: false,
    split_set: 'test',
    pillars: { identity_auth: 0.51, interaction_health: 0.62, network_hygiene: 0.48, content_safety: 0.33 },
  },
  500: {
    user_id: 500,
    ground_truth_label: 'Bot (Tai khoan ao)',
    p_bot: 0.89,
    trust_score: 11.2,
    recommendation_tier: 'TIER_4_QUARANTINE_FRAUD',
    decision: '[CACH LY] - Nghi vấn gian lận/botnet, chặn hoàn toàn khỏi luồng gợi ý.',
    is_recommendable: false,
    split_set: 'train',
    pillars: { identity_auth: 0.09, interaction_health: 0.77, network_hygiene: 0.22, content_safety: 0.11 },
  },
}

function makeMockProfile(userId: number): TrustProfile {
  const rng = (userId * 7919) % 100
  if (rng < 30) return { ...MOCK_PROFILES[42], user_id: userId, trust_score: 80 + (rng % 20) }
  if (rng < 55) return { ...MOCK_PROFILES[100], user_id: userId, trust_score: 65 + (rng % 15) }
  if (rng < 75) return { ...MOCK_PROFILES[250], user_id: userId, trust_score: 45 + (rng % 20) }
  return { ...MOCK_PROFILES[500], user_id: userId, trust_score: 5 + (rng % 40) }
}

export function getMockProfile(userId: number): TrustProfile {
  return MOCK_PROFILES[userId] ?? makeMockProfile(userId)
}

export function getMockReasoningTrace(userId: number): ReasoningTrace {
  const profile = getMockProfile(userId)
  return {
    user_id: userId,
    trust_score: profile.trust_score,
    recommendation_tier: profile.recommendation_tier,
    is_recommendable: profile.is_recommendable,
    decision: profile.decision,
    reasoning_trace: [
      `Rủi ro ${profile.p_bot >= 0.75 ? 'Cực cao' : profile.p_bot >= 0.45 ? 'Trung bình' : 'Thấp'}: Xác suất Bot = ${(profile.p_bot * 100).toFixed(1)}%`,
      profile.pillars.identity_auth < 0.20 ? `Cảnh báo Danh tính: S_auth = ${profile.pillars.identity_auth.toFixed(2)} (< 0.20)` : `Danh tính ổn định: S_auth = ${profile.pillars.identity_auth.toFixed(2)}`,
      `Tương tác: S_interact = ${profile.pillars.interaction_health.toFixed(2)}`,
      `Mạng lưới: S_network = ${profile.pillars.network_hygiene.toFixed(2)}`,
    ],
  }
}

// Generate realistic PYMK candidates for a given user
export function getMockCandidates(userId: number, count = 10): number[] {
  const candidates: number[] = []
  const base = (userId * 1237 + 3571) % 9000
  for (let i = 0; i < count; i++) {
    candidates.push((base + i * 173) % 10199)
  }
  return candidates.filter((id) => id !== userId)
}

export function getMockSafeFilterResponse(targetUserId: number, candidateIds: number[]): SafeFilterResponse {
  const safe: CandidateFilterItem[] = []
  const blocked: CandidateFilterItem[] = []
  for (const id of candidateIds) {
    const p = getMockProfile(id)
    const item: CandidateFilterItem = {
      user_id: id,
      trust_score: p.trust_score,
      recommendation_tier: p.recommendation_tier,
      reason: p.decision,
    }
    if (p.is_recommendable) safe.push(item)
    else blocked.push(item)
  }
  return {
    target_user_id: targetUserId,
    total_candidates: candidateIds.length,
    safe_recommendations_count: safe.length,
    safe_candidates: safe,
    filtered_out_candidates: blocked,
  }
}

export function getMockReRankResponse(targetUserId: number, candidateIds: number[]): SafeReRankResponse {
  const passed: CandidateReRankItem[] = []
  const blocked: CandidateReRankItem[] = []
  candidateIds.forEach((id, i) => {
    const p = getMockProfile(id)
    const pymkScore = 1.0 - i * 0.08
    const dyadic = 0.9
    const finalScore = pymkScore * (p.trust_score / 100) * dyadic
    const item: CandidateReRankItem = {
      candidate_id: id,
      trust_score: p.trust_score,
      recommendation_tier: p.recommendation_tier,
      pymk_score: parseFloat(pymkScore.toFixed(4)),
      dyadic_safety_score: dyadic,
      final_ranking_score: parseFloat(finalScore.toFixed(4)),
      is_allowed: p.recommendation_tier !== 'TIER_4_QUARANTINE_FRAUD',
      reason: p.decision,
    }
    if (item.is_allowed) passed.push(item)
    else blocked.push(item)
  })
  passed.sort((a, b) => b.final_ranking_score - a.final_ranking_score)
  return {
    target_user_id: targetUserId,
    total_candidates: candidateIds.length,
    passed_count: passed.length,
    blocked_count: blocked.length,
    ranked_candidates: passed,
    blocked_candidates: blocked,
  }
}

export function getMockRecommendations(userId: number): RecommendationResponse {
  const candidateIds = getMockCandidates(userId, 10)
  return {
    user_id: userId,
    recommendations: candidateIds.map((id, i) => {
      const p = getMockProfile(id)
      return {
        candidate_id: id,
        score: parseFloat((1.0 - i * 0.08).toFixed(4)),
        rank: i + 1,
        eligibility: p.recommendation_tier === 'TIER_1_VERIFIED_SAFE' || p.recommendation_tier === 'TIER_2_STANDARD_TRUST'
          ? 'ELIGIBLE'
          : p.recommendation_tier === 'TIER_3_RESTRICTED_CAUTION'
          ? 'SUSPICIOUS'
          : 'BLOCKED',
        risk_score: p.p_bot,
        trust_score: p.trust_score,
        reason_code: p.decision,
      }
    }),
    graph_version: 'mgtab-v1 [MOCK]',
    trust_version: 'mock-v1',
    trust_policy_version: 'phase06-fail-safe-v1 [MOCK]',
    raw_cache_hit: false,
  }
}

// Overview statistics (mocked from known data characteristics)
export const MOCK_OVERVIEW_STATS = {
  total_users: 10200,
  suspicious_users: 6215, // ~60.9% are Bot per MGTAB
  tier1_count: 380,
  tier2_count: 1120,
  tier3_count: 2485,
  tier4_count: 6215,
  recommendations_generated: 0,
  filtered_or_downranked: 0,
}
