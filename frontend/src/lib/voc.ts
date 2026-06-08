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

// ---- SMS alerts (josms.net gateway, server-side) ----
export interface AlertSendResult {
  ok: boolean
  configured?: boolean
  sent_to?: string[]
  sent_count?: number
  invalid?: string[]
  error?: string
  message_ar?: string
  results?: { numbers: string[]; http: number; response: string; ok: boolean }[]
}
export interface AlertGroup { id: string; name: string; numbers: string[]; count: number; ts?: string }
export const getSmsBalance = () =>
  j<{ ok: boolean; configured: boolean; balance: number | null; raw?: string }>('/api/alert/balance')
export const sendSmsAlert = (numbers: string[], message: string, groupId?: string) =>
  j<AlertSendResult>('/api/alert/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(groupId ? { group_id: groupId, message } : { numbers, message }),
  })
export const getAlertGroups = () => j<{ groups: AlertGroup[] }>('/api/alert/groups')
export const saveAlertGroup = (name: string, numbers: string[]) =>
  j<{ ok: boolean; group?: AlertGroup; invalid?: string[]; message_ar?: string }>('/api/alert/groups', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, numbers }),
  })
export const deleteAlertGroup = (id: string) =>
  j<{ ok: boolean }>(`/api/alert/groups/${encodeURIComponent(id)}`, { method: 'DELETE' })

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
  plain?: string
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

// ── Multi-agent DEBATE (NDJSON stream of agents arguing) ──────────────────────
export interface DebateEvent {
  type: 'dossier' | 'turn' | 'synthesis' | 'done' | 'error' | 'plan' | 'cluster' | 'phase'
  role?: string
  agent?: string
  text?: string
  engine?: string
  model?: string | null
  subject?: { label_ar?: string; members?: number; severity_avg?: number }
  memory?: { topic: string; summary: string; count: number }[]
  validation?: { verdict?: string; confidence?: number }
  confidence?: number
  verdict?: string
  citations?: { type: string; id?: string; label?: string; text?: string; weight?: number }[]
  report_url?: string
  error?: string
  // deep-research (mode:'deep') fields
  group?: string
  label?: string
  phase?: string
  agents?: number
  clusters?: number
  agenda?: string[]
  index?: number
  members?: number
  topics?: number
}

// Streams POST /api/debate, invoking onEvent per NDJSON line. Resolves when done.
// mode 'deep' runs the full multi-cluster swarm (delegates + expert panel + synthesis).
export async function streamDebate(
  body: { type: 'cluster' | 'service' | 'all'; key?: string; mode?: 'single' | 'deep'; top_k?: number },
  onEvent: (e: DebateEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/debate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.body) return
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i: number
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).trim()
      buf = buf.slice(i + 1)
      if (line) {
        try {
          onEvent(JSON.parse(line) as DebateEvent)
        } catch {
          /* ignore partial / malformed line */
        }
      }
    }
  }
}

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

