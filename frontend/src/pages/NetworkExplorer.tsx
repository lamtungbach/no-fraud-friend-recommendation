import { useEffect, useRef, useState, useCallback } from 'react'
import cytoscape from 'cytoscape'
import type { Core, NodeSingular } from 'cytoscape'
import { Search, ZoomIn, ZoomOut, RefreshCw } from 'lucide-react'
import { PageHeader, ErrorBanner, LoadingSpinner } from '../components/ui/shared.tsx'
import { getMockProfile, getMockCandidates } from '../lib/mock'
import { getTierColor, getTierLabel } from '../lib/utils'
import type { TrustProfile } from '../api/types'

interface NetworkExplorerProps {
  mockMode: boolean
}

interface NodeDetail {
  id: number
  profile: TrustProfile
  edges: number
}

function buildGraphData(centerUserId: number, depth = 2) {
  const nodes = new Map<number, TrustProfile>()
  const edges: { source: number; target: number }[] = []
  const queue = [{ id: centerUserId, level: 0 }]
  const visited = new Set<number>()

  while (queue.length > 0) {
    const { id, level } = queue.shift()!
    if (visited.has(id)) continue
    visited.add(id)
    nodes.set(id, getMockProfile(id))

    if (level < depth) {
      const neighbors = getMockCandidates(id, level === 0 ? 8 : 4)
      for (const n of neighbors) {
        if (!visited.has(n)) {
          edges.push({ source: id, target: n })
          queue.push({ id: n, level: level + 1 })
        }
      }
    }
  }
  return { nodes, edges }
}

