interface PageHeaderProps {
  title: string
  subtitle?: string
  mockMode?: boolean
  children?: React.ReactNode
}

export function PageHeader({ title, subtitle, mockMode, children }: PageHeaderProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        marginBottom: 24,
        flexWrap: 'wrap',
        gap: 12,
      }}
    >
      <div>
        <h1
          style={{
            margin: 0,
            fontSize: 22,
            fontWeight: 700,
            color: 'var(--text-primary)',
            letterSpacing: '-0.3px',
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-muted)' }}>{subtitle}</p>
        )}
        {mockMode && (
          <span
            style={{
              display: 'inline-block',
              marginTop: 6,
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 600,
              background: 'rgba(245,158,11,0.15)',
              color: '#f59e0b',
              border: '1px solid rgba(245,158,11,0.3)',
            }}
          >
            ⚠ DEMO MODE — Sample data only, not real predictions
          </span>
        )}
      </div>
      {children && <div style={{ display: 'flex', gap: 8 }}>{children}</div>}
    </div>
  )
}

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  color?: string
  icon?: React.ReactNode
}

export function StatCard({ label, value, sub, color = 'var(--accent-blue)', icon }: StatCardProps) {
  return (
    <div
      className="card-hover"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 10,
        padding: '16px 20px',
        flex: '1 1 160px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        {icon && <span style={{ color }}>{icon}</span>}
        <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>{label}</span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

interface ErrorBannerProps {
  message: string
  onDismiss?: () => void
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div
      style={{
        background: 'rgba(239,68,68,0.1)',
        border: '1px solid rgba(239,68,68,0.3)',
        borderRadius: 8,
        padding: '12px 16px',
        marginBottom: 16,
        color: '#f87171',
        fontSize: 13,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <span>⚠ {message}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: 16 }}
        >
          ×
        </button>
      )}
    </div>
  )
}

export function LoadingSpinner({ label = 'Loading...' }: { label?: string }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        padding: 48,
        color: 'var(--text-muted)',
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          border: '3px solid var(--border-subtle)',
          borderTop: '3px solid var(--accent-blue)',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }}
      />
      <span style={{ fontSize: 13 }}>{label}</span>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div
      style={{
        textAlign: 'center',
        padding: 48,
        color: 'var(--text-muted)',
        fontSize: 14,
      }}
    >
      <div style={{ fontSize: 32, marginBottom: 8 }}>—</div>
      {message}
    </div>
  )
}
