import { PageHeader } from '../components/ui/shared.tsx'
import { ArrowRight, Database, Shield, GitMerge, FlaskConical } from 'lucide-react'

export default function SystemInfo() {
  return (
    <div style={{ padding: '28px 32px', maxWidth: 1100, margin: '0 auto' }}>
      <PageHeader
        title="System Information"
        subtitle="Technical overview of the Trust-Aware PYMK prototype."
      />

      {/* Architecture diagram */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 12,
          padding: 24,
          marginBottom: 24,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 20 }}>
          Processing Pipeline
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexWrap: 'wrap',
            justifyContent: 'center',
          }}
        >
          {[
            { icon: '👤', label: 'Target Account', sub: 'User selects ID' },
            { icon: '🔗', label: 'PYMK Candidate\nGeneration', sub: '2-hop graph retrieval\n(PyTorch serving index)' },
            { icon: '🛡', label: 'Trust/Fraud\nAssessment', sub: 'R-GCN + 4 pillar\nscoring (CSV lookup)' },
            { icon: '⚖️', label: 'Policy\nApplication', sub: 'DROP or DOWNRANK\n(FastAPI endpoint)' },
            { icon: '✅', label: 'Final\nRecommendations', sub: 'Trust-aware ranked list' },
          ].map((step, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 10,
                  padding: '12px 16px',
                  textAlign: 'center',
                  minWidth: 130,
                }}
              >
                <div style={{ fontSize: 22, marginBottom: 6 }}>{step.icon}</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'pre-line' }}>{step.label}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, whiteSpace: 'pre-line' }}>{step.sub}</div>
              </div>
              {i < 4 && <ArrowRight size={16} color="var(--accent-blue)" style={{ flexShrink: 0 }} />}
            </div>
          ))}
        </div>
      </div>

      {/* Component grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        <ComponentCard
          icon={<Shield size={16} />}
          title="Trust & Fraud Detection"
          color="#10b981"
          items={[
            { label: 'Model', value: 'Precomputed R-GCN scores (CSV)' },
            { label: 'Features', value: '4 trust pillars: identity, interaction, network, content' },
            { label: 'Output', value: 'p_bot ∈ [0,1], trust_score ∈ [0,100], Tier 1–4' },
            { label: 'Lookup', value: 'O(1) in-memory dictionary (10,200 profiles)' },
            { label: 'Source', value: 'mgtab_user_trust_profiles_v2.csv' },
          ]}
        />
        <ComponentCard
          icon={<GitMerge size={16} />}
          title="PYMK Recommendation Engine"
          color="#3b82f6"
          items={[
            { label: 'Method', value: 'Topology-based link prediction' },
            { label: 'Retrieval', value: 'Bounded 2-hop candidate expansion' },
            { label: 'Ranking', value: 'Graph topology scoring (RankingConfig)' },
            { label: 'Caching', value: 'Redis or no-op (configurable via env)' },
            { label: 'Graph', value: 'MGTAB mgtab-v1 · 10,199 nodes · 1,138,182 edges' },
          ]}
        />
        <ComponentCard
          icon={<ArrowRight size={16} />}
          title="Integration & Policy Layer"
          color="#f59e0b"
          items={[
            { label: 'DROP policy', value: '/api/v1/recommendations/safe-filter (Tier 1+2 only)' },
            { label: 'DOWNRANK policy', value: '/api/v1/recommendations/safe-rerank (Final_Score)' },
            { label: 'Formula', value: 'Final_Score = pymk × (trust/100) × dyadic_safety' },
            { label: 'Tier 3 rescue', value: 'Allowed if mutual_tier1_count ≥ threshold' },
            { label: 'Tier 4', value: 'Always blocked (100% quarantine)' },
          ]}
        />
        <ComponentCard
          icon={<Database size={16} />}
          title="Dataset & Features"
          color="#06b6d4"
          items={[
            { label: 'Dataset', value: 'MGTAB (Twitter bot detection benchmark)' },
            { label: 'Size', value: '10,200 users · 1,700,108 raw directed edges' },
            { label: 'License', value: 'CC BY-NC-ND 4.0 (upstream MGTAB)' },
            { label: 'Split', value: '70% train / 15% val / 15% test' },
            { label: 'Note', value: 'Prototype only — not a production social network' },
          ]}
        />
      </div>

      {/* API endpoints */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 12,
          padding: 20,
          marginBottom: 24,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 14 }}>
          Backend API Endpoints (FastAPI · localhost:8000)
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {[
            { method: 'GET', path: '/api/v1/trust/{user_id}', desc: 'Get trust profile for a single user' },
            { method: 'POST', path: '/api/v1/trust/batch', desc: 'Batch trust profile lookup' },
            { method: 'POST', path: '/api/v1/trust/reason', desc: 'Multi-step reasoning trace (TrustAgent)' },
            { method: 'POST', path: '/api/v1/recommendations/safe-filter', desc: 'DROP policy filter (Tier 1+2 pass)' },
            { method: 'POST', path: '/api/v1/recommendations/safe-rerank', desc: 'DOWNRANK policy with Final_Score' },
            { method: 'POST', path: '/v1/recommendations', desc: 'Safe PYMK Top-K via full engine' },
            { method: 'GET', path: '/health/live', desc: 'Liveness check' },
            { method: 'GET', path: '/docs', desc: 'Swagger UI documentation' },
          ].map(({ method, path, desc }) => (
            <div key={path} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '7px 10px', background: 'var(--bg-elevated)', borderRadius: 7 }}>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  padding: '2px 6px',
                  borderRadius: 4,
                  background: method === 'GET' ? 'rgba(16,185,129,0.15)' : 'rgba(59,130,246,0.15)',
                  color: method === 'GET' ? '#10b981' : '#60a5fa',
                  fontFamily: 'monospace',
                  flexShrink: 0,
                }}
              >
                {method}
              </span>
              <code style={{ fontSize: 12, color: '#a5b4fc', flex: '0 0 auto' }}>{path}</code>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Evaluation */}
      <div
        style={{
          background: 'rgba(59,130,246,0.06)',
          border: '1px solid rgba(59,130,246,0.2)',
          borderRadius: 12,
          padding: 16,
          fontSize: 13,
          color: 'var(--text-secondary)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <FlaskConical size={14} color="var(--accent-blue)" />
          <strong style={{ color: 'var(--text-primary)', fontSize: 14 }}>Research Prototype Disclaimer</strong>
        </div>
        This is an academic prototype using the public MGTAB dataset. It evaluates trust scoring and candidate filtering logic, but is not connected to any production social network. Trust profiles are precomputed from graph features — they are not real-time model inference. Model evaluation metrics are available in <code>artifacts/sprint2/</code>. The system does not have access to real user data or private accounts.
      </div>
    </div>
  )
}

interface ComponentCardProps {
  icon: React.ReactNode
  title: string
  color: string
  items: { label: string; value: string }[]
}

function ComponentCard({ icon, title, color, items }: ComponentCardProps) {
  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 12,
        padding: 20,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{ color }}>{icon}</span>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {items.map(({ label, value }) => (
          <div key={label} style={{ display: 'flex', gap: 8 }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)', minWidth: 100, flexShrink: 0 }}>{label}:</span>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