// =========================================================================== //
// Scenario engine — crisis detection + prediction for a NOVEL situation.       //
// POST /api/scenario/detect streams NDJSON stages; each line is a ScenarioEvent.//
// =========================================================================== //
export interface ScenarioCitation {
  source_case_id?: string
  ts?: string
  kind?: 'success' | 'failure'
  outcome?: string
  outcome_ar?: string
  risk_source?: string
  risk_source_ar?: string
  lesson?: string
  relevance?: number
}
export interface ScenarioAgent {
  key: string
  name: string
  score: number
  reason: string
  floor: boolean
}
export interface ScenarioSeriesPoint {
  step: number
  mean_negativity: number
  n_critical: number
}
export interface ScenarioSeir {
  peak_negativity: number
  peak_n_critical: number
  peak_critical_frac: number | null
  time_to_peak: number
  ticks_to_settle: number
  escalating: boolean
  severity: 'low' | 'elevated' | 'critical'
}
export interface ScenarioEscalation {
  source: 'forecast' | 'simulation'
  escalating: boolean
  ratio?: number
  horizon_days?: number
  forecast_source?: string
  peak_critical_frac?: number | null
  ticks_to_settle?: number
  note?: string
}
export interface ScenarioDetection {
  is_crisis: boolean
  severity: 'low' | 'elevated' | 'critical'
  severity_ar: string
  escalating: boolean
  escalation_source?: string
  has_precedent: boolean
}
export interface ScenarioWhichWorked {
  intervention: string
  risk_reduction: number
  source_case_id?: string
  ts?: string
  risk_source?: string
  risk_source_ar?: string
}
export interface ScenarioPrediction {
  likely_outcome: string | null
  likely_outcome_ar: string | null
  which_intervention_worked: ScenarioWhichWorked | null
  risk_trajectory: {
    risk_before?: number | null
    risk_after?: number | null
    risk_reduction?: number | null
    risk_source?: string | null
    risk_source_ar?: string | null
  }
  avoid: { warning: string; avoid_when: string; source_case_id?: string }[]
}
export interface ScenarioConfidence {
  band: 'high' | 'medium' | 'low'
  band_ar: string
  score: number
  breakdown: {
    mean_relevance: number
    outcome_agreement: number
    validation_factor: number
    distinct_precedents: number
  }
}
export interface ScenarioPastRun {
  id: string
  ts?: string
  text: string
  domain?: string
  service?: string | null
  location?: string | null
  severity_ar?: string
  escalating?: boolean
  likely_outcome_ar?: string
  confidence_band_ar?: string
  risk_before?: number
  risk_after?: number
}
export interface ScenarioSolutionEval {
  alignment: 'aligned_with_success' | 'matches_anti_pattern' | 'novel'
  alignment_ar: string
  alignment_score: number
  matched_success: ScenarioCitation | null
  matched_anti_pattern: { warning: string; source_case_id?: string } | null
  optimized_solution: string
  expected_results: {
    risk_before?: number | null
    risk_after?: number | null
    risk_reduction?: number | null
    escalating?: boolean
    engine?: string
  }
  confidence_band: 'high' | 'medium' | 'low'
  confidence_band_ar: string
}
export interface ScenarioEvidence {
  source?: string
  title?: string
  year?: number
  doi?: string | null
  url?: string
  oa_status?: string
  license?: string | null
  cited_by?: number
  snippet?: string
  verified?: boolean
  verify_how?: string
}
export interface ScenarioMonteCarlo {
  available?: boolean
  n?: number
  p10?: number
  p50?: number
  p90?: number
  spread?: number
}
export interface ScenarioReference { name: string; url: string }
export interface ScenarioEvent {
  stage: 'parse' | 'retrieve' | 'history' | 'news_context' | 'select_agents' | 'simulate' | 'debate' | 'detect_predict' | 'solution_eval' | 'evidence' | 'done'
  // parse
  script?: 'ar' | 'latin'
  domain?: string
  using_llm?: boolean
  warnings?: string[]
  // retrieve
  count?: number
  cases?: ScenarioCitation[]
  best_relevance?: number
  // select_agents
  agents?: ScenarioAgent[]
  engine?: string
  // simulate
  available?: boolean
  risk_before?: number
  risk_after?: number
  risk_reduction?: number
  intervention_strength?: number
  n_nodes?: number
  seir_before?: ScenarioSeir
  seir_after?: ScenarioSeir
  series_before?: ScenarioSeriesPoint[]
  series_after?: ScenarioSeriesPoint[]
  escalation?: ScenarioEscalation
  // cascade (Jordan drought) extras
  rainfall_ratio?: number
  sectors_after?: Record<string, number>
  montecarlo?: ScenarioMonteCarlo
  non_mitigating?: string[]
  references?: ScenarioReference[]
  baseline?: Record<string, { value: unknown; kind?: string; source_url?: string; note?: string }>
  label?: string
  // news_context stage (live RSS articles from aegis_news for the location)
  gov?: string
  articles?: { title: string; source: string; published: string | null; summary?: string }[]
  // evidence stage (verified references from the legal research agent)
  items?: ScenarioEvidence[]
  abstained?: boolean
  // debate
  role?: string
  agent?: string
  text?: string
  // detect_predict
  detection?: ScenarioDetection
  prediction?: ScenarioPrediction
  confidence?: ScenarioConfidence
  degradation_flags?: string[]
  degradation_flags_ar?: string[]
  citations?: ScenarioCitation[]
  // history (recalled past runs)
  runs?: ScenarioPastRun[]
  total?: number
  // solution_eval
  alignment?: 'aligned_with_success' | 'matches_anti_pattern' | 'novel'
  alignment_ar?: string
  alignment_score?: number
  matched_success?: ScenarioCitation | null
  matched_anti_pattern?: { warning: string; source_case_id?: string } | null
  optimized_solution?: string
  expected_results?: ScenarioSolutionEval['expected_results']
  confidence_band?: 'high' | 'medium' | 'low'
  confidence_band_ar?: string
  // done
  aborted?: boolean
  reason?: string
}
export interface ScenarioInput {
  text: string
  domain?: string
  horizon_days?: number
  run_debate?: boolean
  top_k?: number
  case_hint?: string
  location?: string
  service?: string
  solution?: string
}
export interface ScenarioOption { value: string; count: number }
export interface ScenarioOptions { locations: ScenarioOption[]; services: ScenarioOption[] }
export const getScenarioOptions = () => j<ScenarioOptions>('/api/scenario/options')

