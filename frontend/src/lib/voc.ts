// API client for the AEGIS Deer Graph backend (voc360 → graph → root cause).
const BASE =
  (import.meta.env.VITE_API as string | undefined) ??
  (typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'http://127.0.0.1:8000')

// v2 console client (signals, kpis, signal-volume, solutions, decisions, narrate).
export * from './voc2'

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

export interface SimSeries {
  step: number
  mean_negativity: number
  complaint_volume: number
  n_critical: number
}
export interface Sim {
  before: { series: SimSeries[] }
  after: { series: SimSeries[] }
  delta: Record<string, number>
  root_cause: { canonical_label_ar?: string; member_count?: number } | null
  engine: string
  mesa_available: boolean
}
export const getSimulate = (c?: string) =>
  j<Sim>(`/api/simulate${c ? `?case=${encodeURIComponent(c)}` : ''}`, { method: 'POST' })

export const getGraph = (c?: string) => j<Graph>(`/api/graph${c ? `?case=${encodeURIComponent(c)}` : ''}`)
export const getRootCause = () => j<{ root_causes: RootCause[]; recommendation: string }>('/api/rootcause?limit=8')
export const getStats = () => j<Record<string, number>>('/api/stats')
export const getHealth = () => j<{ ok: boolean; database?: string; error?: string }>('/api/health')

// ============================================================= PROOF DRILL-DOWN
// Click a graph node → GET /api/proof gives the full PROOF of a problem:
// the 5-whys causal trace, structured validation, evidence quotes, the real
// the_data rows behind it, and a best-effort forecast. See AGREED API CONTRACT.
export interface ProofSubject {
  type: 'cluster' | 'service' | 'all'
  key: string
  cluster_id: string
  label_ar: string
  label_en: string | null
  members: number
  severity_avg: number
  signals: number
  services: [string, number][]
  first_seen: string | null
  last_seen: string | null
}
export interface WhyStep {
  depth: number
  question: string
  because: string
  because_en: string | null
  evidence: string[]
  signals: number
}
export interface ValidationCheck {
  name: string
  pass: boolean
  score: number
  detail: string
  evidence: string[]
}
export interface Validation {
  verdict: string
  confidence: number
  score: number
  summary: string
  checks: ValidationCheck[]
}
export interface EvidenceSegment {
  segment_text: string
  confidence: number
}
export interface RelatedCase {
  record_id: string
  service_id: string
  text: string
  sentiment_label: string
  severity: number
  observed_at: string
  source_type: string
}
export interface ForecastPoint {
  t: string
  mean: number
  lo: number
  hi: number
}
export interface Escalation {
  recent_mean: number
  forecast_mean: number
  ratio: number
  escalating: boolean
}
export interface Forecast {
  history: { t: string; v: number }[]
  forecast: ForecastPoint[]
  escalation: Escalation | null
  source: string
}
export interface ProofBundle {
  ok: boolean
  subject: ProofSubject
  why_chain: WhyStep[]
  root: string
  narration: string
  validation: Validation
  evidence_segments: EvidenceSegment[]
  related_cases: RelatedCase[]
  forecast: Forecast | null
  report_url: string
}

const qp = (o: Record<string, string | number | undefined>) =>
  Object.entries(o)
    .filter(([, v]) => v !== undefined && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')

export const getProof = (p: { type: 'cluster' | 'service' | 'all'; key: string; depth?: number }) =>
  j<ProofBundle>(`/api/proof?${qp({ type: p.type, key: p.key, depth: p.depth ?? 5 })}`)

export const reportUrl = (clusterId: string) => `${BASE}/api/report/${encodeURIComponent(clusterId)}.xlsx`

export const getWhys = (p: { type: 'cluster' | 'service' | 'all'; key: string; max_depth?: number }) =>
  j<{ why_chain: WhyStep[]; root: string; narration: string }>(
    `/api/whys?${qp({ type: p.type, key: p.key, max_depth: p.max_depth ?? 5 })}`,
  )

export const getForecast = (p: { entity: string; key: string; metric?: string; horizon?: number }) =>
  j<Forecast>(`/api/forecast?${qp({ entity: p.entity, key: p.key, metric: p.metric, horizon: p.horizon })}`)

export const getValidate = (p: { cluster_id: string }) =>
  j<Validation>(`/api/validate?${qp({ cluster_id: p.cluster_id })}`)

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
