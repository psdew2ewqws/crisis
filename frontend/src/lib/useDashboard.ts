// useDashboard.ts — T2 React hook: feed the EXISTING Dashboard (KpiCard /
// SignalVolume / DataTable) with REAL voc360 data instead of the static Zarqa
// demo fixtures in lib/data.ts.
//
// It consumes the typed voc2.ts client (getKpis / getSignalVolume / getSignals),
// all of which already degrade gracefully (each returns a well-formed fallback
// when the backend or a not-yet-built endpoint is unreachable). This hook adds:
//   1. load/refresh lifecycle (loading / error / source flags),
//   2. a deterministic mapping from the voc360 response shapes to the EXACT prop
//      types the existing components expect, so App.tsx can swap the fixtures
//      for `dash.kpis` / `dash.volume` / `dash.rows` with zero component edits.
//
// Component prop contracts mirrored here (from lib/data.ts):
//   KpiCard:      { kpi: Kpi }                  Kpi = {title,value,unit?,badge,trend,sub}
//   SignalVolume: reads Point[] = {t,v}         (chart consumes dataKey "t"/"v")
//   DataTable:    SignalRow[] = {entity,observation,source,severity,delta,z,time}
//
// Real voc360 columns only (the_data: source_type, service_id, governorate,
// text_clean, sentiment_label, severity, observed_at, rating). No Zarqa fixtures.
// Import-safe: this module never throws at import time, and every getter call is
// wrapped so a failed fetch yields fixtures-shaped fallbacks, never a crash.

import { useCallback, useEffect, useState } from 'react'
import {
  getKpis,
  getSignals,
  getSignalVolume,
  severityTone,
  type Kpi as VocKpi,
  type KpisResponse,
  type Signal,
  type SignalQuery,
  type SignalsResponse,
  type SignalVolumeResponse,
  type Tone as VocTone,
  type VolumePoint,
} from './voc2'

// --------------------------------------------------------------- prop types
// These are structurally identical to the exports in lib/data.ts so the
// existing components (which import their types from there) accept the mapped
// values verbatim. Re-declared locally to keep this hook self-contained and to
// avoid coupling to the demo-fixtures module that T2 is replacing.

// KpiCard's Tone (lib/data.ts): 'danger' | 'good' | 'warn' | 'neutral'.
export type Tone = 'danger' | 'good' | 'warn' | 'neutral'

export interface Kpi {
  title: string
  value: string
  unit?: string
  badge: { text: string; tone: Tone }
  trend: { text: string; dir: 'up' | 'down'; tone: Tone }
  sub: string
}

// SignalVolume chart point: { t, v } (dataKey "t" on XAxis, "v" on the Area).
export interface Point {
  t: string
  v: number
}

// DataTable row severity (lib/data.ts): 'Critical' | 'Elevated' | 'Nominal'.
export type RowSeverity = 'Critical' | 'Elevated' | 'Nominal'

export interface SignalRow {
  entity: string
  observation: string
  source: string
  severity: RowSeverity
  delta: string
  z: string
  time: string
}

// ------------------------------------------------------------------ mapping
// voc2.ts Tone has an extra 'neutral'; both the KpiCard Tone and voc2 Tone use
// the same string literals, so this is an identity narrowing kept explicit for
// safety against future drift.
const toCardTone = (t: VocTone): Tone =>
  t === 'danger' || t === 'good' || t === 'warn' ? t : 'neutral'

// voc2 KPI → KpiCard Kpi. The voc2 Kpi already carries title/value/unit/badge/
// trend/sub; we only translate the tone enum and drop the `key` field the card
// doesn't read. App.tsx can still use voc2's `key` for React keys via mapKpis.
const mapKpi = (k: VocKpi): Kpi => ({
  title: k.title,
  value: k.value,
  unit: k.unit,
  badge: { text: k.badge.text, tone: toCardTone(k.badge.tone) },
  trend: { text: k.trend.text, dir: k.trend.dir, tone: toCardTone(k.trend.tone) },
  sub: k.sub,
})