// Deterministic written report (rich Arabic prose + structured references)
export interface ReportKeyFigure { label: string; value: string; source: string }
export interface ReportSection { title_ar: string; title_en: string; paragraphs: string[] }
export interface ScenarioReportDoc {
  ok: boolean
  meta?: { title_ar: string; scenario: string; report_no: string; generated_at: string; flagship: boolean }
  key_figures?: ReportKeyFigure[]
  sections?: ReportSection[]
  references?: {
    peer_reviewed: { title?: string; year?: number; oa?: string; doi?: string }[]
    institutional: { name?: string; url?: string }[]
    count: number
  }
}
export async function getScenarioReport(body: {
  text: string
  sim: ScenarioEvent | null
  detection?: ScenarioDetection
  prediction?: ScenarioPrediction
  confidence?: ScenarioConfidence
  references?: ScenarioReference[]
  evidence?: ScenarioEvidence[]
}): Promise<ScenarioReportDoc> {
  const res = await fetch(`${BASE}/api/scenario/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}

// Live multi-agent deliberation that REASONS + negotiates the report (needs a reachable
// model; streams agent turns then the final reasoned report). Falls back to the instant report.
export interface DeliberationEvent {
  stage: 'preflight' | 'agent' | 'tally' | 'fallback' | 'synthesis' | 'section' | 'report' | 'done'
  model_ok?: boolean
  model?: string
  persona?: string
  role?: string
  round?: number
  phase?: 'analysis' | 'negotiation' | 'vote'
  text?: string
  message_ar?: string
  // tally (vote-to-converge)
  ready?: number
  total?: number
  converged?: boolean
  // synthesis progress (the coordinator writes the report section by section)
  sections_total?: number
  index?: number
  title_ar?: string
  ok?: boolean
  // report
  sections?: ReportSection[]
  key_figures?: ReportKeyFigure[]
  references?: ScenarioReportDoc['references']
  deliberated?: boolean
  converged_note?: string
  turns?: number
}
export async function streamDeliberate(
  body: { text: string; sim: ScenarioEvent | null; detection?: ScenarioDetection; prediction?: ScenarioPrediction; confidence?: ScenarioConfidence; evidence?: ScenarioEvidence[]; rounds?: number },
  onEvent: (e: DeliberationEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/scenario/report/deliberate`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal,
  })
  if (!res.body) return
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i: number
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).trim()
      buf = buf.slice(i + 1)
      if (line) {
        try { onEvent(JSON.parse(line) as DeliberationEvent) } catch { /* partial */ }
      }
    }
  }
}

// Streams POST /api/scenario/detect, invoking onEvent per NDJSON line.
export async function streamScenario(
  body: ScenarioInput,
  onEvent: (e: ScenarioEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/scenario/detect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.body) return
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i: number
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).trim()
      buf = buf.slice(i + 1)
      if (line) {
        try {
          onEvent(JSON.parse(line) as ScenarioEvent)
        } catch {
          /* ignore partial / malformed line */
        }
      }
    }
  }
}

// ── Agent-based simulation (the "Agent-Based" tab) ──────────────────────────
export interface AbmAgentPopulations {
  citizens: number; services: number; operators: number; media: number; citizen_pop_total: number
}
export interface AbmResearchSource {
  title: string; year?: number; doi?: string | null; url?: string; contribution: string
}
export interface AbmResearchInsights {
  available: boolean
  n_papers: number
  n_contributing: number
  shock_hint: number | null
  effect_hints: number[]
  interventions: string[]
  sources: AbmResearchSource[]
  confidence: 'high' | 'medium' | 'low'
  notes_ar: string
}
export interface AbmCalibration {
  available: boolean
  source: 'data' | 'dowhy' | 'prior' | 'data+research'
  effect_size: number
  spread_rate: number
  decay: number
  n_rows: number
  n_services: number
  confidence: 'high' | 'medium' | 'low'
  refutation: { available: boolean; robust?: boolean; spurious?: boolean; effect?: number }
  notes_ar: string
  research?: AbmResearchInsights
}
export interface AbmTimelineEvent {
  tick: number; event: string; targets?: string[]; effect_size?: number; obs?: number
}
export interface AbmArchPoint {
  step: number; citizen: number; service_quality: number; media_awareness: number
}
export interface AbmReportDoc {
  ok: boolean
  type?: 'crisis' | 'solution'
  error?: string
  meta?: { title_ar: string; title_en: string; scenario: string }
  key_figures?: ReportKeyFigure[]
  sections?: ReportSection[]
}
export interface AbmEvent {
  stage: 'intake' | 'seed_society' | 'research_intake' | 'calibrate' | 'simulate_problem'
    | 'simulate_solution' | 'compare' | 'reports' | 'synthesize' | 'error' | 'done'
  status?: string
  detail?: string
  // intake
  case?: string | null; domain?: string | null; steps?: number; seed?: number
  // seed_society
  agent_populations?: AbmAgentPopulations
  n_nodes?: number
  engine_notes?: { mesa: boolean; langgraph: boolean; dowhy: boolean }
  // calibrate
  calibration?: AbmCalibration
  // simulate_problem (problem-only slice)
  series?: ScenarioSeriesPoint[]; seir?: ScenarioSeir; risk?: number; per_archetype?: AbmArchPoint[]
  // simulate_solution — full sim payload (same shape ScenarioCharts reads)
  available?: boolean; engine?: string
  risk_before?: number; risk_after?: number; risk_reduction?: number
  intervention_strength?: number; intervention_node?: string | null
  seir_before?: ScenarioSeir; seir_after?: ScenarioSeir; escalation?: ScenarioEscalation
  series_before?: ScenarioSeriesPoint[]; series_after?: ScenarioSeriesPoint[]
  per_archetype_series?: { problem: AbmArchPoint[]; solution: AbmArchPoint[] }
  intervention_timeline?: AbmTimelineEvent[]
  lags?: { detection_lag: number; decision_lag: number; ramp_ticks: number }
  // research_intake — papers fetched before simulation
  papers?: ScenarioEvidence[]
  insights?: AbmResearchInsights
  query?: string
  shock_used?: number
  // reports stage
  crisis_report?: AbmReportDoc
  solution_report?: AbmReportDoc
  // legacy evidence fields (kept for EvidencePanel compat)
  items?: ScenarioEvidence[]
  count?: number
  abstained?: boolean
  // synthesize
  synthesis?: string
  // done
  aborted?: boolean
}
export interface AbmInput {
  text: string; domain?: string; location?: string; service?: string
  case_hint?: string; steps?: number; seed?: number; shock?: number
}

