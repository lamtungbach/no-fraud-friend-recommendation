import { useState } from 'react'
import { Search, Brain } from 'lucide-react'
import { PageHeader, ErrorBanner, LoadingSpinner, EmptyState } from '../components/ui/shared.tsx'
import { TrustProfileCard } from '../components/TrustProfileCard.tsx'
import { getTrustProfile, getReasoningTrace } from '../api/trust'
import { getMockProfile, getMockReasoningTrace } from '../lib/mock'
import type { TrustProfile, ReasoningTrace } from '../api/types'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'
import { getTierColor } from '../lib/utils'

interface TrustPageProps {
  mockMode: boolean
}

export default function TrustDetection({ mockMode }: TrustPageProps) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [profile, setProfile] = useState<TrustProfile | null>(null)
  const [reasoning, setReasoning] = useState<ReasoningTrace | null>(null)
  const [showReasoning, setShowReasoning] = useState(false)

  const handleSearch = async () => {
    const uid = parseInt(input.trim(), 10)
    if (isNaN(uid) || uid < 0 || uid > 10199) {
      setError('Please enter a valid User ID between 0 and 10199.')
      return
    }
    setLoading(true)
    setError(null)
    setProfile(null)
    setReasoning(null)
    setShowReasoning(false)
    try {
      if (mockMode) {
        setProfile(getMockProfile(uid))
      } else {
        setProfile(await getTrustProfile(uid))
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch profile.')
    } finally {
      setLoading(false)
    }
  }

  const handleReason = async () => {
    if (!profile) return
    setLoading(true)
    try {
      if (mockMode) {
        setReasoning(getMockReasoningTrace(profile.user_id))
      } else {
        setReasoning(await getReasoningTrace(profile.user_id))
      }
      setShowReasoning(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to get reasoning.')
    } finally {
      setLoading(false)
    }
  }

  const radarData = profile
    ? [
        { subject: 'S_auth', A: profile.pillars.identity_auth * 100 },
        { subject: 'S_interact', A: profile.pillars.interaction_health * 100 },
        { subject: 'S_network', A: profile.pillars.network_hygiene * 100 },
        { subject: 'S_content', A: profile.pillars.content_safety * 100 },
      ]
    : []

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1100, margin: '0 auto' }}>
      <PageHeader
        title="Trust & Fraud Detection"
        subtitle="Investigate any account in the MGTAB dataset using the R-GCN trust scoring pipeline."
        mockMode={mockMode}
      />

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Search */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 12,
          padding: 20,
          marginBottom: 24,
          display: 'flex',
          gap: 12,
          alignItems: 'flex-end',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: '1 1 200px' }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
            Account ID (0 – 10,199)
          </label>
          <input
            type="number"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="e.g. 42"
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
        <button
          onClick={handleSearch}
          disabled={loading}
          style={{
            padding: '10px 20px',
            background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
            border: 'none',
            borderRadius: 7,
            color: '#fff',
            fontWeight: 600,
            fontSize: 14,
            cursor: loading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            opacity: loading ? 0.6 : 1,
            flexShrink: 0,
          }}
        >
          <Search size={15} />
          Investigate
        </button>
        {profile && (
          <button
            onClick={handleReason}
            disabled={loading}
            style={{
              padding: '10px 20px',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-default)',
              borderRadius: 7,
              color: 'var(--accent-blue-light)',
              fontWeight: 600,
              fontSize: 14,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              flexShrink: 0,
            }}
          >
            <Brain size={15} />
            Run Reasoning Trace
          </button>
        )}
      </div>

      {loading && <LoadingSpinner label="Analyzing account..." />}

      {!loading && !profile && !error && (
        <EmptyState message="Enter an account ID above to investigate its trust profile." />
      )}

      {!loading && profile && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'start' }}>
          {/* Profile card */}
          <TrustProfileCard profile={profile} />

          {/* Radar chart */}
          <div
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 10,
              padding: 20,
            }}
          >
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
              Pillar Scores Radar
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="var(--border-subtle)" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <Radar
                  name="Score"
                  dataKey="A"
                  stroke={getTierColor(profile.recommendation_tier)}
                  fill={getTierColor(profile.recommendation_tier)}
                  fillOpacity={0.25}
                />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 6, fontSize: 12 }}
                  formatter={(v: any) => [`${Number(v ?? 0).toFixed(1)} / 100`, 'Score']}
                />
              </RadarChart>
            </ResponsiveContainer>

            {/* Feature table */}
            <div style={{ marginTop: 12 }}>
              {[
                { label: 'Identity Auth (S_auth)', value: profile.pillars.identity_auth, note: 'Account verification & registration patterns' },
                { label: 'Interaction Health (S_interact)', value: profile.pillars.interaction_health, note: 'Spam & directional asymmetry signals' },
                { label: 'Network Hygiene (S_network)', value: profile.pillars.network_hygiene, note: 'Connection to suspicious neighbors' },
                { label: 'Content Safety (S_content)', value: profile.pillars.content_safety, note: 'URL / spam content ratio' },
              ].map(({ label, value, note }) => (
                <div key={label} style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 }}>
                    <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
                    <span style={{ fontWeight: 700, color: value < 0.4 ? '#ef4444' : value < 0.6 ? '#f59e0b' : '#10b981', fontFamily: 'monospace' }}>
                      {value.toFixed(4)}
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>{note}</div>
                  <div className="score-bar">
                    <div
                      className="score-bar-fill"
                      style={{ width: `${value * 100}%`, background: value < 0.4 ? '#ef4444' : value < 0.6 ? '#f59e0b' : '#10b981' }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Reasoning trace */}
          {showReasoning && reasoning && (
            <div
              style={{
                gridColumn: '1 / -1',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 10,
                padding: 20,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                <Brain size={16} color="var(--accent-blue)" />
                <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                  Trust Agent Reasoning Trace
                </span>
                <span
                  style={{
                    fontSize: 11,
                    padding: '2px 8px',
                    borderRadius: 4,
                    background: 'rgba(59,130,246,0.12)',
                    color: 'var(--accent-blue-light)',
                  }}
                >
                  Multi-step analysis (rule-based, not LLM)
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {reasoning.reasoning_trace.map((step, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      gap: 12,
                      alignItems: 'flex-start',
                      padding: '10px 14px',
                      background: 'var(--bg-elevated)',
                      borderRadius: 7,
                      fontSize: 13,
                    }}
                  >
                    <div
                      style={{
                        width: 22,
                        height: 22,
                        borderRadius: '50%',
                        background: 'rgba(59,130,246,0.2)',
                        color: 'var(--accent-blue-light)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 11,
                        fontWeight: 700,
                        flexShrink: 0,
                      }}
                    >
                      {i + 1}
                    </div>
                    <span style={{ color: 'var(--text-secondary)' }}>{step}</span>
                  </div>
                ))}
              </div>
              <div
                style={{
                  marginTop: 12,
                  padding: '10px 14px',
                  background: 'rgba(59,130,246,0.06)',
                  borderRadius: 7,
                  borderLeft: '3px solid var(--accent-blue)',
                  fontSize: 13,
                  color: 'var(--text-secondary)',
                }}
              >
                <strong style={{ color: 'var(--text-primary)' }}>Final Decision: </strong>
                {reasoning.decision}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
