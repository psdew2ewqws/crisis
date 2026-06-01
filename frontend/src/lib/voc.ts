// API client for the AEGIS Deer Graph backend (voc360 → graph → root cause).
const BASE = import.meta.env.VITE_API ?? 'http://127.0.0.1:8000'

export interface GraphNode {
  id: string
  type: 'case' | 'source' | 'service' | 'governorate' | 'rchub' | 'cluster'
  label: string
  value: number
  severity: 'alert' | 'warn' | 'calm' | 'neutral'
  x: number
  y: number
  label_ar?: string
  members?: number
  severity_avg?: number
}
export interface GraphEdge {
  source: string
  target: string
  weight: number
  kind: string
}
export interface Graph {
  case: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: { signals: number; services: number; sources: number; clusters: number }
}
export interface RootCause {
  rank: number
  cluster_id: string
  label_ar: string
  label_en: string | null
  members: number
  severity_avg: number
  score: number
  evidence: string[]
}
export interface FlowEvent {
  stage: string
  status: 'running' | 'done'
  detail: string
  data?: unknown
}

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, init)
  if (!r.ok) throw new Error(`${path} → ${r.status}`)
  return r.json() as Promise<T>
}

export const getGraph = (c?: string) => j<Graph>(`/api/graph${c ? `?case=${encodeURIComponent(c)}` : ''}`)
export const getRootCause = () => j<{ root_causes: RootCause[]; recommendation: string }>('/api/rootcause?limit=8')
export const getStats = () => j<Record<string, number>>('/api/stats')
export const getHealth = () => j<{ ok: boolean; database?: string; error?: string }>('/api/health')

// stream the Deer Graph flow (NDJSON)
export async function* runFlow(c?: string): AsyncGenerator<FlowEvent> {
  const r = await fetch(`${BASE}/api/flow/run${c ? `?case=${encodeURIComponent(c)}` : ''}`, { method: 'POST' })
  const reader = r.body!.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''
    for (const ln of lines) if (ln.trim()) yield JSON.parse(ln) as FlowEvent
  }
}