// voc2 VolumePoint → chart Point. The chart only reads { t, v }; severity splits
// (critical/high/negative) are preserved on the source series but not needed by
// the existing single-Area component, so we project down to { t, v }.
const mapVolumePoint = (p: VolumePoint): Point => ({ t: formatBucket(p.t), v: p.v })

// the_data.severity (low/medium/high/critical/null) → DataTable's 3-band enum.
// high+critical → Critical, medium → Elevated, low/null(app_reviews) → Nominal.
// This mirrors voc2.severityTone (danger/warn/good/neutral) so colours agree.
const rowSeverityFor = (s: Signal['severity']): RowSeverity => {
  switch (severityTone(s)) {
    case 'danger':
      return 'Critical'
    case 'warn':
      return 'Elevated'
    default:
      return 'Nominal' // 'good' (low) and 'neutral' (null app_reviews)
  }
}

// the_data row → DataTable SignalRow. Real columns only:
//   entity      ← service_id (fallback governorate, then record_id)
//   observation ← text_clean / text (trimmed; Arabic flows through untouched)
//   source      ← source_type
//   severity    ← severity band (above)
//   delta       ← rating shown as ★N when present, else sentiment glyph
//   z           ← confidence (0..1) to 2dp, or '—'
//   time        ← observed_at as HH:MM (local), or '—'
const mapSignalRow = (s: Signal): SignalRow => {
  const body = (s.text_clean ?? s.text ?? '').trim()
  return {
    entity: s.service_id ?? s.governorate ?? s.record_id,
    observation: body ? truncate(body, 80) : '(no text)',
    source: s.source_type,
    severity: rowSeverityFor(s.severity),
    delta: deltaLabel(s),
    z: s.confidence != null ? s.confidence.toFixed(2) : '—',
    time: formatTime(s.observed_at),
  }
}

