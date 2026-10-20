import type { TrustProfile } from '../api/types'
import { getTierClass, getTierLabel, getRiskColor, getRiskLabel } from '../lib/utils'

interface TrustProfileCardProps {
  profile: TrustProfile
  compact?: boolean
}

export function TrustProfileCard({ profile, compact = false }: TrustProfileCardProps) {
  const tierClass = getTierClass(profile.recommendation_tier)
  const riskColor = getRiskColor(profile.p_bot)

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 10,
        padding: compact ? '12px 16px' : '20px',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: compact ? 15 : 18, fontWeight: 700, color: 'var(--text-primary)' }}>
            User #{profile.user_id}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
            {profile.ground_truth_label} · {profile.split_set}
          </div>
        </div>
        <span
          className={tierClass}
          style={{
            padding: '4px 10px',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          {getTierLabel(profile.recommendation_tier)}
        </span>
      </div>

      {/* Main scores */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Trust Score</div>
          <div style={{ fontSize: compact ? 22 : 28, fontWeight: 700, color: 'var(--accent-blue-light)' }}>
            {profile.trust_score.toFixed(1)}
          </div>
          <div className="score-bar" style={{ marginTop: 4 }}>
            <div
              className="score-bar-fill"
              style={{
                width: `${profile.trust_score}%`,
                background: 'linear-gradient(90deg, #3b82f6, #06b6d4)',
              }}
            />
          </div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Bot Risk (p_bot)</div>
          <div style={{ fontSize: compact ? 22 : 28, fontWeight: 700, color: riskColor }}>
            {(profile.p_bot * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: 11, color: riskColor, marginTop: 4 }}>{getRiskLabel(profile.p_bot)}</div>
        </div>
      </div>

      {/* Pillars */}
      {!compact && (
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10, fontWeight: 500 }}>
            4 Trust Pillars
          </div>
          {[
            { key: 'identity_auth', label: 'Identity Auth (S_auth)', value: profile.pillars.identity_auth },
            { key: 'interaction_health', label: 'Interaction Health (S_interact)', value: profile.pillars.interaction_health },
            { key: 'network_hygiene', label: 'Network Hygiene (S_network)', value: profile.pillars.network_hygiene },
            { key: 'content_safety', label: 'Content Safety (S_content)', value: profile.pillars.content_safety },
          ].map(({ label, value }) => (
            <div key={label} style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
                <span style={{ color: value < 0.4 ? '#ef4444' : value < 0.6 ? '#f59e0b' : '#10b981', fontWeight: 600 }}>
                  {value.toFixed(3)}
                </span>
              </div>
              <div className="score-bar">
                <div
                  className="score-bar-fill"
                  style={{
                    width: `${value * 100}%`,
                    background: value < 0.4 ? '#ef4444' : value < 0.6 ? '#f59e0b' : '#10b981',
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Decision */}
      <div
        style={{
          marginTop: 12,
          padding: '8px 12px',
          background: 'var(--bg-elevated)',
          borderRadius: 6,
          fontSize: 12,
          color: 'var(--text-secondary)',
        }}
      >
        {profile.decision}
      </div>
    </div>
  )
}
