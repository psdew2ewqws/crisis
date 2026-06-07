// voc2.ts — T2 typed API client for the new console pages on REAL voc360 data.
// Extends lib/voc.ts: same BASE, same `j<T>` fetch helper, same AEGIS tokens.
// Every type maps to real voc360 columns (the_data, ril_problem_clusters,
// ril_text_segments) — no Zarqa demo fixtures. Import-safe: every getter has a
// graceful fallback so a page never crashes when the backend (or a not-yet-built
// endpoint) is unreachable.
//
// New endpoints consumed (all under the existing FastAPI app on :8000):
//   GET  /api/signals        recent citizen signals (the_data rows)
//   GET  /api/kpis           dashboard KPIs from real voc360 aggregates
//   GET  /api/signal-volume  time-bucketed signal volume for the chart
//   GET  /api/solutions      cause→countermeasure recommendations (T3 engine)
//   GET  /api/decisions      logged decisions
//   POST /api/decisions      append a decision
//   POST /api/narrate        optional LLM narration (grounded fallback)

const BASE =
  (import.meta.env.VITE_API as string | undefined) ??
  (typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'http://127.0.0.1:8000')

// ------------------------------------------------------------------ tokens
// AEGIS palette (mirrors tailwind.config / voc.ts usage) so callers can map a
// severity/sentiment/tone to a colour without re-declaring it per page.
export type Tone = 'danger' | 'good' | 'warn' | 'neutral'

export const AEGIS = {
  bg: '#0A0A0B',
  sidebar: '#0B0B0D',
  card: '#131417',
  cardhi: '#181A1E',
  border: '#212228',
  soft: '#1A1B20',
  txt: '#ECEDEE',
  muted: '#8B8D96',
  faint: '#62646D',
  blue: '#3B82F6',
  danger: '#F04359',
  good: '#34D399',
  warn: '#FBBF24',
} as const

// the_data.severity ∈ {low, medium, high, critical, null(=app_reviews)}
export type Severity = 'low' | 'medium' | 'high' | 'critical' | null

// the_data.sentiment_label ∈ negative / positive / neutral_citizen_sentiment /
// high_severity_complaint (+ nulls)
export type SentimentLabel =
  | 'negative'
  | 'positive'
  | 'neutral_citizen_sentiment'
  | 'high_severity_complaint'
  | string
  | null

export const severityTone = (s: Severity): Tone =>
  s === 'critical' || s === 'high' ? 'danger' : s === 'medium' ? 'warn' : s === 'low' ? 'good' : 'neutral'

export const sentimentTone = (s: SentimentLabel): Tone => {
  if (s === 'positive') return 'good'
  if (s === 'negative' || s === 'high_severity_complaint') return 'danger'
  return 'neutral'
}

export const toneColor = (t: Tone): string =>
  t === 'danger' ? AEGIS.danger : t === 'good' ? AEGIS.good : t === 'warn' ? AEGIS.warn : AEGIS.muted

// ------------------------------------------------------------------ fetch
// Same contract as voc.ts `j<T>` but never throws on the network: returns a
// fallback so pages stay mounted. Pass `fallback` to keep the UI grounded.
async function jf<T>(path: string, fallback: T, init?: RequestInit): Promise<T> {
  try {
    const r = await fetch(BASE + path, init)
    if (!r.ok) return fallback
    return (await r.json()) as T
  } catch {
    return fallback
  }
}

const qs = (params: Record<string, string | number | undefined>): string => {
  const p = Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
  return p.length ? '?' + p.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&') : ''
}

// ============================================================= SIGNALS
// One row of the_data — the signal/data-source layer.
export interface Signal {
  record_id: string
  source_type: string // app_review, social_media_sentiment, employee_complaint, فساد_إداري …
  source_platform: string | null
  source_channel: string | null
  service_id: string | null // Sanad, Amman Bus, جوازات_السفر …
  governorate: string | null // الزرقاء, إربد, العقبة … (mostly null)
  district: string | null
  text: string | null
  text_clean: string | null
  observed_at: string | null
  rating: number | null
  severity: Severity
  sentiment_label: SentimentLabel
  confidence: number | null
}

export interface SignalsResponse {
  signals: Signal[]
  total: number
  filters: { service_id?: string; severity?: string; source_type?: string }
}

export interface SignalQuery {
  service_id?: string
  severity?: string
  source_type?: string
  governorate?: string
  q?: string // free-text search over text/text_clean
  limit?: number
  offset?: number
}

const EMPTY_SIGNALS: SignalsResponse = { signals: [], total: 0, filters: {} }

export const getSignals = (query: SignalQuery = {}): Promise<SignalsResponse> =>
  jf<SignalsResponse>(`/api/signals${qs(query as Record<string, string | number | undefined>)}`, EMPTY_SIGNALS)

// ============================================================= KPIS
// Real voc360 aggregates for the Dashboard cards. Shape is component-compatible
// with the existing KpiCard fixture (title/value/badge/trend/sub).
export interface Kpi {
  key: string
  title: string
  value: string
  unit?: string
  badge: { text: string; tone: Tone }
  trend: { text: string; dir: 'up' | 'down'; tone: Tone }
  sub: string
}

