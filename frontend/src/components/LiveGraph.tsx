import { useEffect, useMemo, useState } from 'react'
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
import { Zap, Loader2, Database, CheckCircle2, Circle } from 'lucide-react'
import { getGraph, getRootCause, getHealth, runFlow, type Graph, type RootCause, type FlowEvent } from '../lib/voc'

const SEV: Record<string, string> = { alert: '#F04359', warn: '#FBBF24', calm: '#34D399', neutral: '#8B8D96' }
const TAG: Record<string, string> = {
  case: 'CASE', source: 'SOURCE', service: 'SERVICE', governorate: 'GOVERNORATE', rchub: 'ROOT CAUSES', cluster: 'PROBLEM',
}
const isAr = (s: string) => /[؀-ۿ]/.test(s)
function nodeColor(t: string, sev: string) {
  if (t === 'case') return '#3B82F6'
  if (t === 'rchub') return '#F04359'
  if (t === 'source' || t === 'governorate') return '#8B8D96'
  return SEV[sev] || '#8B8D96'
}

function GNode({ data }: NodeProps) {
  const c = data.color as string
  return (
    <div className="rounded-lg border bg-card" style={{ borderColor: c, minWidth: data.w, boxShadow: `0 0 16px -7px ${c}` }}>
      <Handle type="target" position={Position.Left} className="!h-1 !w-1 !border-0 !bg-border" />
      <div className="px-2.5 py-1.5" dir={isAr(data.label) ? 'rtl' : 'ltr'}>
        <div className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: c }} />
          <span className="font-mono text-[8px] tracking-[0.12em] text-faint">{data.tag}</span>
          {data.value ? <span className="ml-auto font-mono text-[9px] text-muted">{data.value}</span> : null}
        </div>
        <div className="mt-0.5 text-[11px] leading-tight text-txt" style={{ maxWidth: 200 }}>{data.label}</div>
      </div>
      <Handle type="source" position={Position.Right} className="!h-1 !w-1 !border-0 !bg-border" />
    </div>
  )
}
const nodeTypes = { g: GNode }
const STAGES = ['connect', 'ingest', 'graph', 'rootcause', 'recommend']