// Streams POST /api/abm/simulate, invoking onEvent per NDJSON line.
export async function streamAbm(
  body: AbmInput,
  onEvent: (e: AbmEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/abm/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.body) return
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i: number
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).trim()
      buf = buf.slice(i + 1)
      if (line) {
        try {
          onEvent(JSON.parse(line) as AbmEvent)
        } catch {
          /* ignore partial / malformed line */
        }
      }
    }
  }
}

// Approval-gated write-back of an acted-on scenario into the lessons RAG.
export interface ScenarioRetainInput {
  text: string
  domain?: string
  intervention: string
  risk_before: number
  risk_after: number
  outcome?: string
  worked?: boolean
  source_case_id?: string
  confidence?: number
  approved: boolean
}
export async function retainScenario(body: ScenarioRetainInput): Promise<{ stored: boolean; message_ar?: string; reason?: string }> {
  const res = await fetch(`${BASE}/api/scenario/retain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}

// ---- Saved solutions (the agents' deliberated argument + the final report) ----
export interface SavedSolutionIn {
  scenario: string
  transcript?: { persona?: string; role?: string; round?: number; phase?: string; text?: string }[]
  tallies?: { round?: number; ready?: number; total?: number; converged?: boolean }[]
  report?: ScenarioReportDoc | null
  meta?: Record<string, unknown>
}
export const saveSolution = (body: SavedSolutionIn) =>
  j<{ ok: boolean; id?: string; message_ar?: string }>('/api/scenario/solution/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
export interface SavedSolutionMeta { id: string; ts: string; scenario: string; title_ar: string; deliberated: boolean; n_turns: number }
export const getSavedSolutions = () => j<{ solutions: SavedSolutionMeta[] }>('/api/scenario/solutions')
export const getSolution = (id: string) =>
  j<{ id: string; ts: string; scenario: string; title_ar: string; transcript: DeliberationEvent[]; tallies: DeliberationEvent[]; report: ScenarioReportDoc; meta: Record<string, unknown> }>(
    `/api/scenario/solution/${encodeURIComponent(id)}`)
export const solutionMarkdownUrl = (id: string) => `${BASE}/api/scenario/solution/${encodeURIComponent(id)}.md`

// ---- Background deliberation jobs (survive the UI closing) ----
export interface DeliberationStatus {
  ok: boolean
  status: 'running' | 'done' | 'error'
  iteration: number
  turns: number
  events: DeliberationEvent[]
  total_events: number
  report: ScenarioReportDoc | null
  scenario: string
  saved: boolean
  solution_id?: string
  error?: string
}
export const startDeliberationJob = (body: Record<string, unknown>) =>
  j<{ ok: boolean; job_id?: string }>('/api/scenario/deliberate/start', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
export const getDeliberationStatus = (jobId: string, since = 0) =>
  j<DeliberationStatus>(`/api/scenario/deliberate/status/${encodeURIComponent(jobId)}?since=${since}`)
export const getActiveDeliberations = () =>
  j<{ jobs: { job_id: string; scenario: string; status: string; iteration: number; turns: number; started: string; solution_id?: string }[] }>(
    '/api/scenario/deliberate/active')