export interface KpisResponse {
  kpis: Kpi[]
  generated_at?: string
  source: 'voc360' | 'fallback'
}

const FALLBACK_KPIS: KpisResponse = {
  source: 'fallback',
  kpis: [
    {
      key: 'signals',
      title: 'Citizen Signals',
      value: '—',
      badge: { text: 'voc360', tone: 'neutral' },
      trend: { text: 'Awaiting backend', dir: 'up', tone: 'neutral' },
      sub: 'the_data rows',
    },
    {
      key: 'critical',
      title: 'High / Critical',
      value: '—',
      badge: { text: 'severity', tone: 'danger' },
      trend: { text: 'Awaiting backend', dir: 'up', tone: 'neutral' },
      sub: 'high + critical complaints',
    },
    {
      key: 'clusters',
      title: 'Root-Cause Clusters',
      value: '—',
      badge: { text: 'RIL', tone: 'neutral' },
      trend: { text: 'Awaiting backend', dir: 'up', tone: 'neutral' },
      sub: 'ril_problem_clusters',
    },
    {
      key: 'services',
      title: 'Services Affected',
      value: '—',
      badge: { text: 'distinct', tone: 'neutral' },
      trend: { text: 'Awaiting backend', dir: 'up', tone: 'neutral' },
      sub: 'distinct service_id',
    },
  ],
}

export const getKpis = (caseId?: string): Promise<KpisResponse> =>
  jf<KpisResponse>(`/api/kpis${qs({ case: caseId })}`, FALLBACK_KPIS)

// ============================================================= SIGNAL VOLUME
// Time-bucketed volume for the chart. `t` is the bucket label; `v` total volume.
// Optional split by severity for stacked rendering (recharts).
export interface VolumePoint {
  t: string // bucket label (hour/day/date)
  v: number // total signals in bucket
  critical?: number
  high?: number
  negative?: number
}

export interface SignalVolumeResponse {
  series: VolumePoint[]
  bucket: 'hour' | 'day' | 'dow' | 'date'
  source: 'voc360' | 'fallback'
}

const EMPTY_VOLUME: SignalVolumeResponse = { series: [], bucket: 'day', source: 'fallback' }

export interface VolumeQuery {
  case?: string
  service_id?: string
  bucket?: 'hour' | 'day' | 'dow' | 'date'
}

export const getSignalVolume = (query: VolumeQuery = {}): Promise<SignalVolumeResponse> =>
  jf<SignalVolumeResponse>(
    `/api/signal-volume${qs(query as Record<string, string | number | undefined>)}`,
    EMPTY_VOLUME,
  )

// ============================================================= CASES
// Real voc360 services + top root-cause clusters that drive the sidebar's CASE
// list (replacing the Zarqa demo fixtures). `services` are the actual service_id
// values in the_data with their signal + critical counts; selecting one filters
// the dashboard's signal-volume + signals table by service_id.
export interface CaseServiceRow {
  id: string // real service_id (Sanad, Amman Bus, نقل_عام …)
  signals: number
  critical: number
}

export interface CaseCluster {
  rank: number
  cluster_id: string
  label_ar: string
  label_en: string | null
  members: number
  severity_avg: number
  score: number
  evidence: string[]
}

export interface CasesResponse {
  services: CaseServiceRow[]
  top_root_causes: CaseCluster[]
}

const EMPTY_CASES: CasesResponse = { services: [], top_root_causes: [] }

export const getCases = (): Promise<CasesResponse> =>
  jf<CasesResponse>('/api/cases', EMPTY_CASES)

// ============================================================= SOLUTIONS
// T3 'valid solution' engine: cause → countermeasure, feasibility, impact.
// Grounded in a ril_problem_clusters root cause.
export interface Solution {
  cluster_id: string
  label_ar: string
  label_en: string | null
  cause: string // human-readable root cause
  countermeasure: string // recommended action
  owning_service: string | null // service_id the action routes to
  feasibility: number // 0..1
  feasibility_label: 'high' | 'medium' | 'low'
  expected_impact: number // 0..1 projected reduction
  impact_label: 'high' | 'medium' | 'low'
  affected_signals: number // recovered record count for the cluster
  severity_avg: number
  evidence: string[] // sample segment_text
  rationale?: string // optional narration / justification
}

export interface SolutionsResponse {
  solutions: Solution[]
  recommendation: string | null
  source: 'engine' | 'fallback'
}

const EMPTY_SOLUTIONS: SolutionsResponse = { solutions: [], recommendation: null, source: 'fallback' }

export const getSolutions = (limit = 8): Promise<SolutionsResponse> =>
  jf<SolutionsResponse>(`/api/solutions${qs({ limit })}`, EMPTY_SOLUTIONS)