export default function LiveGraph() {
  const [graph, setGraph] = useState<Graph | null>(null)
  const [causes, setCauses] = useState<RootCause[]>([])
  const [health, setHealth] = useState<{ ok: boolean; database?: string } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [flow, setFlow] = useState<Record<string, FlowEvent>>({})
  const [running, setRunning] = useState(false)
  const [rec, setRec] = useState<string | null>(null)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ ok: false }))
    Promise.all([getGraph(), getRootCause()])
      .then(([g, rc]) => { setGraph(g); setCauses(rc.root_causes); setRec(rc.recommendation) })
      .catch((e) => setErr(String(e)))
  }, [])

  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [] as Node[], edges: [] as Edge[] }
    const nodes: Node[] = graph.nodes.map((n) => ({
      id: n.id, type: 'g', position: { x: n.x, y: n.y }, draggable: true,
      data: { label: n.label, tag: TAG[n.type], value: n.value, color: nodeColor(n.type, n.severity), w: Math.min(230, 96 + Math.sqrt(n.value || 1) * 5) },
    }))
    const edges: Edge[] = graph.edges.map((e, i) => {
      const root = e.kind === 'root_cause' || e.kind === 'cluster' || e.kind === 'diagnoses'
      return {
        id: `e${i}`, source: e.source, target: e.target, animated: root,
        style: { stroke: root ? '#F04359' : '#2a2c33', strokeWidth: Math.min(4, 0.6 + Math.log10((e.weight || 1) + 1) * 1.3), opacity: root ? 0.8 : 0.5 },
      }
    })
    return { nodes, edges }
  }, [graph])

  async function run() {
    if (running) return
    setRunning(true); setFlow({})
    try {
      for await (const ev of runFlow()) {
        setFlow((f) => ({ ...f, [ev.stage]: ev }))
        if (ev.stage === 'recommend' && ev.status === 'done') setRec(ev.detail)
      }
    } catch (e) {
      setErr(String(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* header */}
      <div className="flex items-center justify-between border-b border-border px-8 py-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-txt">Live Crisis Graph</h1>
          <p className="mt-1 flex items-center gap-2 text-[13px] text-muted">
            <Database className="h-3.5 w-3.5" />
            <span className={health?.ok ? 'text-good' : 'text-danger'}>
              {health?.ok ? `voc360 connected` : 'db offline'}
            </span>
            {graph && <span className="text-faint">· {graph.stats.signals.toLocaleString()} signals · {graph.stats.services} services · {graph.stats.clusters} root causes</span>}
          </p>
        </div>
        <button
          onClick={run}
          className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-60"
          disabled={running}
        >
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4 fill-white" />}
          {running ? 'Running flow…' : 'Run Deer Graph Flow'}
        </button>
      </div>

      <div className="flex min-h-0 flex-1">
        {/* graph canvas */}
        <div className="relative min-h-0 flex-1">
          {err && <div className="absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 rounded-lg border border-danger/40 bg-card px-4 py-3 text-[13px] text-danger">{err}</div>}
          {graph && (
            <ReactFlow
              nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.18 }}
              proOptions={{ hideAttribution: true }} minZoom={0.15} nodesConnectable={false} elementsSelectable={false}
            >
              <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#1A1B20" />
              <MiniMap nodeColor={(n) => (n.data as { color: string }).color} maskColor="#0A0A0Bcc" style={{ background: '#0B0B0D' }} pannable />
              <Controls showInteractive={false} />
            </ReactFlow>
          )}
        </div>

        {/* right panel */}
        <aside className="flex w-[360px] shrink-0 flex-col overflow-y-auto border-l border-border bg-sidebar">
          {/* flow stages */}
          <div className="border-b border-border p-4">
            <div className="mb-3 font-mono text-[10px] tracking-[0.14em] text-faint">DEER GRAPH FLOW</div>
            <ol className="space-y-2">
              {STAGES.map((s) => {
                const ev = flow[s]
                const done = ev?.status === 'done'
                const active = ev?.status === 'running'
                return (
                  <li key={s} className="flex items-start gap-2.5">
                    {done ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-good" />
                      : active ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-blue" />
                        : <Circle className="mt-0.5 h-4 w-4 shrink-0 text-faint" />}
                    <div className="min-w-0">
                      <div className={`text-[13px] capitalize ${done || active ? 'text-txt' : 'text-muted'}`}>{s}</div>
                      {ev && <div className="text-[11px] leading-tight text-muted" dir={isAr(ev.detail) ? 'rtl' : 'ltr'}>{ev.detail}</div>}
                    </div>
                  </li>
                )
              })}
            </ol>
            {rec && <div className="mt-3 rounded-lg border border-blue/30 bg-blue/10 p-2.5 text-[12px] leading-snug text-txt" dir={isAr(rec) ? 'rtl' : 'ltr'}>{rec}</div>}
          </div>

          {/* root causes */}
          <div className="p-4">
            <div className="mb-3 font-mono text-[10px] tracking-[0.14em] text-faint">RANKED ROOT CAUSES · RIL</div>
            <div className="space-y-2">
              {causes.map((c) => {
                const col = c.severity_avg >= 0.5 ? SEV.alert : c.severity_avg >= 0.3 ? SEV.warn : SEV.calm
                return (
                  <div key={c.cluster_id} className="rounded-lg border border-border bg-card p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[11px] text-muted">#{c.rank}</span>
                      <span className="font-mono text-[11px]" style={{ color: col }}>{c.members} reports · sev {c.severity_avg}</span>
                    </div>
                    <div className="mt-1 text-[12.5px] leading-snug text-txt" dir="rtl">{c.label_ar}</div>
                    <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-soft">
                      <div className="h-full rounded-full" style={{ width: `${Math.min(100, (c.members / 551) * 100)}%`, background: col }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
