import { useState, useCallback } from 'react'
import { RefreshCw, ArrowRight, Filter, TrendingDown, CheckCircle2, XCircle } from 'lucide-react'
import { PageHeader, ErrorBanner, LoadingSpinner, EmptyState } from '../components/ui/shared.tsx'
import { getTrustProfile, filterSafeCandidates, rerankCandidates, getBatchTrustProfiles } from '../api/trust'
import {
  getMockCandidates,
  getMockProfile,
  getMockSafeFilterResponse,
  getMockReRankResponse,
} from '../lib/mock'
import { getTierClass, getTierLabel, formatScore } from '../lib/utils'
import type { TrustProfile, RecommendationTier, CandidateFilterItem, CandidateReRankItem } from '../api/types'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

type Policy = 'DROP' | 'DOWNRANK'

// A unified candidate shape for display
interface DisplayCandidate {
  id: number
  pymkRank: number // 1-based original rank
  pymkScore: number
  trustScore: number | null
  pBot: number | null
  tier: RecommendationTier | null
  finalScore: number | null
  decision: 'KEPT' | 'DOWNRANKED' | 'FILTERED'
  reason: string
  isAllowed: boolean
}

interface PYMKPageProps {
  mockMode: boolean
}

const TOP_CANDIDATES = 12

