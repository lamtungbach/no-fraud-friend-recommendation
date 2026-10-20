import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  ShieldCheck,
  Network,
  Info,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react'

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Overview', end: true },
  { path: '/pymk', icon: Users, label: 'PYMK Demo' },
  { path: '/trust', icon: ShieldCheck, label: 'Trust & Fraud' },
  { path: '/network', icon: Network, label: 'Network Explorer' },
  { path: '/system', icon: Info, label: 'System Info' },
]

interface SidebarProps {
  mockMode: boolean
  onToggleMock: () => void
  apiError: string | null
}

export function Sidebar({ mockMode, onToggleMock, apiError }: SidebarProps) {
  return (
    <aside
      style={{
        width: 240,
        minWidth: 240,
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        padding: '0 0 16px 0',
      }}
    >
      {/* Logo */}
      <div
        style={{
          padding: '20px 20px 16px',
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 14,
              fontWeight: 700,
              color: '#fff',
              flexShrink: 0,
            }}
          >
            TF
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              Trust-Aware PYMK
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>MGTAB · Prototype</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '12px 8px' }}>
        {navItems.map(({ path, icon: Icon, label, end }) => (
          <NavLink
            key={path}
            to={path}
            end={end}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '9px 12px',
              borderRadius: 7,
              marginBottom: 2,
              textDecoration: 'none',
              fontSize: 13.5,
              fontWeight: isActive ? 600 : 400,
              color: isActive ? 'var(--accent-blue-light)' : 'var(--text-secondary)',
              background: isActive ? 'rgba(59,130,246,0.12)' : 'transparent',
              transition: 'all 0.15s ease',
            })}
          >
            <Icon size={16} />
            <span style={{ flex: 1 }}>{label}</span>
            {path === '/pymk' && (
              <ChevronRight size={12} style={{ opacity: 0.5 }} />
            )}
          </NavLink>
        ))}
      </nav>

      {/* Mode toggle */}
      <div style={{ padding: '0 12px' }}>
        {apiError && (
          <div
            style={{
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: 7,
              padding: '8px 10px',
              marginBottom: 8,
              fontSize: 11,
              color: '#f87171',
              display: 'flex',
              gap: 6,
              alignItems: 'flex-start',
            }}
          >
            <AlertTriangle size={12} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>Backend unreachable. Using mock data.</span>
          </div>
        )}
        <button
          onClick={onToggleMock}
          style={{
            width: '100%',
            padding: '8px 12px',
            borderRadius: 7,
            border: '1px solid var(--border-subtle)',
            background: mockMode ? 'rgba(245,158,11,0.12)' : 'var(--bg-elevated)',
            color: mockMode ? '#f59e0b' : 'var(--text-secondary)',
            fontSize: 12,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            transition: 'all 0.15s',
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: mockMode ? '#f59e0b' : '#10b981',
              flexShrink: 0,
            }}
          />
          {mockMode ? 'Demo Mode (Mock)' : 'Live API Mode'}
        </button>
      </div>
    </aside>
  )
}
