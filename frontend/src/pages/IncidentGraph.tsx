import { useState, useCallback, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Play } from 'lucide-react'
import CrisisNode from '../components/graph/CrisisNode'
import CrisisEdge from '../components/graph/CrisisEdge'
import { graphNodes, graphEdges, type GraphNode } from '../lib/data'
import { useWizardStore } from '../stores/wizardStore'
import { useAppStore } from '../stores/appStore'

const POSITIONS: Record<string, { x: number; y: number }> = {
  'PIPE-ZN-44': { x: 50, y: 200 },
  'ZONE-NORTH': { x: 350, y: 100 },
  'VALVE-441': { x: 350, y: 320 },
  'HOSP-ZN-NEW': { x: 650, y: 50 },
  'JCT-HW35': { x: 650, y: 250 },
  'PSAP-ZN': { x: 950, y: 150 },
  'SOCIAL-ZN': { x: 1200, y: 150 },
}

const nodeTypes = { crisis: CrisisNode }
const edgeTypes = { crisis: CrisisEdge }

const initialNodes: Node[] = graphNodes.map((n) => ({
  id: n.id,
  type: 'crisis',
  position: POSITIONS[n.id] ?? { x: 0, y: 0 },
  data: { ...n },
}))

const initialEdges: Edge[] = graphEdges.map((e) => ({
  id: e.id,
  source: e.source,
  target: e.target,
  type: 'crisis',
  data: { ...e },
}))

export default function IncidentGraph() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [inspected, setInspected] = useState<GraphNode | null>(null)
  const [replaying, setReplaying] = useState(false)
  const replayRef = useRef(false)
  const wizardOpen = useWizardStore((s) => s.open)
  const setGuard = useWizardStore((s) => s.setGuard)
  const highlightedNodeId = useAppStore((s) => s.highlightedNodeId)
  const setHighlightedNodeId = useAppStore((s) => s.setHighlightedNodeId)

  // Wizard guard: graph data always exists
  useEffect(() => {
    if (wizardOpen) setGuard(2, true)
  }, [wizardOpen])

  // Cross-page: auto-select highlighted node
  useEffect(() => {
    if (highlightedNodeId) {
      const gn = graphNodes.find((n) => n.id === highlightedNodeId)
      if (gn) setInspected(gn)
      setHighlightedNodeId(null)
    }
  }, [highlightedNodeId])

  const handleSignalClick = (signalId: string) => {
    useAppStore.getState().setHighlightedSignalId(signalId)
    navigate('/signals')
  }

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const gn = graphNodes.find((n) => n.id === node.id)
      setInspected(gn ?? null)
    },
    [],
  )

  const replay = useCallback(() => {
    if (replayRef.current) return
    replayRef.current = true
    setReplaying(true)

    // dim all nodes and hide edges
    setNodes((nds) => nds.map((n) => ({ ...n, style: { opacity: 0.15 } })))
    setEdges([])

    const maxOrder = Math.max(...graphEdges.map((e) => e.propagationOrder))
    const sortedEdges = [...graphEdges].sort((a, b) => a.propagationOrder - b.propagationOrder)

    let step = 0
    const interval = setInterval(() => {
      if (step > maxOrder) {
        clearInterval(interval)
        replayRef.current = false
        setReplaying(false)
        return
      }

      const currentOrder = step
      // reveal edges for this propagation order
      const newEdges = sortedEdges
        .filter((e) => e.propagationOrder <= currentOrder)
        .map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          type: 'crisis' as const,
          data: { ...e },
        }))
      setEdges(newEdges)

      // reveal nodes connected in this order or earlier
      const revealedNodeIds = new Set<string>()
      sortedEdges
        .filter((e) => e.propagationOrder <= currentOrder)
        .forEach((e) => {
          revealedNodeIds.add(e.source)
          revealedNodeIds.add(e.target)
        })
      // always show apex
      revealedNodeIds.add('PIPE-ZN-44')

      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          style: { opacity: revealedNodeIds.has(n.id) ? 1 : 0.15, transition: 'opacity 0.4s ease' },
        })),
      )

      step++
    }, 600)
  }, [setNodes, setEdges])

  const minimapColors = useCallback((node: Node) => {
    const d = node.data as unknown as GraphNode
    if (d.tone === 'danger') return '#F04359'
    if (d.tone === 'warn') return '#FBBF24'
    return '#34D399'
  }, [])

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 64px)' }}>
      {/* header */}
      <div className="flex items-center justify-between px-8 py-4">
        <div>
          <h1 className="text-[28px] font-semibold tracking-tight text-txt">Incident Graph</h1>
          <p className="mt-1 text-[14px] text-muted">
            Stitched dependency graph — cascade visualization for case {id}
          </p>
        </div>
        <button
          onClick={replay}
          disabled={replaying}
          className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-[13px] font-medium text-txt transition-colors hover:bg-cardhi disabled:opacity-40"
        >
          <Play className="h-3.5 w-3.5" />
          {replaying ? 'Replaying…' : 'Replay Cascade'}
        </button>
      </div>

      {/* graph canvas */}
      <div className="relative flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
          className="bg-bg"
        >
          <Background gap={20} size={1} color="var(--color-border)" />
          <Controls className="!bg-card !border-border !rounded-lg [&>button]:!bg-card [&>button]:!border-border [&>button]:!text-muted" />
          <MiniMap
            nodeColor={minimapColors}
            maskColor="var(--color-bg)"
            className="!bg-card !border-border !rounded-lg"
          />
        </ReactFlow>

        {/* node inspector */}
        {inspected && (
          <div className="absolute bottom-0 left-0 right-0 border-t border-border bg-card/95 backdrop-blur-sm"
            style={{ height: '30%' }}
          >
            <div className="flex h-full gap-8 px-8 py-4 overflow-auto">
              <div className="min-w-[200px]">
                <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">ENTITY</div>
                <div className="mt-1 text-[16px] font-semibold text-txt">{inspected.label}</div>
                <div className="mt-0.5 font-mono text-[12px] text-muted">{inspected.id}</div>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-[12px] text-muted">{inspected.type}</span>
                  <span className="h-4 w-px bg-border" />
                  <span className="font-mono text-[12px] text-muted">Z {inspected.zScore}</span>
                </div>
              </div>
              <div className="h-full w-px bg-border shrink-0" />
              <div>
                <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">METRICS</div>
                <div className="mt-2 grid grid-cols-3 gap-x-8 gap-y-2">
                  {Object.entries(inspected.metrics).map(([k, v]) => (
                    <div key={k}>
                      <div className="text-[11px] text-faint">{k}</div>
                      <div className="font-mono text-[13px] text-txt">{v}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="h-full w-px bg-border shrink-0" />
              <div>
                <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">LINKED SIGNALS</div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {inspected.signalIds.map((sid) => (
                    <button
                      key={sid}
                      onClick={() => handleSignalClick(sid)}
                      className="rounded-md border border-border bg-soft px-2 py-0.5 font-mono text-[11px] text-muted hover:text-blue hover:border-blue/30 transition-colors cursor-pointer"
                    >
                      {sid}
                    </button>
                  ))}
                </div>
              </div>
              <button
                onClick={() => setInspected(null)}
                className="ml-auto shrink-0 self-start rounded-lg border border-border px-3 py-1 text-[12px] text-muted hover:text-txt hover:bg-cardhi"
              >
                ✕
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
