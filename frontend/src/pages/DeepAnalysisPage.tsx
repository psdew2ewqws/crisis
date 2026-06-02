// DeepAnalysisPage — the v3 "Deep Analysis" console: a grounded reasoning engine
// over REAL voc360 (the_data, ril_problem_clusters, ril_text_segments). It binds
// the five v3 backend capabilities into one operator surface:
//
//   • a service / cluster picker grounded in the ranked RIL root causes
//   • SUGGESTED QUESTION chips (GET /api/suggest) that on click run the analysis
//   • the WHY-CHAIN root-cause graph (reactflow, POST /api/whys → graph)
//   • a FORECAST chart (recharts AreaChart mean+band, GET /api/forecast) + escalation flag
//   • a VALIDATION badge (GET /api/validate) — verdict + 4 grounded axes + confidence
//   • a grounded ASK box (POST /api/ask) — answer + citations + followup chips
//
// TRUST BOUNDARY: every number/label/quote rendered here is a RETRIEVED fact from
// the v3 endpoints (which compose answers from real rows; the LLM only phrases).
// The page never fabricates: when an endpoint is unreachable it shows a grounded
// empty/fallback state, never invented data.
//
// IMPORT-SAFE: the v3 client (getSuggest/askWhys/getRootCauseGraph/getForecast/
// validateCase/ask/getEscalations) is defined inline against the existing voc2
// `jf<T>` fallback contract, so this file compiles and runs today against the
// current backend and degrades cleanly while the api_v3 router lands. No hard
// dependency on torch / timesfm / a live LLM — those live server-side and the
// honest `engine`/`method` flags are surfaced as badges.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  ReferenceLine,
} from 'recharts'
import {
  Brain,
  Sparkles,
  Loader2,
  RefreshCw,
  Database,
  AlertTriangle,
  Quote,
  Send,
  TrendingUp,
  TrendingDown,
  Minus,
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
  Network,
  CornerDownRight,
  Search,
  MessagesSquare,
  Layers,
  StopCircle,
} from 'lucide-react'
import { getRootCause, streamDebate, type RootCause, type DebateEvent } from '../lib/voc'
import { t } from '../lib/labels.gen'

// agent persona colours for the deep-research debate stream (mirrors ProofPanel)
const ROLE_COLOR: Record<string, string> = {
  delegate: '#22D3EE', analyst: '#3B82F6', advocate: '#34D399', skeptic: '#FBBF24', synthesizer: '#A78BFA',
}

/* ====================================================================== tokens
 * AEGIS palette (mirrors tailwind.config / voc2.ts) — kept local so the page is
 * self-contained and never depends on a not-yet-exported token table. */
