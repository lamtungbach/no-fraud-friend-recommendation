import type { RecommendationTier } from '../api/types.ts'

export function getTierLabel(tier: RecommendationTier): string {
  switch (tier) {
    case 'TIER_1_VERIFIED_SAFE': return 'Tier 1 · Verified Safe'
    case 'TIER_2_STANDARD_TRUST': return 'Tier 2 · Standard Trust'
    case 'TIER_3_RESTRICTED_CAUTION': return 'Tier 3 · Restricted'
    case 'TIER_4_QUARANTINE_FRAUD': return 'Tier 4 · Quarantined'
    default: return 'Unknown'
  }
}

export function getTierShort(tier: RecommendationTier): string {
  switch (tier) {
    case 'TIER_1_VERIFIED_SAFE': return 'T1'
    case 'TIER_2_STANDARD_TRUST': return 'T2'
    case 'TIER_3_RESTRICTED_CAUTION': return 'T3'
    case 'TIER_4_QUARANTINE_FRAUD': return 'T4'
    default: return '??'
  }
}

export function getTierClass(tier: RecommendationTier | null | undefined): string {
  switch (tier) {
    case 'TIER_1_VERIFIED_SAFE': return 'tier-1'
    case 'TIER_2_STANDARD_TRUST': return 'tier-2'
    case 'TIER_3_RESTRICTED_CAUTION': return 'tier-3'
    case 'TIER_4_QUARANTINE_FRAUD': return 'tier-4'
    default: return ''
  }
}

export function getTierColor(tier: RecommendationTier | null | undefined): string {
  switch (tier) {
    case 'TIER_1_VERIFIED_SAFE': return '#10b981'
    case 'TIER_2_STANDARD_TRUST': return '#3b82f6'
    case 'TIER_3_RESTRICTED_CAUTION': return '#f59e0b'
    case 'TIER_4_QUARANTINE_FRAUD': return '#ef4444'
    default: return '#64748b'
  }
}

export function getRiskColor(pBot: number): string {
  if (pBot >= 0.75) return '#ef4444'
  if (pBot >= 0.45) return '#f59e0b'
  return '#10b981'
}

export function getRiskLabel(pBot: number): string {
  if (pBot >= 0.75) return 'High Risk'
  if (pBot >= 0.45) return 'Medium Risk'
  return 'Low Risk'
}

export function formatScore(score: number | null | undefined, decimals = 2): string {
  if (score == null) return 'N/A'
  return score.toFixed(decimals)
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}
