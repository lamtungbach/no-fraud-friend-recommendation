import { useState, useCallback } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Sidebar } from './components/layout/Sidebar.tsx'
import Overview from './pages/Overview.tsx'
import PYMKDemo from './pages/PYMKDemo.tsx'
import TrustDetection from './pages/TrustDetection.tsx'
import NetworkExplorer from './pages/NetworkExplorer.tsx'
import SystemInfo from './pages/SystemInfo.tsx'
import { apiClient } from './api/client'

export default function App() {
  const [mockMode, setMockMode] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const handleToggleMock = useCallback(async () => {
    if (!mockMode) {
      // Try a quick health check before switching to live mode
      try {
        await apiClient.get('/health/live')
        setApiError(null)
        setMockMode(false)
      } catch {
        setApiError('Backend unreachable')
        setMockMode(true)
      }
    } else {
      setMockMode(false)
    }
  }, [mockMode])

  return (
    <BrowserRouter>
      <div
        style={{
          display: 'flex',
          height: '100vh',
          overflow: 'hidden',
          background: 'var(--bg-base)',
        }}
      >
        <Sidebar mockMode={mockMode} onToggleMock={handleToggleMock} apiError={apiError} />
        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            background: 'var(--bg-base)',
          }}
        >
          <Routes>
            <Route path="/" element={<Overview mockMode={mockMode} />} />
            <Route path="/pymk" element={<PYMKDemo mockMode={mockMode} />} />
            <Route path="/trust" element={<TrustDetection mockMode={mockMode} />} />
            <Route path="/network" element={<NetworkExplorer mockMode={mockMode} />} />
            <Route path="/system" element={<SystemInfo />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