const AEGIS = {
  bg: '#0A0A0B',
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

type Tone = 'danger' | 'good' | 'warn' | 'neutral'
const toneColor = (x: Tone): string =>
  x === 'danger' ? AEGIS.danger : x === 'good' ? AEGIS.good : x === 'warn' ? AEGIS.warn : AEGIS.muted

const isAr = (s?: string | null) => !!s && /[؀-ۿ]/.test(s)
const dir = (s?: string | null): 'rtl' | 'ltr' => (isAr(s) ? 'rtl' : 'ltr')

// severity_avg is 0..~1 across the RIL layer; band it like RootCausePage/LiveGraph.
function sevTone(sev: number): Tone {
  if (sev >= 0.5) return 'danger'
  if (sev >= 0.3) return 'warn'
  return 'good'
}
function sevColor(sev: number): string {
  return toneColor(sevTone(sev))
}

/* ===================================================================== v3 client
 * Import-safe fetch helper identical in spirit to voc2.ts `jf<T>`: never throws on
 * the network, returns the grounded `fallback` so the page stays mounted. */
const BASE =
  (import.meta.env.VITE_API as string | undefined) ??
  (typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'http://127.0.0.1:8000')

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
const jpost = <T,>(path: string, body: unknown, fallback: T): Promise<T> =>
  jf<T>(path, fallback, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

/* ---- shared v3 types (mirror D-api.md contracts) ---- */
type Engine = 'llm' | 'fallback' | string
type Verdict = 'valid' | 'weak' | 'insufficient'
type FcMethod = 'timesfm-2.5' | 'timesfm-2.0' | 'holt-winters' | 'seasonal-naive' | 'empty' | string

export interface Citation {
  type?: 'segment' | 'signal' | 'cluster' | 'forecast' | 'service' | 'engine' | string
  id?: string
  label?: string
  text?: string
}

// reactflow-feeding why graph (api_v3 /api/whys.graph & /api/rootcause-graph)
export interface WhyNode {
  id: string
  depth: number
  kind?: 'symptom' | 'cluster' | 'subtheme' | 'root' | string
  type?: 'service' | 'cluster' | 'subtheme' | 'phrase' | string
  label_ar?: string
  label_en?: string
  label?: string
  count?: number
  severity_avg?: number
  evidence?: string[]
  why?: string
  signals?: number
}
export interface WhyEdge {
  source: string
  target: string
  weight?: number
  kind?: string
}
export interface WhyGraph {
  nodes: WhyNode[]
  edges: WhyEdge[]
  stats?: { depth?: number; leaves?: number; total_signals?: number }
}
export interface WhyChainStep {
  depth: number
  why?: string
  question?: string
  label_ar?: string
  label_en?: string
  because?: string
  because_en?: string
  count?: number
  members?: number
  signals?: number
  severity_avg?: number
  confidence?: number
  evidence?: string[]
}
export interface WhysResponse {
  case?: string
  cluster_id?: string
  depth?: number
  chain: WhyChainStep[]
  graph: WhyGraph
  narration?: string
  engine?: Engine
  root?: WhyChainStep | null
}

export interface SuggestQuestion {
  id: string
  text?: string
  q?: string
  kind?: 'whys' | 'validate' | 'forecast' | 'ask' | string
  intent?: string
  category?: string // Arabic group header emitted by /api/suggest
  params?: { case?: string; cluster_id?: string; service?: string; id?: string; [k: string]: unknown }
  why_useful?: string
}
export interface SuggestResponse {
  questions?: SuggestQuestion[]
  suggestions?: SuggestQuestion[]
  grounded?: boolean
}

export interface FcPoint {
  t: string
  mean: number
  lo: number
  hi: number
}
export interface HistPoint {
  t: string
  v: number
}
export interface Escalation {
  recent_mean?: number
  forecast_mean?: number
  ratio?: number
  escalating?: boolean
}
export interface ForecastResponse {
  target?: string
  id?: string
  metric?: 'volume' | 'sentiment' | string
  history: HistPoint[]
  forecast: FcPoint[]
  method?: FcMethod
  source?: FcMethod // live API emits the engine here ('seasonal-naive' | 'timesfm-2.5' | ...)
  escalation?: Escalation | null
  narration?: string
  engine?: Engine
}

export interface ValAxis {
  score?: number
  pass?: boolean
  trend?: string
  slope?: number
  delta?: number
  signals?: number
  segments?: number
  of?: number
  detail?: string
}
export interface ValidateResponse {
  cluster_id?: string
  label_en?: string
  label_ar?: string
  verdict?: Verdict
  confidence?: number
  score?: number
  axes?: Record<string, ValAxis>
  checks?: Array<{ name: string; pass: boolean; detail?: string; value?: unknown; weight?: number }>
  citations?: Citation[]
  narration?: string
  engine?: Engine
  summary?: string
}

export interface AskResponse {
  question?: string
  answer: string
  intent?: string
  grounded?: boolean
  facts?: Array<{ label: string; value: string | number }>
  citations?: Citation[]
  engine?: Engine
  followups?: string[]
}

export interface EscalationRow {
  level?: 'service' | 'cluster' | string
  id?: string
  label?: string
  label_ar?: string
  ratio?: number
  growth?: number
  escalating?: boolean
  base?: number
  proj?: number
}
export interface EscalationsResponse {
  escalations?: EscalationRow[]
  items?: EscalationRow[]
  source?: FcMethod
}

/* ---- fallbacks (grounded-empty, never fabricated) ---- */
const FB_WHYS: WhysResponse = { chain: [], graph: { nodes: [], edges: [] }, engine: 'fallback' }
const FB_SUGGEST: SuggestResponse = { questions: [], grounded: false }
const FB_FORECAST: ForecastResponse = {
  history: [],
  forecast: [],
  method: 'empty',
  escalation: null,
  engine: 'fallback',
}
const FB_VALIDATE: ValidateResponse = { verdict: 'insufficient', confidence: 0, axes: {}, engine: 'fallback' }
const FB_ASK: AskResponse = {
  answer: 'No voc360 facts retrieved — the analysis backend is unreachable.',
  grounded: false,
  citations: [],
  followups: [],
  engine: 'fallback',
}
const FB_ESCALATIONS: EscalationsResponse = { escalations: [], source: 'empty' }

/* ---- client funcs (names mirror the planned voc2 exports) ---- */
type Scope = { type: 'service' | 'cluster'; key: string }

const getSuggest = (scope: Scope | null, n = 6): Promise<SuggestResponse> =>
  jf<SuggestResponse>(
    `/api/suggest${qs(
      scope
        ? scope.type === 'cluster'
          ? { cluster_id: scope.key, n, type: 'cluster', key: scope.key }
          : { case: scope.key, n, type: 'service', key: scope.key }
        : { n, type: 'national' },
    )}`,
    FB_SUGGEST,
  )

const askWhys = (scope: Scope, maxDepth = 5): Promise<WhysResponse> =>
  jpost<WhysResponse>(
    '/api/whys',
    scope.type === 'cluster' ? { cluster_id: scope.key, max_depth: maxDepth } : { case: scope.key, max_depth: maxDepth },
    FB_WHYS,
  )

const getForecast = (
  scope: Scope,
  horizon = 30,
  metric: 'volume' | 'sentiment' = 'volume',
): Promise<ForecastResponse> =>
  jf<ForecastResponse>(`/api/forecast${qs({ entity: scope.type, key: scope.key, horizon, metric })}`, FB_FORECAST)

const validateCase = (scope: Scope): Promise<ValidateResponse> =>
  jf<ValidateResponse>(
    `/api/validate${qs(scope.type === 'cluster' ? { cluster_id: scope.key } : { case: scope.key })}`,
    FB_VALIDATE,
  )

const ask = (question: string, caseId?: string): Promise<AskResponse> =>
  jpost<AskResponse>('/api/ask', { question, case: caseId }, { ...FB_ASK, question })

const getEscalations = (horizon = 14): Promise<EscalationsResponse> =>
  jf<EscalationsResponse>(`/api/forecast/escalations${qs({ horizon })}`, FB_ESCALATIONS)

/* ============================================================ label resolution
 * Prefer the build-time map (labels.gen t()), then the row's own label_en, then
 * the raw Arabic — never invent. */
function enOf(row: { cluster_id?: string; label_en?: string | null; label_ar?: string | null }): string {
  const fromMap = row.cluster_id ? t(row.cluster_id) : ''
  const en = (fromMap && fromMap !== row.cluster_id ? fromMap : '') || row.label_en || ''
  return (en || '').trim() || (row.label_ar || '').trim() || '(untranslated)'
}

/* ================================================================== why graph
 * Depth-layered reactflow node mirroring the LiveGraph GNode look. */
const KIND_TAG: Record<string, string> = {
  symptom: 'SYMPTOM',
  cluster: 'CLUSTER',
  subtheme: 'SUB-THEME',
  root: 'ROOT CAUSE',
  service: 'SERVICE',
  phrase: 'ROOT CAUSE',
}

// the live /api/whys nodes carry `type` (service|cluster|subtheme|phrase); older
// shapes used `kind` — read either so colors/tags resolve against the real keys.
const nodeKind = (n: WhyNode): string => (n.kind ?? n.type ?? '')

function WhyGNode({ data }: NodeProps) {
  const c = data.color as string
  const active = data.active as boolean
  return (
    <div
      className="rounded-lg border bg-card transition-shadow"
      style={{
        borderColor: c,
        minWidth: data.w,
        boxShadow: active ? `0 0 0 1.5px ${c}, 0 0 22px -6px ${c}` : `0 0 16px -7px ${c}`,
      }}
    >
      <Handle type="target" position={Position.Left} className="!h-1 !w-1 !border-0 !bg-border" />
      <div className="px-2.5 py-1.5" dir={dir(data.label as string)}>
        <div className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: c }} />
          <span className="font-mono text-[8px] tracking-[0.12em] text-faint">{data.tag}</span>
          {data.count ? <span className="ml-auto font-mono text-[9px] text-muted">{data.count}</span> : null}
        </div>
        <div className="mt-0.5 text-[11px] leading-tight text-txt" style={{ maxWidth: 210 }}>
          {data.label}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!h-1 !w-1 !border-0 !bg-border" />
    </div>
  )
}
const nodeTypes = { why: WhyGNode }

function whyNodeColor(n: WhyNode): string {
  const k = nodeKind(n)
  if (k === 'symptom' || k === 'service') return AEGIS.blue
  if (k === 'root' || k === 'phrase') return AEGIS.danger
  return sevColor(n.severity_avg ?? 0)
}