export default function PYMKDemo({ mockMode }: PYMKPageProps) {
  const [targetId, setTargetId] = useState<string>('42')
  const [policy, setPolicy] = useState<Policy>('DROP')
  const [tier3Threshold, setTier3Threshold] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [targetProfile, setTargetProfile] = useState<TrustProfile | null>(null)
  const [originalCandidates, setOriginalCandidates] = useState<DisplayCandidate[]>([])
  const [filteredCandidates, setFilteredCandidates] = useState<DisplayCandidate[]>([])
  const [stats, setStats] = useState<{ total: number; kept: number; downranked: number; filtered: number } | null>(null)
  const [showComparison, setShowComparison] = useState(false)

  const handleGenerate = useCallback(async () => {
    const uid = parseInt(targetId.trim(), 10)
    if (isNaN(uid) || uid < 0 || uid > 10199) {
      setError('Please enter a valid User ID between 0 and 10199.')
      return
    }
    setLoading(true)
    setError(null)
    setStats(null)
    setShowComparison(false)

    try {
      // Step 1: Get target user profile
      let tProfile: TrustProfile
      if (mockMode) {
        tProfile = getMockProfile(uid)
      } else {
        tProfile = await getTrustProfile(uid)
      }
      setTargetProfile(tProfile)

      // Step 2: Get PYMK candidates (simulated as 2-hop neighbors)
      const candidateIds = getMockCandidates(uid, TOP_CANDIDATES)
      const pymkScores: Record<number, number> = {}
      candidateIds.forEach((id, i) => { pymkScores[id] = parseFloat((1.0 - i * 0.07).toFixed(4)) })

      // Step 3: Get trust profiles for all candidates
      let trustProfiles: Record<number, TrustProfile> = {}
      if (mockMode) {
        for (const id of candidateIds) {
          trustProfiles[id] = getMockProfile(id)
        }
      } else {
        try {
          const profiles = await getBatchTrustProfiles(candidateIds)
          for (const p of profiles) { trustProfiles[p.user_id] = p }
        } catch {
          // Fall back to per-id fetch
          for (const id of candidateIds) {
            try { trustProfiles[id] = await getTrustProfile(id) } catch { /* skip */ }
          }
        }
      }

      // Build original list
      const original: DisplayCandidate[] = candidateIds.map((id, i) => {
        const tp = trustProfiles[id]
        return {
          id,
          pymkRank: i + 1,
          pymkScore: pymkScores[id],
          trustScore: tp?.trust_score ?? null,
          pBot: tp?.p_bot ?? null,
          tier: tp?.recommendation_tier ?? null,
          finalScore: null,
          decision: 'KEPT',
          reason: tp?.decision ?? 'Profile not found',
          isAllowed: tp?.is_recommendable ?? false,
        }
      })
      setOriginalCandidates(original)

      // Step 4: Apply policy
      if (policy === 'DROP') {
        let filterResp
        if (mockMode) {
          filterResp = getMockSafeFilterResponse(uid, candidateIds)
        } else {
          filterResp = await filterSafeCandidates({ target_user_id: uid, candidate_user_ids: candidateIds })
        }
        const safeSet = new Set(filterResp.safe_candidates.map((c: CandidateFilterItem) => c.user_id))
        const filtered: DisplayCandidate[] = original
          .filter(c => safeSet.has(c.id))
          .map(c => ({ ...c, decision: 'KEPT' as const }))
        const dropped = original.filter(c => !safeSet.has(c.id)).length
        setFilteredCandidates(filtered)
        setStats({ total: original.length, kept: filtered.length, downranked: 0, filtered: dropped })
      } else {
        // DOWNRANK
        const inputs = candidateIds.map(id => ({
          candidate_id: id,
          pymk_score: pymkScores[id],
          mutual_total_count: 0,
          mutual_tier1_count: 0,
          asymmetry_penalty: 0.0,
        }))
        let rerankResp
        if (mockMode) {
          rerankResp = getMockReRankResponse(uid, candidateIds)
        } else {
          rerankResp = await rerankCandidates({ target_user_id: uid, candidates: inputs, tier3_threshold: tier3Threshold })
        }

        const passedMap: Record<number, CandidateReRankItem> = {}
        rerankResp.ranked_candidates.forEach((r: CandidateReRankItem) => { passedMap[r.candidate_id] = r })
        const blockedMap: Record<number, CandidateReRankItem> = {}
        rerankResp.blocked_candidates.forEach((r: CandidateReRankItem) => { blockedMap[r.candidate_id] = r })

        const kept: DisplayCandidate[] = rerankResp.ranked_candidates.map((r: CandidateReRankItem) => {
          const orig = original.find(o => o.id === r.candidate_id)
          const isDownranked = r.recommendation_tier === 'TIER_3_RESTRICTED_CAUTION'
          return {
            id: r.candidate_id,
            pymkRank: orig?.pymkRank ?? 99,
            pymkScore: r.pymk_score,
            trustScore: r.trust_score,
            pBot: orig?.pBot ?? null,
            tier: r.recommendation_tier,
            finalScore: r.final_ranking_score,
            decision: isDownranked ? 'DOWNRANKED' : 'KEPT',
            reason: r.reason,
            isAllowed: true,
          }
        })
        const blocked: DisplayCandidate[] = rerankResp.blocked_candidates.map((r: CandidateReRankItem) => {
          const orig = original.find(o => o.id === r.candidate_id)
          return {
            id: r.candidate_id,
            pymkRank: orig?.pymkRank ?? 99,
            pymkScore: r.pymk_score,
            trustScore: r.trust_score,
            pBot: orig?.pBot ?? null,
            tier: r.recommendation_tier,
            finalScore: r.final_ranking_score,
            decision: 'FILTERED' as const,
            reason: r.reason,
            isAllowed: false,
          }
        })
        const result = [...kept, ...blocked]
        setFilteredCandidates(result)
        const downrankedCount = kept.filter(c => c.decision === 'DOWNRANKED').length
        setStats({
          total: original.length,
          kept: kept.filter(c => c.decision === 'KEPT').length,
          downranked: downrankedCount,
          filtered: blocked.length,
        })
      }
      setShowComparison(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'An unexpected error occurred.')
    } finally {
      setLoading(false)
    }
  }, [targetId, policy, tier3Threshold, mockMode])


  const chartData = stats
    ? [
        { name: 'Kept', value: stats.kept, color: '#10b981' },
        { name: 'Downranked', value: stats.downranked, color: '#f59e0b' },
        { name: 'Filtered', value: stats.filtered, color: '#ef4444' },
      ].filter(d => d.value > 0)
    : []

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1200, margin: '0 auto' }}>
      <PageHeader
        title="PYMK Recommendation Demo"
        subtitle="Select a target account and a trust policy to see how fraud detection changes recommendations."
        mockMode={mockMode}
      />

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Control Panel */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 12,
          padding: 20,
          marginBottom: 24,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 16 }}>
          Configuration
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {/* Target user input */}
          <div style={{ flex: '1 1 160px' }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
              Target Account (User ID 0–10199)
            </label>
            <input
              type="number"
              value={targetId}
              onChange={e => setTargetId(e.target.value)}
              min={0}
              max={10199}
              style={{
                width: '100%',
                padding: '9px 12px',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-default)',
                borderRadius: 7,
                color: 'var(--text-primary)',
                fontSize: 14,
                outline: 'none',
              }}
            />
          </div>

          {/* Policy selector */}
          <div style={{ flex: '1 1 200px' }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
              Suspicious Account Policy
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['DROP', 'DOWNRANK'] as Policy[]).map(p => (
                <button
                  key={p}
                  onClick={() => setPolicy(p)}
                  style={{
                    flex: 1,
                    padding: '9px 12px',
                    borderRadius: 7,
                    border: `1px solid ${policy === p ? 'var(--accent-blue)' : 'var(--border-subtle)'}`,
                    background: policy === p ? 'rgba(59,130,246,0.15)' : 'var(--bg-elevated)',
                    color: policy === p ? 'var(--accent-blue-light)' : 'var(--text-secondary)',
                    fontSize: 13,
                    fontWeight: policy === p ? 600 : 400,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 6,
                  }}
                >
                  {p === 'DROP' ? <Filter size={13} /> : <TrendingDown size={13} />}
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Tier3 threshold (DOWNRANK only) */}
          {policy === 'DOWNRANK' && (
            <div style={{ flex: '1 1 180px' }}>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                Tier-3 Rescue Threshold (mutual Tier-1 friends)
              </label>
              <input
                type="number"
                value={tier3Threshold}
                onChange={e => setTier3Threshold(parseInt(e.target.value) || 5)}
                min={1}
                max={20}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 7,
                  color: 'var(--text-primary)',
                  fontSize: 14,
                  outline: 'none',
                }}
              />
            </div>
          )}

          {/* Generate button */}
          <button
            onClick={handleGenerate}
            disabled={loading}
            style={{
              padding: '10px 24px',
              background: loading ? 'var(--bg-elevated)' : 'linear-gradient(135deg, #3b82f6, #06b6d4)',
              border: 'none',
              borderRadius: 7,
              color: '#fff',
              fontWeight: 600,
              fontSize: 14,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              flexShrink: 0,
              opacity: loading ? 0.6 : 1,
            }}
          >
            <RefreshCw size={15} style={{ animation: loading ? 'spin 0.8s linear infinite' : 'none' }} />
            {loading ? 'Running...' : 'Generate'}
          </button>
        </div>

        {/* Policy description */}
        <div
          style={{
            marginTop: 12,
            padding: '8px 12px',
            background: 'var(--bg-elevated)',
            borderRadius: 6,
            fontSize: 12,
            color: 'var(--text-muted)',
            borderLeft: `3px solid ${policy === 'DROP' ? '#ef4444' : '#f59e0b'}`,
          }}
        >
          {policy === 'DROP'
            ? '🚫 DROP policy: Tier 3 & Tier 4 candidates are removed entirely from the final list. Only Tier 1 & Tier 2 users are shown.'
            : '📉 DOWNRANK policy: Tier 3 candidates are moved to the bottom (final_score = pymk_score × trust/100 × dyadic_safety). Tier 4 candidates are still always removed.'
          }
        </div>
      </div>

      {loading && <LoadingSpinner label="Fetching profiles and applying trust policy..." />}

      {!loading && !showComparison && !error && (
        <EmptyState message="Configure the target account and policy above, then click Generate to run the demo." />
      )}

      {!loading && showComparison && stats && (
        <>
          {/* Summary row */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
            {targetProfile && (
              <div
                style={{
                  flex: '0 0 auto',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 10,
                  padding: '14px 18px',
                  display: 'flex',
                  gap: 14,
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Target Account</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>
                    User #{targetProfile.user_id}
                  </div>
                  <span
                    className={getTierClass(targetProfile.recommendation_tier)}
                    style={{ fontSize: 11, padding: '2px 6px', borderRadius: 4, fontWeight: 600 }}
                  >
                    {getTierLabel(targetProfile.recommendation_tier)}
                  </span>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Trust Score</div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent-blue-light)' }}>
                    {targetProfile.trust_score.toFixed(1)}
                  </div>
                </div>
              </div>
            )}
            {[
              { label: 'Total Candidates', value: stats.total, color: 'var(--text-primary)' },
              { label: 'Kept', value: stats.kept, color: '#10b981' },
              { label: policy === 'DROP' ? 'Filtered (Dropped)' : 'Downranked', value: policy === 'DROP' ? stats.filtered : stats.downranked, color: '#f59e0b' },
              ...(policy === 'DOWNRANK' ? [{ label: 'Filtered (T4)', value: stats.filtered, color: '#ef4444' }] : []),
            ].map(s => (
              <div
                key={s.label}
                style={{
                  flex: '1 1 100px',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 10,
                  padding: '14px 18px',
                }}
              >
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{s.label}</div>
                <div style={{ fontSize: 26, fontWeight: 700, color: s.color }}>{s.value}</div>
              </div>
            ))}

            {/* Mini chart */}
            {chartData.length > 0 && (
              <div
                style={{
                  flex: '1 1 180px',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 10,
                  padding: '14px 18px',
                }}
              >
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>Distribution</div>
                <ResponsiveContainer width="100%" height={60}>
                  <BarChart data={chartData} barSize={24}>
                    <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis hide />
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 6, fontSize: 12 }}
                      cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {chartData.map((entry, index) => <Cell key={index} fill={entry.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Comparison table */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 16, marginBottom: 24, alignItems: 'start' }}>
            {/* Original */}
            <CandidateTable
              title="Original PYMK List"
              subtitle="Before trust filtering — ranked by link-prediction score"
              candidates={originalCandidates}
              scoreKey="pymkScore"
              showFinalScore={false}
            />

            {/* Arrow */}
            <div style={{ display: 'flex', alignItems: 'center', paddingTop: 50 }}>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 4,
                  color: 'var(--text-muted)',
                  fontSize: 11,
                }}
              >
                <ArrowRight size={20} color="var(--accent-blue)" />
                <span>{policy}</span>
                <span>Policy</span>
              </div>
            </div>

            {/* Filtered */}
            <CandidateTable
              title="Trust-Aware Final List"
              subtitle={policy === 'DROP' ? 'After DROP — suspicious removed' : 'After DOWNRANK — reordered by final score'}
              candidates={filteredCandidates}
              scoreKey={policy === 'DOWNRANK' ? 'finalScore' : 'pymkScore'}
              showFinalScore={policy === 'DOWNRANK'}
            />
          </div>
        </>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

// ─── Candidate table ────────────────────────────────────────────────────────

interface CandidateTableProps {
  title: string
  subtitle: string
  candidates: DisplayCandidate[]
  scoreKey: 'pymkScore' | 'finalScore'
  showFinalScore: boolean
}

function CandidateTable({ title, subtitle, candidates, scoreKey, showFinalScore }: CandidateTableProps) {
  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 12,
        overflow: 'hidden',
      }}
    >
      <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{subtitle}</div>
      </div>
      {candidates.length === 0 ? (
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
          All candidates removed
        </div>
      ) : (
        <div>
          {/* Header */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '36px 1fr 70px 70px auto 90px',
              padding: '6px 16px',
              fontSize: 10,
              color: 'var(--text-muted)',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              borderBottom: '1px solid var(--border-subtle)',
              background: 'var(--bg-elevated)',
            }}
          >
            <span>#</span>
            <span>Candidate</span>
            <span>PYMK</span>
            <span>Trust</span>
            <span>Tier</span>
            <span style={{ textAlign: 'right' }}>Decision</span>
          </div>
          {candidates.map((c, i) => (
            <div
              key={c.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '36px 1fr 70px 70px auto 90px',
                padding: '8px 16px',
                alignItems: 'center',
                borderBottom: i < candidates.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                background: c.decision === 'FILTERED' ? 'rgba(239,68,68,0.04)' : c.decision === 'DOWNRANKED' ? 'rgba(245,158,11,0.04)' : 'transparent',
                opacity: c.decision === 'FILTERED' ? 0.65 : 1,
              }}
            >
              <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>{i + 1}</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>#{c.id}</div>
                {c.decision === 'DOWNRANKED' && (
                  <div style={{ fontSize: 10, color: '#f59e0b' }}>was #{c.pymkRank}</div>
                )}
              </div>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                {showFinalScore && c.finalScore != null
                  ? formatScore(c.finalScore, 3)
                  : formatScore(c[scoreKey] ?? c.pymkScore, 3)}
              </span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: c.trustScore != null ? (c.trustScore >= 80 ? '#10b981' : c.trustScore >= 65 ? '#3b82f6' : c.trustScore >= 45 ? '#f59e0b' : '#ef4444') : 'var(--text-muted)',
                }}
              >
                {c.trustScore != null ? c.trustScore.toFixed(0) : 'N/A'}
              </span>
              {c.tier ? (
                <span
                  className={getTierClass(c.tier)}
                  style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, fontWeight: 600, whiteSpace: 'nowrap' }}
                >
                  {c.tier === 'TIER_1_VERIFIED_SAFE' ? 'T1' : c.tier === 'TIER_2_STANDARD_TRUST' ? 'T2' : c.tier === 'TIER_3_RESTRICTED_CAUTION' ? 'T3' : 'T4'}
                </span>
              ) : <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>?</span>}
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
                {c.decision === 'KEPT' ? <CheckCircle2 size={12} color="#10b981" /> : c.decision === 'DOWNRANKED' ? <TrendingDown size={12} color="#f59e0b" /> : <XCircle size={12} color="#ef4444" />}
                <span style={{ fontSize: 11, color: decisionColor(c.decision), fontWeight: 600 }}>{c.decision}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )

  function decisionColor(d: string) {
    if (d === 'KEPT') return '#10b981'
    if (d === 'DOWNRANKED') return '#f59e0b'
    return '#ef4444'
  }
}