export default function NetworkExplorer({ mockMode }: NetworkExplorerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const [centerId, setCenterId] = useState('42')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<NodeDetail | null>(null)

  const buildGraph = useCallback((centerUserId: number) => {
    if (!containerRef.current) return
    setLoading(true)
    setError(null)
    setSelectedNode(null)

    try {
      const { nodes, edges } = buildGraphData(centerUserId, 2)

      const elements: cytoscape.ElementDefinition[] = []
      nodes.forEach((profile, id) => {
        elements.push({
          data: {
            id: String(id),
            label: `#${id}`,
            tier: profile.recommendation_tier,
            trust: profile.trust_score,
            isCenter: id === centerUserId,
          },
        })
      })
      edges.forEach(({ source, target }) => {
        elements.push({
          data: {
            id: `e-${source}-${target}`,
            source: String(source),
            target: String(target),
          },
        })
      })

      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }

      const cy = cytoscape({
        container: containerRef.current,
        elements,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': (ele: NodeSingular) => getTierColor(ele.data('tier')),
              'border-width': (ele: NodeSingular) => ele.data('isCenter') ? 3 : 1.5,
              'border-color': (ele: NodeSingular) => ele.data('isCenter') ? '#fff' : 'rgba(255,255,255,0.2)',
              'width': (ele: NodeSingular) => ele.data('isCenter') ? 36 : 22,
              'height': (ele: NodeSingular) => ele.data('isCenter') ? 36 : 22,
              'label': 'data(label)',
              'font-size': 9,
              'color': '#fff',
              'text-valign': 'center' as const,
              'text-halign': 'center' as const,
              'text-outline-width': 0,
            },
          },
          {
            selector: 'edge',
            style: {
              'width': 1,
              'line-color': '#2d3748',
              'target-arrow-color': '#3d4f6a',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              'opacity': 0.6,
              'arrow-scale': 0.6,
            },
          },
          {
            selector: 'node:selected',
            style: {
              'border-width': 3,
              'border-color': '#60a5fa',
              'background-color': '#3b82f6',
            },
          },
        ],
        layout: {
          name: 'cose',
          animate: false,
          nodeRepulsion: () => 8000,
          gravity: 1,
          numIter: 1000,
        } as cytoscape.LayoutOptions,
      })

      cy.on('tap', 'node', (evt: cytoscape.EventObject) => {
        const nodeId = parseInt(evt.target.id(), 10)
        const profile = getMockProfile(nodeId)
        setSelectedNode({
          id: nodeId,
          profile,
          edges: cy.edges(`[source="${nodeId}"], [target="${nodeId}"]`).length,
        })
      })

      cy.on('tap', (evt: cytoscape.EventObject) => {
        if (evt.target === cy) setSelectedNode(null)
      })

      cyRef.current = cy
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to build graph.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    buildGraph(42)
    return () => { cyRef.current?.destroy() }
  }, [buildGraph])

  const handleLoad = () => {
    const uid = parseInt(centerId.trim(), 10)
    if (isNaN(uid) || uid < 0 || uid > 10199) {
      setError('Please enter a valid User ID between 0 and 10199.')
      return
    }
    buildGraph(uid)
  }

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1200, margin: '0 auto' }}>
      <PageHeader
        title="Network Explorer"
        subtitle="Interactive graph visualization of account connections. Click a node to see its trust profile."
        mockMode={mockMode}
      />

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Controls */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 12,
          padding: '14px 16px',
          marginBottom: 16,
          display: 'flex',
          gap: 12,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <input
          type="number"
          value={centerId}
          onChange={e => setCenterId(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleLoad()}
          placeholder="Center User ID"
          min={0}
          max={10199}
          style={{
            padding: '7px 12px',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-default)',
            borderRadius: 7,
            color: 'var(--text-primary)',
            fontSize: 14,
            outline: 'none',
            width: 160,
          }}
        />
        <button
          onClick={handleLoad}
          style={{
            padding: '8px 16px',
            background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
            border: 'none',
            borderRadius: 7,
            color: '#fff',
            fontWeight: 600,
            fontSize: 13,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <Search size={13} />
          Load Graph
        </button>
        <button
          onClick={() => cyRef.current?.fit()}
          style={{ padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 7, color: 'var(--text-secondary)', cursor: 'pointer' }}
          title="Fit to view"
        >
          <ZoomIn size={14} />
        </button>
        <button
          onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.8)}
          style={{ padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 7, color: 'var(--text-secondary)', cursor: 'pointer' }}
          title="Zoom out"
        >
          <ZoomOut size={14} />
        </button>
        <button
          onClick={() => buildGraph(parseInt(centerId) || 42)}
          style={{ padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 7, color: 'var(--text-secondary)', cursor: 'pointer' }}
          title="Reload"
        >
          <RefreshCw size={14} />
        </button>

        {/* Legend */}
        <div style={{ display: 'flex', gap: 12, marginLeft: 'auto', flexWrap: 'wrap' }}>
          {[
            { label: 'T1 Verified', color: '#10b981' },
            { label: 'T2 Standard', color: '#3b82f6' },
            { label: 'T3 Restricted', color: '#f59e0b' },
            { label: 'T4 Fraud', color: '#ef4444' },
          ].map(({ label, color }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
              {label}
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 16, alignItems: 'start' }}>
        {/* Graph */}
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 12,
            overflow: 'hidden',
            position: 'relative',
            height: 520,
          }}
        >
          {loading && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)', zIndex: 10 }}>
              <LoadingSpinner label="Building graph..." />
            </div>
          )}
          <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
        </div>

        {/* Selected node details */}
        {selectedNode && (
          <div
            style={{
              width: 260,
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 12,
              padding: 16,
              flexShrink: 0,
            }}
          >
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 14 }}>
              Node Details
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Account ID</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>#{selectedNode.id}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Trust Score</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent-blue-light)' }}>
                  {selectedNode.profile.trust_score.toFixed(1)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Bot Risk (p_bot)</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: selectedNode.profile.p_bot >= 0.75 ? '#ef4444' : selectedNode.profile.p_bot >= 0.45 ? '#f59e0b' : '#10b981' }}>
                  {(selectedNode.profile.p_bot * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Tier</div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    padding: '3px 8px',
                    borderRadius: 5,
                    display: 'inline-block',
                    marginTop: 3,
                    background: `${getTierColor(selectedNode.profile.recommendation_tier)}20`,
                    color: getTierColor(selectedNode.profile.recommendation_tier),
                  }}
                >
                  {getTierLabel(selectedNode.profile.recommendation_tier)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Label</div>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{selectedNode.profile.ground_truth_label}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Edges (visible)</div>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{selectedNode.edges}</div>
              </div>
              <div style={{ padding: '8px 10px', background: 'var(--bg-elevated)', borderRadius: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                {selectedNode.profile.decision}
              </div>
            </div>
          </div>
        )}
      </div>

      <div
        style={{
          marginTop: 12,
          fontSize: 11,
          color: 'var(--text-muted)',
          textAlign: 'center',
        }}
      >
        Showing 2-hop neighborhood of selected center node · Mock topology (real graph uses PyTorch serving index)
      </div>
    </div>
  )
}
