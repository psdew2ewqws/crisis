import { useMemo } from 'react'
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { Incident } from '../types'
import { SEV_HEX } from '../types'

const POS: Record<string, { x: number; y: number }> = {
  'PIPE-ZN-44': { x: 10, y: 150 },
  'ZONE-ZN-3': { x: 280, y: 150 },
  'HOSP-ZN-NEW': { x: 560, y: 50 },
  'JCT-31': { x: 560, y: 255 },
  'PSAP-ZN': { x: 840, y: 50 },
}

function CrisisNode({ data }: NodeProps) {
  const c = SEV_HEX[data.severity as keyof typeof SEV_HEX]
  return (
    <div
      className={`relative w-[176px] overflow-hidden rounded-md border bg-raised ${data.isRoot ? 'animate-pulsering' : ''}`}
      style={{ borderColor: data.isRoot ? c : '#232C3A' }}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-hair !bg-hair" />
      <div className="absolute left-0 top-0 h-full w-1" style={{ background: c }} />
      <div className="py-2 pl-4 pr-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[8px] tracking-[0.16em] text-muted">{String(data.kind).toUpperCase()}</span>
          {data.isRoot && (
            <span className="rounded-sm bg-alert/15 px-1.5 py-0.5 font-mono text-[8px] tracking-[0.16em] text-alert">
              ROOT
            </span>
          )}
        </div>
        <div className="mt-0.5 text-[13px] font-medium leading-tight text-txt">{data.label}</div>
        <div className="font-mono text-[10px] text-muted">{data.id}</div>
      </div>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-hair !bg-hair" />
    </div>
  )
}
const nodeTypes = { crisis: CrisisNode }

export default function IncidentGraph({ incident }: { incident: Incident }) {
  const nodes: Node[] = useMemo(
    () =>
      incident.nodes.map((n) => ({
        id: n.id,
        type: 'crisis',
        position: POS[n.id] ?? { x: 0, y: 0 },
        data: { ...n },
      })),
    [incident],
  )
  const edges: Edge[] = useMemo(
    () =>
      incident.edges.map((e) => {
        const tgt = incident.nodes.find((n) => n.id === e.target)!
        const c = SEV_HEX[tgt.severity]
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          animated: true,
          label: `${e.relation} · ${e.lag_min}m`,
          labelStyle: { fill: '#8A97A6', fontFamily: 'JetBrains Mono', fontSize: 9 },
          labelBgStyle: { fill: '#0A0E12', fillOpacity: 0.85 },
          labelBgPadding: [4, 2] as [number, number],
          style: { stroke: c, strokeWidth: 1.4 + e.weight * 1.6, opacity: 0.85 },
        }
      }),
    [incident],
  )

  return (
    <div className="relative h-full w-full overflow-hidden rounded-md border border-hair bg-panel shadow-panel">
      <div className="pointer-events-none absolute left-3 top-3 z-10">
        <div className="font-mono text-[10px] tracking-[0.18em] text-muted">INCIDENT GRAPH</div>
        <div className="font-display text-sm text-txt">{incident.title}</div>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.22 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnDrag
        minZoom={0.4}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#1A2230" />
        <MiniMap
          nodeColor={(n) => SEV_HEX[(n.data as { severity: keyof typeof SEV_HEX }).severity]}
          maskColor="#0A0E12cc"
          style={{ background: '#0A0E12' }}
          pannable
        />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