// --------------------------------------------------------------- formatters
// Rating drives the Δ column when present (app_reviews); otherwise fall back to
// a compact sentiment glyph so the cell is never blank.
function deltaLabel(s: Signal): string {
  if (s.rating != null && Number.isFinite(s.rating)) return `★${s.rating}`
  const sl = (s.sentiment_label ?? '').toLowerCase()
  if (sl.startsWith('positive')) return '▲'
  if (sl.startsWith('negative') || sl.startsWith('high_severity')) return '▼'
  return '—'
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

// Bucket labels from the backend may be ISO datetimes (date_trunc) or already
// short labels; render datetimes as a short, locale-stable axis tick.
function formatBucket(t: string): string {
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t // already a label (e.g. "08:00")
  // Hourly granularity → HH:00; daily/weekly → MM/DD. Heuristic on minutes.
  return d.getMinutes() === 0 && d.getHours() !== 0
    ? `${pad(d.getHours())}:00`
    : `${pad(d.getMonth() + 1)}/${pad(d.getDate())}`
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

// ------------------------------------------------------------------ public
export interface DashboardData {
  // Mapped, component-ready props (drop straight into the existing components):
  kpis: Kpi[] // → KpiCard[]
  volume: Point[] // → SignalVolume chart data
  rows: SignalRow[] // → DataTable rows

  // Raw voc360 responses (for pages that want richer fields than the fixtures):
  raw: {
    kpis: KpisResponse | null
    volume: SignalVolumeResponse | null
    signals: SignalsResponse | null
  }

  // Provenance + lifecycle so the UI can badge honestly and show spinners.
  source: 'voc360' | 'fallback' // 'voc360' only when every getter returned live data
  total: number // total matched signals (the_data) for the active filter
  loading: boolean
  error: string | null
  refresh: () => void
}

export interface UseDashboardOptions {
  caseId?: string // forwarded to getKpis / getSignalVolume (case scoping)
  serviceId?: string // forwarded to volume + signal queries
  bucket?: SignalVolumeResponse['bucket'] // chart granularity
  rowLimit?: number // rows pulled for the DataTable feed
  signalQuery?: SignalQuery // extra signal filters (severity/source/q/…)
}

const DEFAULT_ROW_LIMIT = 25

// Stable empties so the hook returns valid component props even before the first
// fetch resolves (and on total failure). Never the Zarqa fixtures.
const EMPTY: Pick<DashboardData, 'kpis' | 'volume' | 'rows' | 'total'> = {
  kpis: [],
  volume: [],
  rows: [],
  total: 0,
}

/**
 * useDashboard — load real voc360 KPIs, signal-volume series and the recent
 * signal feed, and expose them already mapped to the existing Dashboard
 * components' prop shapes.
 *
 * Usage in App.tsx (replacing the `import { kpis } from './lib/data'` fixtures):
 *
 *   const dash = useDashboard({ rowLimit: 25 })
 *   ...
 *   {dash.kpis.map((k) => <KpiCard key={k.title} kpi={k} />)}
 *   <SignalVolume data={dash.volume} />          // pass data instead of fixture
 *   <DataTable rows={dash.rows} onRun={...} />    // pass rows instead of fixture
 *
 * (SignalVolume/DataTable currently read fixtures internally; the minimal T2
 * edit is to accept an optional `data`/`rows` prop and fall back to the fixture
 * when omitted — these mapped arrays satisfy those props exactly.)
 */
export function useDashboard(opts: UseDashboardOptions = {}): DashboardData {
  const {
    caseId,
    serviceId,
    bucket,
    rowLimit = DEFAULT_ROW_LIMIT,
    signalQuery,
  } = opts

  const [state, setState] = useState<
    Pick<DashboardData, 'kpis' | 'volume' | 'rows' | 'total' | 'raw' | 'source'>
  >({
    ...EMPTY,
    raw: { kpis: null, volume: null, signals: null },
    source: 'fallback',
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Bump to force a re-fetch without changing inputs.
  const [nonce, setNonce] = useState(0)
  const refresh = useCallback(() => setNonce((n) => n + 1), [])

  // Serialize the signal filter so it can sit in the effect deps without
  // re-running on every render due to object identity.
  const signalQueryKey = JSON.stringify(signalQuery ?? {})

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)

    const sigQuery: SignalQuery = {
      limit: rowLimit,
      ...(serviceId ? { service_id: serviceId } : {}),
      ...(signalQuery ?? {}),
    }

    Promise.all([
      getKpis(caseId),
      getSignalVolume({ case: caseId, service_id: serviceId, bucket }),
      getSignals(sigQuery),
    ])
      .then(([kRes, vRes, sRes]) => {
        if (!alive) return
        const live =
          kRes.source === 'voc360' &&
          vRes.source === 'voc360' &&
          (sRes.total > 0 || sRes.signals.length > 0)
        setState({
          kpis: kRes.kpis.map(mapKpi),
          volume: vRes.series.map(mapVolumePoint),
          rows: sRes.signals.map(mapSignalRow),
          total: sRes.total,
          raw: { kpis: kRes, volume: vRes, signals: sRes },
          source: live ? 'voc360' : 'fallback',
        })
      })
      .catch((e: unknown) => {
        // The voc2 getters swallow network errors already; this only fires on an
        // unexpected mapping fault. Keep the dashboard mounted with empties.
        if (!alive) return
        setError(e instanceof Error ? e.message : String(e))
        setState((s) => ({ ...s, ...EMPTY, source: 'fallback' }))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })

    return () => {
      alive = false
    }
    // signalQueryKey captures `signalQuery`; eslint can't see through the JSON.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, serviceId, bucket, rowLimit, signalQueryKey, nonce])

  return {
    kpis: state.kpis,
    volume: state.volume,
    rows: state.rows,
    raw: state.raw,
    source: state.source,
    total: state.total,
    loading,
    error,
    refresh,
  }
}

// Convenience re-exports of the pure mappers so pages/tests can transform a
// voc360 payload without mounting the hook.
export { mapKpi, mapVolumePoint, mapSignalRow, rowSeverityFor }

export default useDashboard