// ============================================================= DECISIONS
// Decision log — what the operator chose to do about a root cause / solution.
export interface Decision {
  id: string
  cluster_id: string | null
  title: string
  action: string
  status: 'proposed' | 'approved' | 'rejected' | 'in_progress' | 'done'
  owner?: string | null
  rationale?: string | null
  created_at: string
}

export interface DecisionsResponse {
  decisions: Decision[]
  source: 'store' | 'fallback'
}

const EMPTY_DECISIONS: DecisionsResponse = { decisions: [], source: 'fallback' }

export const getDecisions = (): Promise<DecisionsResponse> =>
  jf<DecisionsResponse>('/api/decisions', EMPTY_DECISIONS)

// Payload to log a new decision (id/created_at assigned server-side).
export interface NewDecision {
  cluster_id?: string | null
  title: string
  action: string
  status?: Decision['status']
  owner?: string | null
  rationale?: string | null
}

export interface CreateDecisionResponse {
  ok: boolean
  decision?: Decision
  error?: string
}

export const createDecision = (payload: NewDecision): Promise<CreateDecisionResponse> =>
  jf<CreateDecisionResponse>(
    '/api/decisions',
    { ok: false, error: 'backend unreachable' },
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )

// Transition an existing decision IN PLACE (the authorization gate). The server
// mutates the proposed row's status + authorized_by rather than appending a new
// one. Returns the bare updated decision row (no `ok` wrapper) on success.
export interface DecisionPatch {
  status?: Decision['status']
  authorized_by?: string
}

export const updateDecision = (
  id: string,
  patch: DecisionPatch,
): Promise<CreateDecisionResponse | Decision> =>
  jf<CreateDecisionResponse | Decision>(
    `/api/decisions/${encodeURIComponent(id)}`,
    { ok: false, error: 'backend unreachable' },
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    },
  )

// ============================================================= NARRATE (LLM)
// Optional LLM narration node for the Deer Graph flow. The backend tries the
// local model (LLM_BASE_URL, default ollama @ :11434) and falls back to a
// grounded deterministic summary when the server is unreachable — `engine`
// distinguishes the two so the UI can badge it honestly.
export interface NarrateRequest {
  case?: string
  cluster_id?: string
  topic?: 'root_cause' | 'solution' | 'simulation' | 'graph'
}

export interface NarrateResponse {
  narration: string
  engine: 'llm' | 'fallback'
  model?: string | null
  grounded_on?: string[] // cluster ids / evidence the narration is grounded in
}

const FALLBACK_NARRATION: NarrateResponse = {
  narration: 'Narration unavailable — local model unreachable and no grounded summary returned.',
  engine: 'fallback',
  model: null,
  grounded_on: [],
}

export const narrate = (req: NarrateRequest = {}): Promise<NarrateResponse> =>
  jf<NarrateResponse>('/api/narrate', FALLBACK_NARRATION, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

// ============================================================= GOVERNORATE MAP
export interface GovSignal {
  record_id: string | null
  service_id: string | null
  text_clean: string | null
  text: string | null
  severity: Severity
  sentiment_label: SentimentLabel
  observed_at: string | null
}

export interface GovSummary {
  gov: string
  total: number
  by_severity: Record<string, number>
  signals: GovSignal[]
  error?: string
}

const EMPTY_GOV: GovSummary = { gov: '', total: 0, by_severity: {}, signals: [] }

export const getGovSignals = (gov: string): Promise<GovSummary> =>
  jf<GovSummary>(`/api/gov-signals?gov=${encodeURIComponent(gov)}`, { ...EMPTY_GOV, gov })

// ============================================================= LIVE NEWS
// Google News RSS, one search per governorate (Arabic), geolocated + TTL-cached
// server-side. Each item is a marker on the Jordan map; clustered per gov.
export interface NewsItem {
  id: string
  title: string
  summary: string
  source: string
  link: string
  published: string | null
  gov: string | null
}

export interface NewsByGov {
  generated_at: string
  ttl_seconds?: number
  total: number
  by_gov: Record<string, NewsItem[]>
  national: NewsItem[]
  source: 'google_news_rss' | 'fallback'
  error?: string
}

const EMPTY_NEWS: NewsByGov = {
  generated_at: '', total: 0, by_gov: {}, national: [], source: 'fallback',
}

export const getNews = (): Promise<NewsByGov> => jf<NewsByGov>('/api/news', EMPTY_NEWS)

// Composite per-governorate analysis: recent news + signal summary + suggested scenario text.
export interface NewsAnalysis {
  gov: string
  articles: NewsItem[]
  article_count: number
  domains: string[]
  signal_total: number
  by_severity: Record<string, number>
  scenario_text: string
  generated_at: string
  error?: string
}

const EMPTY_ANALYSIS: NewsAnalysis = {
  gov: '', articles: [], article_count: 0, domains: [],
  signal_total: 0, by_severity: {}, scenario_text: '', generated_at: '',
}

export const getNewsAnalysis = (gov: string): Promise<NewsAnalysis> =>
  jf<NewsAnalysis>(`/api/news-analysis?gov=${encodeURIComponent(gov)}`, { ...EMPTY_ANALYSIS, gov })