/* ===================================================================== page */
export default function DeepAnalysisPage() {
  // ---- entity universe (grounded in ranked RIL clusters) ----
  const [causes, setCauses] = useState<RootCause[]>([])
  const [services, setServices] = useState<string[]>([])
  const [universeErr, setUniverseErr] = useState<string | null>(null)
  const [loadingUniverse, setLoadingUniverse] = useState(true)

  // ---- selected scope ----
  const [scope, setScope] = useState<Scope | null>(null)

  // ---- panels ----
  const [suggest, setSuggest] = useState<SuggestResponse>(FB_SUGGEST)
  const [whys, setWhys] = useState<WhysResponse>(FB_WHYS)
  const [forecast, setForecast] = useState<ForecastResponse>(FB_FORECAST)
  const [validation, setValidation] = useState<ValidateResponse>(FB_VALIDATE)
  const [escalations, setEscalations] = useState<EscalationsResponse>(FB_ESCALATIONS)

  // per-panel loading
  const [busy, setBusy] = useState({ suggest: false, whys: false, forecast: false, validate: false })
  const [metric, setMetric] = useState<'volume' | 'sentiment'>('volume')
  const [selectedNode, setSelectedNode] = useState<WhyNode | null>(null)

  // ---- ask box ----
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [asking, setAsking] = useState(false)
  const askRef = useRef<HTMLInputElement | null>(null)

  // ---- deep-research agent debate (streamed) ----
  const [debateTurns, setDebateTurns] = useState<DebateEvent[]>([])
  const [debateDossier, setDebateDossier] = useState<DebateEvent | null>(null)
  const [debating, setDebating] = useState(false)
  const debateAbortRef = useRef<AbortController | null>(null)

  /* ---------------------------------------------------- load entity universe */
  const loadUniverse = useCallback(async () => {
    setLoadingUniverse(true)
    setUniverseErr(null)
    try {
      const rc = await getRootCause().catch(() => ({ root_causes: [] as RootCause[], recommendation: '' }))
      const ranked = rc.root_causes ?? []
      setCauses(ranked)
      // distinct owning services are surfaced by the suggest/forecast layer; seed
      // a small service list from a national suggest probe + a few known service_ids
      // that the_data carries (Sanad/Amman Bus/Bekhedmetkom are the app-review heavy
      // ones). These are real service_id values, never invented.
      const seed = ['Sanad', 'Amman Bus', 'Bekhedmetkom', 'نقل_عام', 'طرق_وبنية_تحتية', 'جوازات_السفر']
      setServices(seed)
      // default scope = the #1 root-cause cluster (grounded), else first service
      setScope((prev) => prev ?? (ranked[0] ? { type: 'cluster', key: ranked[0].cluster_id } : { type: 'service', key: seed[0] }))
    } catch (e) {
      setUniverseErr(String(e))
    } finally {
      setLoadingUniverse(false)
    }
  }, [])

  useEffect(() => {
    void loadUniverse()
    void getEscalations(14).then(setEscalations)
  }, [loadUniverse])

  /* ----------------------------------------------- run the deep analysis suite */
  const runAnalysis = useCallback(
    async (sc: Scope, m: 'volume' | 'sentiment' = metric) => {
      setBusy({ suggest: true, whys: true, forecast: true, validate: true })
      setSelectedNode(null)
      // fire all panels in parallel — each is independently grounded + fallback-safe
      void getSuggest(sc, 6)
        .then(setSuggest)
        .finally(() => setBusy((b) => ({ ...b, suggest: false })))
      void askWhys(sc, 5)
        .then((w) => {
          setWhys(w)
          // auto-select the deepest (root) node for the evidence panel
          const root = [...(w.graph.nodes ?? [])].sort((a, b) => (b.depth ?? 0) - (a.depth ?? 0))[0] ?? null
          setSelectedNode(root)
        })
        .finally(() => setBusy((b) => ({ ...b, whys: false })))
      void getForecast(sc, 30, m)
        .then(setForecast)
        .finally(() => setBusy((b) => ({ ...b, forecast: false })))
      void validateCase(sc)
        .then(setValidation)
        .finally(() => setBusy((b) => ({ ...b, validate: false })))
    },
    [metric],
  )

  // run whenever scope changes
  useEffect(() => {
    if (scope) void runAnalysis(scope, metric)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope?.type, scope?.key])

  // refetch only the forecast when metric toggles
  useEffect(() => {
    if (!scope) return
    setBusy((b) => ({ ...b, forecast: true }))
    void getForecast(scope, 30, metric)
      .then(setForecast)
      .finally(() => setBusy((b) => ({ ...b, forecast: false })))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [metric])

  /* ------------------------------------------------------ suggested-question run */
  const runSuggestion = useCallback(
    (sq: SuggestQuestion) => {
      const p = sq.params ?? {}
      const text = sq.text ?? sq.q ?? ''
      const kind = sq.kind ?? sq.intent

      // resolve scope — handles all param shapes the backend emits:
      //   {cluster_id}, {case}, {service}, {type+key}, {entity+key}, {id}
      const resolvedScope: Scope | null = p.cluster_id
        ? { type: 'cluster', key: String(p.cluster_id) }
        : p.case || p.service
          ? { type: 'service', key: String(p.case ?? p.service) }
          : (p.type === 'cluster' || p.entity === 'cluster') && p.key
            ? { type: 'cluster', key: String(p.key) }
            : (p.type === 'service' || p.entity === 'service') && p.key
              ? { type: 'service', key: String(p.key) }
              : p.id
                ? { type: 'cluster', key: String(p.id) }
                : scope

      // intents that drive the analysis panels (why-chain graph, forecast, validation)
      // → change scope so all panels refresh; everything else → grounded Q&A box
      const SCOPE_INTENTS = new Set(['why_chain', 'forecast_volume', 'case_validation'])
      if (SCOPE_INTENTS.has(kind ?? '') && resolvedScope) {
        if (resolvedScope.key !== scope?.key || resolvedScope.type !== scope?.type) {
          setScope(resolvedScope)
        } else {
          void runAnalysis(resolvedScope, metric)
        }
        return
      }

      // all other intents (root_cause_rank, escalation_scan, metric_breakdown,
      // compare_services, sim_impact, cluster_subthemes, cluster_services, ask…)
      // → put question in the ask box and scroll to it
      setQuestion(text)
      void runAsk(text, resolvedScope?.type === 'service' ? resolvedScope.key : undefined)
      askRef.current?.focus()
      askRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scope, metric],
  )

  /* ------------------------------------------------------------------- ask */
  const runAsk = useCallback(
    async (q: string, caseId?: string) => {
      const query = q.trim()
      if (!query) return
      setAsking(true)
      try {
        const res = await ask(query, caseId ?? (scope?.type === 'service' ? scope.key : undefined))
        setAnswer(res)
      } finally {
        setAsking(false)
      }
    },
    [scope],
  )

  /* ------------------------------------------- deep-research: stream the debate
   * Streams POST /api/debate for the current scope (cluster/service/all). Mirrors
   * the abortable pattern in components/ProofPanel.tsx. */
  const debateQuery: { type: 'cluster' | 'service' | 'all'; key?: string } = scope
    ? { type: scope.type, key: scope.key }
    : { type: 'all' }

  const stopDebate = useCallback(() => {
    debateAbortRef.current?.abort()
    setDebating(false)
  }, [])

  const runDebate = useCallback(async () => {
    if (debating) return
    setDebateTurns([])
    setDebateDossier(null)
    setDebating(true)
    const ac = new AbortController()
    debateAbortRef.current = ac
    try {
      await streamDebate(
        // Deep Analysis runs the FULL multi-cluster deep-research swarm.
        { ...debateQuery, mode: 'deep', top_k: 6 },
        (e) => {
          if (e.type === 'dossier' || e.type === 'plan') setDebateDossier(e)
          else if (e.type === 'turn' || e.type === 'synthesis' || e.type === 'cluster' || e.type === 'phase')
            setDebateTurns((xs) => [...xs, e])
        },
        ac.signal,
      )
    } catch {
      /* aborted or network error — keep whatever streamed */
    } finally {
      setDebating(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debating, scope?.type, scope?.key])

  // reset the debate whenever the analysis target changes
  useEffect(() => {
    setDebateTurns([])
    setDebateDossier(null)
    setDebating(false)
    debateAbortRef.current?.abort()
  }, [scope?.type, scope?.key])

  /* --------------------------------------------------- derived: forecast chart */
  const fcData = useMemo(() => {
    const hist = forecast.history ?? []
    const fc = forecast.forecast ?? []
    // history rows: only `v`; forecast rows: mean/lo/hi/band — recharts plots both
    const h = hist.map((p) => ({ t: p.t, hist: p.v }))
    const f = fc.map((p) => ({ t: p.t, mean: p.mean, lo: p.lo, band: Math.max(0, (p.hi ?? 0) - (p.lo ?? 0)) }))
    return [...h, ...f]
  }, [forecast])
  const lastHistT = (forecast.history ?? []).at(-1)?.t

  /* --------------------------------------------------- derived: reactflow graph */
  const { rfNodes, rfEdges } = useMemo(() => {
    const g = whys.graph
    if (!g || !g.nodes?.length) return { rfNodes: [] as Node[], rfEdges: [] as Edge[] }
    // group by depth for an x-layered tree; spread siblings on y
    const byDepth = new Map<number, WhyNode[]>()
    for (const n of g.nodes) {
      const d = n.depth ?? 0
      if (!byDepth.has(d)) byDepth.set(d, [])
      byDepth.get(d)!.push(n)
    }
    const COLW = 280
    const ROWH = 96
    const pos = new Map<string, { x: number; y: number }>()
    for (const [d, list] of byDepth) {
      const total = list.length
      list.forEach((n, i) => {
        pos.set(n.id, { x: d * COLW + 40, y: (i - (total - 1) / 2) * ROWH + 260 })
      })
    }
    const rfNodes: Node[] = g.nodes.map((n) => {
      const label = n.label_ar && isAr(n.label_ar) ? n.label_ar : enOf(n) || n.label || n.why || n.label_ar || ''
      const c = whyNodeColor(n)
      return {
        id: n.id,
        type: 'why',
        position: pos.get(n.id) ?? { x: 0, y: 0 },
        draggable: true,
        data: {
          label,
          tag: KIND_TAG[nodeKind(n)] ?? nodeKind(n).toUpperCase(),
          count: n.count ?? n.signals,
          color: c,
          active: selectedNode?.id === n.id,
          w: Math.min(240, 110 + Math.sqrt((n.count ?? n.signals ?? 1) || 1) * 4),
        },
      }
    })
    const rfEdges: Edge[] = (g.edges ?? []).map((e, i) => ({
      id: `e${i}`,
      source: e.source,
      target: e.target,
      animated: true,
      style: {
        stroke: '#F04359',
        strokeWidth: Math.min(3.5, 0.8 + Math.log10((e.weight ?? 1) + 1) * 1.3),
        opacity: 0.72,
      },
    }))
    return { rfNodes, rfEdges }
  }, [whys, selectedNode])

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      const found = whys.graph.nodes.find((n) => n.id === node.id) ?? null
      setSelectedNode(found)
    },
    [whys],
  )

  /* ===================================================================== render */
  const scopeLabel =
    scope?.type === 'cluster'
      ? enOf(causes.find((c) => c.cluster_id === scope.key) ?? { cluster_id: scope.key })
      : (scope?.key ?? '—')

  return (
    <div className="flex-1 overflow-y-auto bg-bg">
      <div className="mx-auto max-w-[1340px] px-8 py-7">
        {/* ----------------------------------------------------------- header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="flex items-center gap-2.5 text-[28px] font-semibold tracking-tight text-txt">
              <Brain className="h-7 w-7 text-blue" />
              Deep Analysis
            </h1>
            <p className="mt-1.5 flex items-center gap-2 text-[14px] text-muted">
              <Database className="h-3.5 w-3.5" />
              Grounded 5-Whys · forecast · validation over real voc360
              {causes.length > 0 && (
                <span className="text-faint">· {causes.length} root-cause clusters in scope</span>
              )}
            </p>
          </div>
          <button
            onClick={() => {
              void loadUniverse()
              if (scope) void runAnalysis(scope, metric)
            }}
            disabled={loadingUniverse}
            className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-60"
          >
            {loadingUniverse ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {loadingUniverse ? 'Loading…' : 'Refresh'}
          </button>
        </div>

        {universeErr && (
          <div className="mt-6 flex items-center gap-2 rounded-lg border border-danger/40 bg-card px-4 py-3 text-[13px] text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            Could not load the entity universe — {universeErr}
          </div>
        )}

        {/* ----------------------------------------------------- scope picker */}
        <div className="mt-6 rounded-xl border border-border bg-card p-4">
          <div className="mb-3 flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] text-faint">
            <Network className="h-3.5 w-3.5" />
            ANALYSIS TARGET
          </div>
          <div className="flex flex-col gap-3 lg:flex-row">
            {/* services */}
            <div className="min-w-0 flex-1">
              <div className="mb-1.5 text-[11px] text-muted">Service</div>
              <div className="flex flex-wrap gap-1.5">
                {services.map((s) => {
                  const on = scope?.type === 'service' && scope.key === s
                  return (
                    <button
                      key={s}
                      onClick={() => setScope({ type: 'service', key: s })}
                      dir={dir(s)}
                      className={`rounded-lg border px-2.5 py-1.5 text-[12.5px] transition-colors ${
                        on
                          ? 'border-blue bg-blue/15 text-txt'
                          : 'border-border bg-cardhi text-muted hover:bg-soft hover:text-txt'
                      }`}
                    >
                      {isAr(s) ? s : t(s) || s}
                    </button>
                  )
                })}
              </div>
            </div>
            {/* clusters */}
            <div className="min-w-0 flex-[1.4]">
              <div className="mb-1.5 text-[11px] text-muted">Root-cause cluster (RIL)</div>
              <div className="flex flex-wrap gap-1.5">
                {causes.slice(0, 8).map((c) => {
                  const on = scope?.type === 'cluster' && scope.key === c.cluster_id
                  const en = enOf(c)
                  return (
                    <button
                      key={c.cluster_id}
                      onClick={() => setScope({ type: 'cluster', key: c.cluster_id })}
                      title={c.label_ar || en}
                      className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12.5px] transition-colors ${
                        on
                          ? 'border-blue bg-blue/15 text-txt'
                          : 'border-border bg-cardhi text-muted hover:bg-soft hover:text-txt'
                      }`}
                    >
                      <span
                        className="h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ background: sevColor(c.severity_avg) }}
                      />
                      <span className="max-w-[200px] truncate">{en}</span>
                      <span className="font-mono text-[10px] text-faint">{c.members}</span>
                    </button>
                  )
                })}
                {causes.length === 0 && !loadingUniverse && (
                  <span className="text-[12px] text-muted">No clusters returned by voc360.</span>
                )}
              </div>
            </div>
          </div>
          {scope && (
            <div className="mt-3 flex items-center gap-2 border-t border-border pt-3 text-[12px] text-muted">
              <span className="font-mono text-[10px] tracking-[0.12em] text-faint">SELECTED</span>
              <span className="text-txt" dir={dir(scopeLabel)}>
                {scopeLabel}
              </span>
              <span className="rounded-md bg-soft px-1.5 py-0.5 font-mono text-[10px] text-faint">{scope.type}</span>
            </div>
          )}
        </div>

        {/* ---------------------------------------------- suggested questions */}
        <SuggestedQuestions
          data={suggest}
          busy={busy.suggest}
          onPick={runSuggestion}
          onFreeAsk={(q) => {
            // free-pick: reuse the exact ASK flow the chips use (populate + submit)
            setQuestion(q)
            void runAsk(q)
            askRef.current?.focus()
            askRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
          }}
        />

        {/* ------------------------------------------- main grid: graph + side */}
        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
          {/* WHY-CHAIN graph */}
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] text-faint">
                <Sparkles className="h-3.5 w-3.5" />
                WHY-CHAIN · ROOT-CAUSE GRAPH
              </div>
              <div className="flex items-center gap-2">
                {whys.engine && <EngineBadge engine={whys.engine} />}
                {busy.whys && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted" />}
              </div>
            </div>
            <div className="relative h-[440px]">
              {rfNodes.length > 0 ? (
                <ReactFlow
                  nodes={rfNodes}
                  edges={rfEdges}
                  nodeTypes={nodeTypes}
                  fitView
                  fitViewOptions={{ padding: 0.2 }}
                  proOptions={{ hideAttribution: true }}
                  minZoom={0.2}
                  nodesConnectable={false}
                  elementsSelectable
                  onNodeClick={onNodeClick}
                >
                  <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#1A1B20" />
                  <MiniMap
                    nodeColor={(n) => (n.data as { color: string }).color}
                    maskColor="transparent"
                    style={{ background: 'var(--color-card)' }}
                    pannable
                  />
                  <Controls showInteractive={false} />
                </ReactFlow>
              ) : (
                <div className="grid h-full place-items-center text-[13px] text-muted">
                  {busy.whys ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" /> Tracing the why-chain…
                    </span>
                  ) : (
                    'No grounded why-chain for this target.'
                  )}
                </div>
              )}
            </div>
            {/* chain spine as text (symptom → root) */}
            {whys.chain.length > 0 && (
              <div className="border-t border-border px-5 py-3">
                <ol className="space-y-1.5">
                  {whys.chain.map((step) => {
                    const because = step.because_en || enOf(step) || step.because || step.label_ar || ''
                    return (
                      <li key={step.depth} className="flex items-start gap-2 text-[12.5px]">
                        <span className="mt-0.5 font-mono text-[10px] text-faint">#{step.depth}</span>
                        <div className="min-w-0">
                          <span className="text-muted">{step.why || step.question || 'Why?'} → </span>
                          <span className="text-txt" dir={dir(because)}>
                            {because}
                          </span>
                          {(step.signals ?? step.count ?? step.members) != null && (
                            <span className="ml-1.5 font-mono text-[10px] text-faint">
                              {(step.signals ?? step.count ?? step.members)?.toLocaleString()} signals
                            </span>
                          )}
                          {step.confidence != null && (
                            <span className="ml-1.5 font-mono text-[10px] text-faint">
                              conf {(step.confidence * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                      </li>
                    )
                  })}
                </ol>
              </div>
            )}
          </div>

          {/* RIGHT COLUMN: validation + evidence */}
          <div className="flex flex-col gap-4">
            <ValidationBadge data={validation} busy={busy.validate} />
            <EvidencePanel node={selectedNode} />
          </div>
        </div>

        {/* ---------------------------------------------------------- forecast */}
        <ForecastPanel
          data={forecast}
          busy={busy.forecast}
          metric={metric}
          onMetric={setMetric}
          fcData={fcData}
          lastHistT={lastHistT}
          escalations={escalations}
        />

        {/* -------------------------------------------------------------- ask */}
        <AskPanel
          inputRef={askRef}
          question={question}
          setQuestion={setQuestion}
          asking={asking}
          answer={answer}
          onAsk={() => void runAsk(question)}
          onFollowup={(f) => {
            setQuestion(f)
            void runAsk(f)
          }}
          scopeLabel={scopeLabel}
          debating={debating}
          debateTurns={debateTurns}
          debateDossier={debateDossier}
          onDebate={() => void runDebate()}
          onStopDebate={stopDebate}
        />
      </div>
    </div>
  )
}

/* ===================================================== suggested questions */
function SuggestedQuestions({
  data,
  busy,
  onPick,
  onFreeAsk,
}: {
  data: SuggestResponse
  busy: boolean
  onPick: (q: SuggestQuestion) => void
  onFreeAsk: (q: string) => void
}) {
  const list = data.questions ?? data.suggestions ?? []
  const [free, setFree] = useState('')

  // group chips by their Arabic `category`; ungrouped chips fall into a default
  // bucket so nothing is ever dropped. Insertion order preserved (Map).
  const groups = useMemo(() => {
    const m = new Map<string, SuggestQuestion[]>()
    for (const q of list) {
      const cat = (q.category ?? '').trim() || 'أسئلة مقترحة'
      if (!m.has(cat)) m.set(cat, [])
      m.get(cat)!.push(q)
    }
    return [...m.entries()]
  }, [list])

  const submitFree = () => {
    const q = free.trim()
    if (!q) return
    onFreeAsk(q)
    setFree('')
  }

  return (
    <div className="mt-4 rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] text-faint">
          <Sparkles className="h-3.5 w-3.5 text-warn" />
          SUGGESTED QUESTIONS
          {data.grounded === false && <span className="text-faint">· awaiting backend</span>}
        </div>
        {busy && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted" />}
      </div>

      {/* free-pick: type your own question → runs the same ASK flow as the chips */}
      <div className="mb-3 flex items-center gap-2">
        <input
          value={free}
          onChange={(e) => setFree(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submitFree()
          }}
          dir={dir(free)}
          placeholder="اكتب سؤالك بنفسك…"
          className="min-w-0 flex-1 rounded-lg border border-border bg-bg px-3 py-2 text-[13px] text-txt placeholder:text-faint focus:border-blue/60 focus:outline-none"
        />
        <button
          onClick={submitFree}
          disabled={!free.trim()}
          className="flex shrink-0 items-center gap-1.5 rounded-lg bg-blue px-3 py-2 text-[12.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-50"
        >
          <Send className="h-3.5 w-3.5" />
          اسأل
        </button>
      </div>

      {list.length > 0 ? (
        <div className="space-y-3">
          {groups.map(([cat, qs]) => (
            <div key={cat}>
              <div className="mb-1.5 font-mono text-[10px] tracking-[0.12em] text-faint" dir={dir(cat)}>
                {cat}
              </div>
              <div className="flex flex-wrap gap-2">
                {qs.map((q) => {
                  const text = q.text ?? q.q ?? ''
                  return (
                    <button
                      key={q.id}
                      onClick={() => onPick(q)}
                      dir={dir(text)}
                      title={q.why_useful}
                      className="group flex max-w-[420px] items-center gap-2 rounded-lg border border-border bg-cardhi px-3 py-2 text-left text-[12.5px] text-muted transition-colors hover:border-blue/50 hover:bg-soft hover:text-txt"
                    >
                      <CornerDownRight className="h-3.5 w-3.5 shrink-0 text-faint group-hover:text-blue" />
                      <span className="truncate">{text}</span>
                      {(q.kind || q.intent) && (
                        <span className="ml-auto shrink-0 rounded bg-soft px-1.5 py-0.5 font-mono text-[9px] text-faint">
                          {q.kind ?? q.intent}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[12.5px] text-muted">
          {busy ? 'Generating grounded questions…' : 'No suggested questions for this target.'}
        </p>
      )}
    </div>
  )
}

/* ===================================================== validation badge */
const VERDICT_META: Record<Verdict, { tone: Tone; Icon: typeof ShieldCheck; label: string }> = {
  valid: { tone: 'good', Icon: ShieldCheck, label: 'VALID' },
  weak: { tone: 'warn', Icon: ShieldAlert, label: 'WEAK' },
  insufficient: { tone: 'danger', Icon: ShieldQuestion, label: 'INSUFFICIENT' },
}

function ValidationBadge({ data, busy }: { data: ValidateResponse; busy: boolean }) {
  const verdict = (data.verdict ?? 'insufficient') as Verdict
  const meta = VERDICT_META[verdict] ?? VERDICT_META.insufficient
  const conf = data.confidence ?? 0
  const col = toneColor(meta.tone)

  // normalise axes (api may return `axes` map or `checks` list)
  const axes: Array<{ key: string; score: number; pass: boolean; detail: string }> = []
  if (data.axes) {
    for (const [k, a] of Object.entries(data.axes)) {
      const score =
        a.score != null
          ? a.score
          : a.pass
            ? 1
            : 0
      axes.push({
        key: k,
        score: Math.max(0, Math.min(1, score)),
        pass: !!a.pass,
        detail:
          a.detail ??
          a.trend ??
          [
            a.signals != null ? `${a.signals} signals` : '',
            a.segments != null ? `${a.segments} segments` : '',
            a.slope != null ? `slope ${a.slope}` : '',
            a.delta != null ? `Δ ${a.delta}` : '',
          ]
            .filter(Boolean)
            .join(' · '),
      })
    }
  } else if (data.checks) {
    for (const c of data.checks) {
      axes.push({
        key: c.name,
        score: c.pass ? 1 : 0,
        pass: !!c.pass,
        detail: c.detail ?? '',
      })
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] text-faint">
          <ShieldCheck className="h-3.5 w-3.5" />
          CASE VALIDATION
        </div>
        {busy && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted" />}
      </div>

      <div className="flex items-center gap-3">
        <div
          className="flex items-center gap-2 rounded-lg border px-3 py-2"
          style={{ borderColor: col, background: `${col}1a` }}
        >
          <meta.Icon className="h-5 w-5" style={{ color: col }} />
          <span className="text-[15px] font-semibold tracking-tight" style={{ color: col }}>
            {meta.label}
          </span>
        </div>
        <div className="leading-tight">
          <div className="font-mono text-[20px] text-txt">{(conf * 100).toFixed(0)}%</div>
          <div className="font-mono text-[9px] tracking-[0.12em] text-faint">CONFIDENCE</div>
        </div>
      </div>

      {axes.length > 0 ? (
        <div className="mt-4 space-y-2.5">
          {axes.map((a) => (
            <AxisBar key={a.key} name={a.key} score={a.score} pass={a.pass} detail={a.detail} />
          ))}
        </div>
      ) : (
        <p className="mt-3 text-[12px] text-muted">
          {busy ? 'Validating coverage, evidence, trend, sim-impact…' : 'No validation axes returned.'}
        </p>
      )}

      {(data.summary || data.narration) && (
        <p className="mt-3 border-t border-border pt-3 text-[12.5px] leading-snug text-muted" dir={dir(data.summary || data.narration)}>
          {data.summary || data.narration}
        </p>
      )}
      {data.engine && (
        <div className="mt-2">
          <EngineBadge engine={data.engine} />
        </div>
      )}
    </div>
  )
}

function AxisBar({ name, score, pass, detail }: { name: string; score: number; pass: boolean; detail: string }) {
  const col = pass ? AEGIS.good : score >= 0.4 ? AEGIS.warn : AEGIS.danger
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[12px] capitalize text-txt">{name.replace(/_/g, ' ')}</span>
        <span className="font-mono text-[10px]" style={{ color: col }}>
          {pass ? 'PASS' : 'FAIL'} · {(score * 100).toFixed(0)}%
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-soft">
        <div className="h-full rounded-full" style={{ width: `${Math.min(100, score * 100)}%`, background: col }} />
      </div>
      {detail && (
        <div className="mt-0.5 truncate font-mono text-[10px] text-faint" dir={dir(detail)}>
          {detail}
        </div>
      )}
    </div>
  )
}

/* ===================================================== evidence panel */
function EvidencePanel({ node }: { node: WhyNode | null }) {
  if (!node) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 text-[13px] text-muted">
        Click a node in the why-chain graph to inspect its grounded evidence.
      </div>
    )
  }
  const label = node.label_ar && isAr(node.label_ar) ? node.label_ar : enOf(node) || node.label || node.why || ''
  const col = whyNodeColor(node)
  const ev = node.evidence ?? []
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: col }} />
        <span className="font-mono text-[10px] tracking-[0.14em] text-faint">
          {KIND_TAG[nodeKind(node)] ?? nodeKind(node).toUpperCase()} · DEPTH {node.depth}
        </span>
      </div>
      <h3 className="mt-2 text-[15px] font-semibold leading-snug text-txt" dir={dir(label)}>
        {label}
      </h3>
      {node.label_ar && isAr(node.label_ar) && enOf(node) && enOf(node) !== node.label_ar && (
        <p className="mt-0.5 text-[12.5px] text-muted">{enOf(node)}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-2 font-mono text-[10px] text-faint">
        {(node.count ?? node.signals) != null && <span>{(node.count ?? node.signals)?.toLocaleString()} signals</span>}
        {node.severity_avg != null && <span style={{ color: col }}>sev {node.severity_avg}</span>}
      </div>
      <div className="mt-3">
        <div className="mb-2 flex items-center gap-1.5 font-mono text-[10px] tracking-[0.14em] text-faint">
          <Quote className="h-3 w-3" />
          REAL CITIZEN SEGMENTS
        </div>
        {ev.length > 0 ? (
          <ul className="space-y-2">
            {ev.slice(0, 3).map((q, i) => (
              <li
                key={i}
                className="rounded-lg border border-border bg-cardhi px-3 py-2 text-[12.5px] leading-snug text-txt"
                dir={dir(q)}
              >
                {q}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[12px] text-muted">No sample segments at this node.</p>
        )}
      </div>
    </div>
  )
}

/* ===================================================== forecast panel */
function ForecastPanel({
  data,
  busy,
  metric,
  onMetric,
  fcData,
  lastHistT,
  escalations,
}: {
  data: ForecastResponse
  busy: boolean
  metric: 'volume' | 'sentiment'
  onMetric: (m: 'volume' | 'sentiment') => void
  fcData: Array<{ t: string; hist?: number; mean?: number; lo?: number; band?: number }>
  lastHistT?: string
  escalations: EscalationsResponse
}) {
  const esc = data.escalation
  const escalating = !!esc?.escalating
  const ratio = esc?.ratio
  const escList = escalations.escalations ?? escalations.items ?? []
  return (
    <div className="mt-4 rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[16px] font-semibold text-txt">
            <TrendingUp className="h-4 w-4 text-blue" />
            Forecast
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-[13px] text-muted">
            30-day {metric === 'volume' ? 'signal volume' : 'negative-sentiment share'} ·{' '}
            <MethodBadge method={data.method ?? data.source} />
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* metric toggle */}
          <div className="flex items-center gap-1 rounded-lg border border-border bg-bg p-1">
            {(['volume', 'sentiment'] as const).map((m) => (
              <button
                key={m}
                onClick={() => onMetric(m)}
                className={`rounded-md px-3 py-1 text-[12.5px] transition-colors ${
                  metric === m ? 'bg-cardhi font-medium text-txt' : 'text-muted hover:text-txt'
                }`}
              >
                {m === 'volume' ? 'Volume' : 'Sentiment'}
              </button>
            ))}
          </div>
          {/* escalation flag */}
          {esc && (
            <div
              className="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12px]"
              style={{
                borderColor: escalating ? `${AEGIS.danger}66` : `${AEGIS.good}55`,
                background: escalating ? `${AEGIS.danger}1a` : `${AEGIS.good}12`,
                color: escalating ? AEGIS.danger : AEGIS.good,
              }}
            >
              {escalating ? <TrendingUp className="h-3.5 w-3.5" /> : <Minus className="h-3.5 w-3.5" />}
              {escalating ? 'Escalating' : 'Stable'}
              {ratio != null && <span className="font-mono text-[10px] opacity-80">×{ratio.toFixed(2)}</span>}
            </div>
          )}
        </div>
      </div>

      {fcData.length > 0 ? (
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={fcData} margin={{ top: 10, right: 8, bottom: 0, left: -16 }}>
            <defs>
              <linearGradient id="fc-hist" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={AEGIS.blue} stopOpacity={0.32} />
                <stop offset="100%" stopColor={AEGIS.blue} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={AEGIS.soft} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="t"
              tick={{ fill: AEGIS.faint, fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              minTickGap={28}
              dy={8}
            />
            <YAxis tick={{ fill: AEGIS.faint, fontSize: 10 }} tickLine={false} axisLine={false} width={42} />
            <Tooltip
              cursor={{ stroke: AEGIS.blue, strokeWidth: 1, strokeDasharray: '3 3' }}
              contentStyle={{
                background: AEGIS.card,
                border: `1px solid ${AEGIS.border}`,
                borderRadius: 10,
                fontSize: 12,
              }}
              labelStyle={{ color: AEGIS.muted }}
              itemStyle={{ color: AEGIS.txt }}
            />
            {lastHistT && (
              <ReferenceLine x={lastHistT} stroke={AEGIS.faint} strokeDasharray="4 4" />
            )}
            {/* confidence band: stack invisible `lo` then translucent `band` */}
            <Area dataKey="lo" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} />
            <Area
              dataKey="band"
              stackId="band"
              stroke="none"
              fill={AEGIS.warn}
              fillOpacity={0.12}
              isAnimationActive={false}
              name="80% band"
            />
            {/* observed history */}
            <Area
              type="monotone"
              dataKey="hist"
              stroke={AEGIS.blue}
              strokeWidth={2.2}
              fill="url(#fc-hist)"
              connectNulls
              name="observed"
            />
            {/* forecast mean */}
            <Area
              type="monotone"
              dataKey="mean"
              stroke={escalating ? AEGIS.danger : AEGIS.good}
              strokeWidth={2.2}
              strokeDasharray="5 4"
              fill="none"
              connectNulls
              name="forecast"
            />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <div className="grid h-[200px] place-items-center text-[13px] text-muted">
          {busy ? (
            <span className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" /> Building the daily series…
            </span>
          ) : (
            'No history available to forecast this target.'
          )}
        </div>
      )}

      {/* escalation watchlist (national) */}
      {escList.length > 0 && (
        <div className="mt-4 border-t border-border pt-3">
          <div className="mb-2 font-mono text-[10px] tracking-[0.14em] text-faint">
            ESCALATION WATCHLIST · NEXT 14 DAYS
          </div>
          <div className="flex flex-wrap gap-2">
            {escList.slice(0, 6).map((e, i) => {
              const up = !!e.escalating || (e.growth ?? 0) > 0
              const label = e.label_ar && isAr(e.label_ar) ? e.label_ar : e.label || e.id || '—'
              return (
                <span
                  key={`${e.id ?? i}-${i}`}
                  className="flex items-center gap-1.5 rounded-lg border border-border bg-cardhi px-2.5 py-1.5 text-[12px] text-muted"
                  dir={dir(label)}
                >
                  {up ? (
                    <TrendingUp className="h-3 w-3 text-danger" />
                  ) : (
                    <TrendingDown className="h-3 w-3 text-good" />
                  )}
                  <span className="max-w-[160px] truncate text-txt">{label}</span>
                  {e.growth != null && (
                    <span className="font-mono text-[10px]" style={{ color: up ? AEGIS.danger : AEGIS.good }}>
                      {e.growth > 0 ? '+' : ''}
                      {(e.growth * 100).toFixed(0)}%
                    </span>
                  )}
                  {e.level && <span className="font-mono text-[9px] text-faint">{e.level}</span>}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {data.narration && (
        <p className="mt-3 border-t border-border pt-3 text-[12.5px] leading-snug text-muted" dir={dir(data.narration)}>
          {data.narration}
        </p>
      )}
    </div>
  )
}

/* ===================================================== ask panel */
function AskPanel({
  inputRef,
  question,
  setQuestion,
  asking,
  answer,
  onAsk,
  onFollowup,
  scopeLabel,
  debating,
  debateTurns,
  debateDossier,
  onDebate,
  onStopDebate,
}: {
  inputRef: React.RefObject<HTMLInputElement | null>
  question: string
  setQuestion: (s: string) => void
  asking: boolean
  answer: AskResponse | null
  onAsk: () => void
  onFollowup: (f: string) => void
  scopeLabel: string
  debating: boolean
  debateTurns: DebateEvent[]
  debateDossier: DebateEvent | null
  onDebate: () => void
  onStopDebate: () => void
}) {
  // Arabic-first answer block: when the answer is Arabic, render RTL, a touch
  // larger and roomier so it reads like a clean answer, not a dense mash-up.
  const answerAr = isAr(answer?.answer)
  return (
    <div className="mt-4 rounded-xl border border-border bg-card p-5">
      <div className="mb-3 flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] text-faint">
        <Search className="h-3.5 w-3.5" />
        GROUNDED Q&amp;A · ANSWERS COMPOSED FROM REAL voc360 FACTS
      </div>
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onAsk()
          }}
          dir={dir(question)}
          placeholder="Ask anything — e.g. why is Sanad rising? which problem will escalate next?"
          className="min-w-0 flex-1 rounded-lg border border-border bg-bg px-3.5 py-2.5 text-[13.5px] text-txt placeholder:text-faint focus:border-blue/60 focus:outline-none"
        />
        <button
          onClick={onAsk}
          disabled={asking || !question.trim()}
          className="flex shrink-0 items-center gap-2 rounded-lg bg-blue px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-50"
        >
          {asking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          Ask
        </button>
        {/* deep-research · agent debate over the current scope */}
        <button
          onClick={debating ? onStopDebate : onDebate}
          className="flex shrink-0 items-center gap-2 rounded-lg border border-[#A78BFA]/45 bg-[#A78BFA]/10 px-4 py-2.5 text-[13px] font-semibold text-[#A78BFA] transition-colors hover:bg-[#A78BFA]/20"
        >
          {debating ? <StopCircle className="h-4 w-4" /> : <MessagesSquare className="h-4 w-4" />}
          {debating ? 'إيقاف' : 'بحث عميق · نقاش الوكلاء'}
        </button>
      </div>

      {answer && (
        <div className="mt-4">
          <div className="rounded-lg border border-border bg-cardhi p-4">
            <div className="mb-2 flex flex-wrap items-center gap-2" dir={answerAr ? 'rtl' : 'ltr'}>
              {answer.intent && (
                <span className="rounded bg-soft px-1.5 py-0.5 font-mono text-[9px] tracking-[0.1em] text-faint">
                  {answer.intent}
                </span>
              )}
              {answer.grounded === false ? (
                <span className="rounded bg-soft px-1.5 py-0.5 font-mono text-[9px] text-warn">UNGROUNDED</span>
              ) : (
                <span className="rounded bg-soft px-1.5 py-0.5 font-mono text-[9px] text-good">GROUNDED</span>
              )}
              {answer.engine && (
                <>
                  {/* which model answered, Arabic-first */}
                  <span className="rounded bg-soft px-1.5 py-0.5 text-[10px] text-txt" dir="rtl">
                    {answer.engine === 'llm' ? 'النموذج المحلي' : 'محرك مبني على القواعد'}
                  </span>
                  <EngineBadge engine={answer.engine} />
                </>
              )}
            </div>
            <p
              className={
                answerAr
                  ? 'text-[15.5px] leading-[1.95] text-txt'
                  : 'text-[13.5px] leading-relaxed text-txt'
              }
              dir={dir(answer.answer)}
            >
              {answer.answer}
            </p>

            {/* facts — Arabic labels first when the answer is Arabic */}
            {answer.facts && answer.facts.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5" dir={answerAr ? 'rtl' : 'ltr'}>
                {answer.facts.map((f, i) => (
                  <span
                    key={i}
                    className="rounded-md border border-border bg-card px-2 py-1 text-[11.5px] text-muted"
                    dir={dir(`${f.label} ${f.value}`)}
                  >
                    <span className="text-faint">{f.label}: </span>
                    <span className="text-txt">{String(f.value)}</span>
                  </span>
                ))}
              </div>
            )}

            {/* citations */}
            {answer.citations && answer.citations.length > 0 && (
              <div className="mt-3 border-t border-border pt-3">
                <div className="mb-1.5 font-mono text-[9px] tracking-[0.12em] text-faint">CITATIONS</div>
                <ul className="space-y-1.5">
                  {answer.citations.map((c, i) => (
                    <li key={i} className="flex items-start gap-2 text-[11.5px]">
                      <span className="mt-0.5 shrink-0 rounded bg-soft px-1.5 py-0.5 font-mono text-[9px] text-faint">
                        {c.type}
                        {c.id ? `·${c.id}` : ''}
                      </span>
                      {(c.text ?? c.label) && (
                        <span className="text-muted" dir={dir(c.text ?? c.label)}>
                          {c.text ?? c.label}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* followups */}
          {answer.followups && answer.followups.length > 0 && (
            <div className="mt-3">
              <div className="mb-1.5 font-mono text-[9px] tracking-[0.12em] text-faint">FOLLOW-UP</div>
              <div className="flex flex-wrap gap-2">
                {answer.followups.map((f, i) => (
                  <button
                    key={i}
                    onClick={() => onFollowup(f)}
                    dir={dir(f)}
                    className="flex max-w-[420px] items-center gap-1.5 rounded-lg border border-border bg-cardhi px-3 py-1.5 text-left text-[12px] text-muted transition-colors hover:border-blue/50 hover:bg-soft hover:text-txt"
                  >
                    <CornerDownRight className="h-3.5 w-3.5 shrink-0 text-faint" />
                    <span className="truncate">{f}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------- deep-research agent debate */}
      {(debating || debateTurns.length > 0 || debateDossier) && (
        <div className="mt-4 rounded-lg border border-[#A78BFA]/30 bg-[#A78BFA]/5 p-4">
          <div className="mb-3 flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] text-faint">
            <MessagesSquare className="h-3.5 w-3.5 text-[#A78BFA]" />
            نقاش الوكلاء · AGENT DEBATE
            <span className="text-faint" dir={dir(scopeLabel)}>
              · {scopeLabel}
            </span>
            {debating && <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-[#A78BFA]" />}
          </div>

          {/* LightMem topics from the dossier */}
          {debateDossier && (
            <div className="mb-3">
              <div className="mb-1.5 flex items-center gap-1.5 text-[10px] text-faint">
                <Layers className="h-3 w-3" /> ذاكرة LightMem · {debateDossier.memory?.length ?? 0} محاور
                {debateDossier.model && <span className="ml-auto font-mono">{debateDossier.model}</span>}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(debateDossier.memory ?? []).map((m, i) => (
                  <span
                    key={i}
                    dir="rtl"
                    className="rounded-md border border-border bg-card px-1.5 py-0.5 text-[10px] text-muted"
                  >
                    «{m.topic}» · {m.count}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* streamed agent turns as RTL Arabic chat bubbles */}
          <div className="space-y-2">
            {debateTurns.map((turn, i) => {
              // deep-research dividers: cluster header + expert-panel phase
              if (turn.type === 'cluster') {
                return (
                  <div
                    key={i}
                    dir="rtl"
                    className="mt-3 flex items-center gap-2 border-t border-border/60 pt-2.5 text-[11.5px] font-semibold text-txt"
                  >
                    <span className="h-1.5 w-1.5 rounded-full" style={{ background: '#22D3EE' }} />
                    محور: {turn.label}
                    <span className="font-mono text-[9px] text-faint">
                      {turn.members} بلاغ · {turn.topics} موضوعات
                    </span>
                  </div>
                )
              }
              if (turn.type === 'phase') {
                return (
                  <div
                    key={i}
                    dir="rtl"
                    className="mt-3 flex items-center gap-2 border-t border-[#A78BFA]/40 pt-2.5 text-[11.5px] font-semibold text-[#A78BFA]"
                  >
                    <MessagesSquare className="h-3 w-3" /> {turn.label || 'لجنة الخبراء'}
                  </div>
                )
              }
              const col = ROLE_COLOR[turn.role ?? ''] ?? AEGIS.muted
              const isSynth = turn.type === 'synthesis'
              return (
                <div
                  key={i}
                  className={`rounded-lg border p-2.5 ${
                    isSynth ? 'border-[#A78BFA]/45 bg-[#A78BFA]/10' : 'border-border bg-card'
                  }`}
                >
                  <div className="mb-1 flex items-center gap-1.5">
                    <span className="grid h-4 w-4 place-items-center rounded-full" style={{ background: col }}>
                      {isSynth ? (
                        <Brain className="h-2.5 w-2.5 text-white" />
                      ) : (
                        <span className="h-1.5 w-1.5 rounded-full bg-white" />
                      )}
                    </span>
                    <span className="text-[11.5px] font-semibold text-txt">{turn.agent}</span>
                    {turn.engine && <span className="ml-auto font-mono text-[9px] text-faint">{turn.engine}</span>}
                  </div>
                  <div dir="rtl" className="text-[12.5px] leading-relaxed text-txt">
                    {turn.text}
                  </div>
                  {isSynth && typeof turn.confidence === 'number' && (
                    <div className="mt-1.5 font-mono text-[10px] text-faint">
                      الثقة {Math.round(turn.confidence * 100)}%{turn.verdict ? ` · ${turn.verdict}` : ''}
                    </div>
                  )}
                </div>
              )
            })}
            {debating && (
              <div className="flex items-center gap-2 py-1 text-[11px] text-muted">
                <Loader2 className="h-3 w-3 animate-spin" /> الوكلاء يتناقشون…
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/* ===================================================== small badges */
function EngineBadge({ engine }: { engine?: string }) {
  if (!engine) return null
  const isLlm = engine === 'llm'
  const isFallback = engine === 'fallback'
  // Service-name engines (validate, forecast, suggest, …) are real, not fallbacks.
  const label = isLlm ? 'LLM' : isFallback ? 'GROUNDED FALLBACK' : engine.toUpperCase()
  const color = isFallback ? AEGIS.muted : AEGIS.good
  return (
    <span
      className="rounded px-1.5 py-0.5 font-mono text-[9px] tracking-[0.1em]"
      style={{ background: AEGIS.soft, color }}
    >
      {label}
    </span>
  )
}

function MethodBadge({ method }: { method?: FcMethod }) {
  if (!method) return null
  const isTf = method.startsWith('timesfm')
  const empty = method === 'empty'
  return (
    <span
      className="rounded px-1.5 py-0.5 font-mono text-[9px] tracking-[0.1em]"
      style={{
        background: AEGIS.soft,
        color: empty ? AEGIS.faint : isTf ? AEGIS.good : AEGIS.warn,
      }}
    >
      {empty ? 'NO DATA' : isTf ? method.toUpperCase() : `${method.toUpperCase()} (STAT)`}
    </span>
  )
}
