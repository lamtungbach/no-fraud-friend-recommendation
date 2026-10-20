import { Users, ShieldOff, ShieldCheck, AlertTriangle, CheckCircle } from 'lucide-react'
import { PageHeader, StatCard } from '../components/ui/shared.tsx'
import { MOCK_OVERVIEW_STATS } from '../lib/mock'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis,
} from 'recharts'

interface OverviewProps {
  mockMode: boolean
}

const TIER_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444']
const TIER_LABELS = ['Tier 1 (Verified)', 'Tier 2 (Standard)', 'Tier 3 (Restricted)', 'Tier 4 (Quarantined)']

const SCORE_DISTRIBUTION = [
  { range: '0-10', count: 1240 },
  { range: '10-20', count: 2180 },
  { range: '20-30', count: 1020 },
  { range: '30-40', count: 820 },
  { range: '40-50', count: 495 },
  { range: '50-60', count: 620 },
  { range: '60-70', count: 810 },
  { range: '70-80', count: 635 },
  { range: '80-90', count: 290 },
  { range: '90-100', count: 90 },
]

const SAMPLE_ACCOUNTS = [
  { id: 42, tier: 'Tier 1', trust: 82.4, p_bot: '12.0%', status: 'Human', label: 'Safe' },
  { id: 100, tier: 'Tier 2', trust: 67.3, p_bot: '28.0%', status: 'Human', label: 'Safe' },
  { id: 250, tier: 'Tier 3', trust: 52.1, p_bot: '55.0%', status: 'Human', label: 'Caution' },
  { id: 500, tier: 'Tier 4', trust: 11.2, p_bot: '89.0%', status: 'Bot', label: 'Fraud' },
  { id: 750, tier: 'Tier 4', trust: 8.5, p_bot: '93.0%', status: 'Bot', label: 'Fraud' },
]

export default function Overview({ mockMode }: OverviewProps) {
  const stats = MOCK_OVERVIEW_STATS

  const tierPieData = [
    { name: TIER_LABELS[0], value: stats.tier1_count, color: TIER_COLORS[0] },
    { name: TIER_LABELS[1], value: stats.tier2_count, color: TIER_COLORS[1] },
    { name: TIER_LABELS[2], value: stats.tier3_count, color: TIER_COLORS[2] },
    { name: TIER_LABELS[3], value: stats.tier4_count, color: TIER_COLORS[3] },
  ]

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1200, margin: '0 auto' }}>
      <PageHeader
        title="Overview Dashboard"
        subtitle="Summary statistics from the MGTAB trust profile dataset (10,200 accounts)."
        mockMode={mockMode}
      />

      {/* Stat cards */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
        <StatCard
          label="Total Accounts Analyzed"
          value={stats.total_users.toLocaleString()}
          sub="MGTAB dataset"
          icon={<Users size={16} />}
          color="var(--accent-blue-light)"
        />
        <StatCard
          label="Suspicious / Bot Accounts"
          value={stats.suspicious_users.toLocaleString()}
          sub={`${((stats.suspicious_users / stats.total_users) * 100).toFixed(1)}% of total`}
          icon={<ShieldOff size={16} />}
          color="#ef4444"
        />
        <StatCard
          label="Safe Accounts (Tier 1+2)"
          value={(stats.tier1_count + stats.tier2_count).toLocaleString()}
          sub="Eligible for recommendation"
          icon={<ShieldCheck size={16} />}
          color="#10b981"
        />
        <StatCard
          label="Tier 3 (Restricted)"
          value={stats.tier3_count.toLocaleString()}
          sub="Context-dependent admission"
          icon={<AlertTriangle size={16} />}
          color="#f59e0b"
        />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: 20, marginBottom: 24 }}>
        {/* Tier pie */}
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 12,
            padding: 20,
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
            Account Trust Distribution
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={tierPieData}
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={3}
                dataKey="value"
              >
                {tierPieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 6, fontSize: 12 }}
                formatter={(v) => [Number(v).toLocaleString(), 'Accounts']}
              />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
            {tierPieData.map((d, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: d.color, flexShrink: 0 }} />
                <span style={{ flex: 1, color: 'var(--text-secondary)' }}>{d.name}</span>
                <span style={{ fontWeight: 600, color: d.color }}>{d.value.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Score histogram */}
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 12,
            padding: 20,
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
            Trust Score Distribution (S_trust)
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={SCORE_DISTRIBUTION} barSize={22}>
              <XAxis dataKey="range" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 6, fontSize: 12 }}
                cursor={{ fill: 'rgba(255,255,255,0.04)' }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]} name="Accounts">
                {SCORE_DISTRIBUTION.map((entry, i) => (
                  <Cell key={i} fill={i < 4 ? '#ef4444' : i < 6 ? '#f59e0b' : i < 7 ? '#3b82f6' : '#10b981'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, textAlign: 'center' }}>
            Score range 0–100 · Red = Tier 4 · Orange = Tier 3 · Blue = Tier 2 · Green = Tier 1
          </div>
        </div>
      </div>

      {/* Recent sample accounts table */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 12,
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>Sample Account Analysis</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Representative accounts from the MGTAB dataset</div>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--bg-elevated)' }}>
              {['Account ID', 'Trust Score', 'Bot Risk', 'Tier', 'Label', 'Recommendable'].map(h => (
                <th key={h} style={{ padding: '8px 16px', textAlign: 'left', fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {SAMPLE_ACCOUNTS.map((acc, i) => (
              <tr key={acc.id} style={{ borderTop: i > 0 ? '1px solid var(--border-subtle)' : 'none' }}>
                <td style={{ padding: '10px 16px', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>#{acc.id}</td>
                <td style={{ padding: '10px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: acc.trust >= 80 ? '#10b981' : acc.trust >= 65 ? '#3b82f6' : acc.trust >= 45 ? '#f59e0b' : '#ef4444' }}>{acc.trust}</span>
                    <div className="score-bar" style={{ width: 60 }}>
                      <div className="score-bar-fill" style={{ width: `${acc.trust}%`, background: acc.trust >= 80 ? '#10b981' : acc.trust >= 65 ? '#3b82f6' : acc.trust >= 45 ? '#f59e0b' : '#ef4444' }} />
                    </div>
                  </div>
                </td>
                <td style={{ padding: '10px 16px', fontSize: 13, color: parseFloat(acc.p_bot) >= 75 ? '#ef4444' : parseFloat(acc.p_bot) >= 45 ? '#f59e0b' : '#10b981' }}>{acc.p_bot}</td>
                <td style={{ padding: '10px 16px' }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: acc.tier === 'Tier 1' ? '#10b981' : acc.tier === 'Tier 2' ? '#3b82f6' : acc.tier === 'Tier 3' ? '#f59e0b' : '#ef4444' }}>{acc.tier}</span>
                </td>
                <td style={{ padding: '10px 16px', fontSize: 13, color: 'var(--text-secondary)' }}>{acc.status}</td>
                <td style={{ padding: '10px 16px' }}>
                  {acc.label === 'Safe' ? (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#10b981' }}>
                      <CheckCircle size={13} /> Yes
                    </span>
                  ) : (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#ef4444' }}>
                      <ShieldOff size={13} /> No
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
