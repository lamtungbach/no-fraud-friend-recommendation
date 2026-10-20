// All TypeScript types for the Trust-Aware PYMK Demo

export type RecommendationTier =
  | 'TIER_1_VERIFIED_SAFE'
  | 'TIER_2_STANDARD_TRUST'
  | 'TIER_3_RESTRICTED_CAUTION'
  | 'TIER_4_QUARANTINE_FRAUD'

export interface PillarScores {
  identity_auth: number
  interaction_health: number
  network_hygiene: number
  content_safety: number
}

export interface TrustProfile {
  user_id: number
  ground_truth_label: string
  p_bot: number
  trust_score: number
  recommendation_tier: RecommendationTier
  decision: string
  is_recommendable: boolean
  split_set: string
  pillars: PillarScores
}

export interface ReasoningTrace {
  user_id: number
  trust_score: number
  recommendation_tier: string
  is_recommendable: boolean
  decision: string
  reasoning_trace: string[]
}

// Safe Filter (DROP policy)
export interface CandidateFilterItem {
  user_id: number
  trust_score: number
  recommendation_tier: RecommendationTier
  reason: string
}

export interface SafeFilterRequest {
  target_user_id: number
  candidate_user_ids: number[]
}

export interface SafeFilterResponse {
  target_user_id: number
  total_candidates: number
  safe_recommendations_count: number
  safe_candidates: CandidateFilterItem[]
  filtered_out_candidates: CandidateFilterItem[]
}

// Safe Re-Rank (DOWNRANK policy)
export interface CandidateReRankInput {
  candidate_id: number
  pymk_score: number
  mutual_total_count: number
  mutual_tier1_count: number
  asymmetry_penalty: number
}

export interface CandidateReRankItem {
  candidate_id: number
  trust_score: number
  recommendation_tier: RecommendationTier
  pymk_score: number
  dyadic_safety_score: number
  final_ranking_score: number
  is_allowed: boolean
  reason: string
}

export interface SafeReRankRequest {
  target_user_id: number
  candidates: CandidateReRankInput[]
  tier3_threshold: number
}

export interface SafeReRankResponse {
  target_user_id: number
  total_candidates: number
  passed_count: number
  blocked_count: number
  ranked_candidates: CandidateReRankItem[]
  blocked_candidates: CandidateReRankItem[]
}

// Raw PYMK recommendations
export interface SafeRecommendationItem {
  candidate_id: number
  score: number
  rank: number
  eligibility: 'ELIGIBLE' | 'SUSPICIOUS' | 'BLOCKED' | 'UNKNOWN'
  risk_score: number | null
  trust_score: number | null
  reason_code: string | null
}

export interface RecommendationRequest {
  user_id: number
  top_k: number
}

export interface RecommendationResponse {
  user_id: number
  recommendations: SafeRecommendationItem[]
  graph_version: string
  trust_version: string
  trust_policy_version: string
  raw_cache_hit: boolean
}

// Policy types for the UI
export type TrustPolicy = 'DROP' | 'DOWNRANK'

// Enriched candidate for display
export interface EnrichedCandidate {
  candidate_id: number
  pymk_score: number
  original_rank: number
  trust_score: number | null
  p_bot: number | null
  trust_tier: RecommendationTier | null
  is_recommendable: boolean | null
  final_score: number | null
  decision: 'KEPT' | 'DOWNRANKED' | 'FILTERED'
  reason: string
  mutual_count?: number
}

// API error
export interface ApiError {
  message: string
  status?: number
}
