// SignalsPage — the SIGNAL / data-source layer of voc360 (the_data, 22,882 rows).
//
// Real voc360 columns only: record_id, source_type, source_platform, service_id,
// governorate, text/text_clean (Arabic, RTL), observed_at, rating, sentiment_label,
// severity. Filters by service / severity / source + free-text search, with paging.
//
// Import-safe: it fetches /api/signals directly and degrades to a graceful
// empty state. AEGIS dark-console tokens throughout.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertTriangle,
  RotateCw,
  Radio,
} from 'lucide-react'

// ── voc360 row shape (the_data) ────────────────────────────────────────────
export interface Signal {
  record_id: string | number
  source_type: string | null
  source_platform?: string | null
  service_id: string | null
  governorate?: string | null
  text?: string | null
  text_clean?: string | null
  observed_at?: string | null
  rating?: number | null
  sentiment_label?: string | null
  severity?: string | null
}

interface SignalsResponse {
  rows: Signal[]
  total: number
  // optional facet lists the API may return; we degrade to local distincts.
  services?: string[]
  sources?: string[]
}

interface Query {
  service: string
  severity: string
  source: string
  search: string
  page: number
}

const PAGE_SIZE = 25
const ALL = '__all__'

// ── severity → AEGIS tone (real voc360 buckets: low/medium/high/critical) ──
const SEV_DOT: Record<string, string> = {
  critical: 'bg-danger',
  high: 'bg-danger',
  medium: 'bg-warn',
  low: 'bg-good',
}
const SEV_TEXT: Record<string, string> = {
  critical: 'text-danger',
  high: 'text-danger',
  medium: 'text-warn',
  low: 'text-good',
}
function sevKey(s?: string | null): string {
  return (s ?? '').trim().toLowerCase()
}

const SENT_TONE: Record<string, string> = {
  negative: 'text-danger',
  high_severity_complaint: 'text-danger',
  positive: 'text-good',
}
function sentTone(s?: string | null): string {
  return SENT_TONE[sevKey(s)] ?? 'text-muted'
}

const SEVERITY_OPTIONS = ['critical', 'high', 'medium', 'low']

// ── resilient data loader ──────────────────────────────────────────────────
// Fetches /api/signals; HTTP/network failures throw and surface the error UI.
const API_BASE =
  (import.meta as { env?: Record<string, string> }).env?.VITE_API ?? 'http://127.0.0.1:8000'

async function loadSignals(q: Query): Promise<SignalsResponse> {
  const params: Record<string, string> = { limit: String(PAGE_SIZE), offset: String(q.page * PAGE_SIZE) }
  if (q.service !== ALL) params.service_id = q.service
  if (q.severity !== ALL) params.severity = q.severity
  if (q.source !== ALL) params.source_type = q.source
  if (q.search.trim()) params.q = q.search.trim()

  const qs = new URLSearchParams(params).toString()
  const r = await fetch(`${API_BASE}/api/signals?${qs}`)
  if (!r.ok) throw new Error(`/api/signals → ${r.status}`)
  return normalize(await r.json())
}

// Accept a few plausible response envelopes and coerce to {rows,total,…}.
function normalize(res: unknown): SignalsResponse {
  if (Array.isArray(res)) return { rows: res as Signal[], total: (res as Signal[]).length }
  const o = (res ?? {}) as Record<string, unknown>
  const rows = (o.rows ?? o.signals ?? o.data ?? []) as Signal[]
  const total = Number(o.total ?? o.count ?? rows.length) || rows.length
  const services = Array.isArray(o.services) ? (o.services as string[]) : undefined
  const sources = Array.isArray(o.sources) ? (o.sources as string[]) : undefined
  return { rows, total, services, sources }
}

// ── small UI atoms ─────────────────────────────────────────────────────────
function Select({
  value,
  onChange,
  options,
  allLabel,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  allLabel: string
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-border bg-bg px-3 py-2 text-[13px] text-txt outline-none transition-colors hover:bg-soft focus:border-blue"
    >
      <option value={ALL}>{allLabel}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

function isArabic(s: string): boolean {
  return /[؀-ۿ]/.test(s)
}

function timeAgo(iso?: string | null): string {
  if (!iso) return '—'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return String(iso)
  const d = Date.now() - t
  const m = Math.round(d / 60000)
  if (m < 1) return 'now'
  if (m < 60) return `${m}m`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h`
  return `${Math.round(h / 24)}d`
}

// ── page ───────────────────────────────────────────────────────────────────
export default function SignalsPage() {
  const [q, setQ] = useState<Query>({ service: ALL, severity: ALL, source: ALL, search: '', page: 0 })
  const [searchInput, setSearchInput] = useState('')
  const [data, setData] = useState<SignalsResponse>({ rows: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const reqId = useRef(0)

  const fetchPage = useCallback(async (query: Query) => {
    const id = ++reqId.current
    setLoading(true)
    setErr(null)
    try {
      const res = await loadSignals(query)
      if (id === reqId.current) setData(res)
    } catch (e) {
      if (id === reqId.current) {
        setErr(e instanceof Error ? e.message : 'Failed to load signals')
        setData({ rows: [], total: 0 })
      }
    } finally {
      if (id === reqId.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPage(q)
  }, [q, fetchPage])

  // debounce free-text search → resets to first page
  useEffect(() => {
    const t = setTimeout(() => {
      setQ((p) => (p.search === searchInput ? p : { ...p, search: searchInput, page: 0 }))
    }, 300)
    return () => clearTimeout(t)
  }, [searchInput])

  // facet options: prefer API-provided lists, else derive from current rows.
  const serviceOptions = useMemo(() => {
    const src = data.services ?? Array.from(new Set(data.rows.map((r) => r.service_id).filter(Boolean) as string[]))
    return src.sort().map((s) => ({ value: s, label: s }))
  }, [data])

  const sourceOptions = useMemo(() => {
    const src = data.sources ?? Array.from(new Set(data.rows.map((r) => r.source_type).filter(Boolean) as string[]))
    return src.sort().map((s) => ({ value: s, label: s }))
  }, [data])

  const setFilter = (patch: Partial<Query>) => setQ((p) => ({ ...p, ...patch, page: 0 }))

  const total = data.total
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const from = total === 0 ? 0 : q.page * PAGE_SIZE + 1
  const to = Math.min(total, q.page * PAGE_SIZE + data.rows.length)

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[1340px] px-8 py-7">
        {/* header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="flex items-center gap-2.5 text-[28px] font-semibold tracking-tight text-txt">
              <Radio className="h-6 w-6 text-blue" />
              Signals
            </h1>
            <p className="mt-1.5 text-[14px] text-muted">
              Voice-of-Customer signal layer · <span className="font-mono text-faint">the_data</span> ·{' '}
              {loading && !data.rows.length ? '…' : total.toLocaleString()} records
            </p>
          </div>
          <button
            onClick={() => fetchPage(q)}
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-[13px] text-muted transition-colors hover:bg-soft hover:text-txt"
          >
            <RotateCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* filter bar */}
        <div className="mt-6 flex flex-wrap items-center gap-2.5">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search signal text…"
              dir="auto"
              className="w-full rounded-lg border border-border bg-bg py-2 pl-9 pr-3 text-[13px] text-txt outline-none transition-colors placeholder:text-faint hover:bg-soft focus:border-blue"
            />
          </div>
          <Select
            value={q.service}
            onChange={(v) => setFilter({ service: v })}
            options={serviceOptions}
            allLabel="All services"
          />
          <Select
            value={q.severity}
            onChange={(v) => setFilter({ severity: v })}
            options={SEVERITY_OPTIONS.map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))}
            allLabel="All severity"
          />
          <Select
            value={q.source}
            onChange={(v) => setFilter({ source: v })}
            options={sourceOptions}
            allLabel="All sources"
          />
        </div>

        {/* table */}
        <div className="mt-4 overflow-hidden rounded-xl border border-border bg-card">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[11px] font-medium tracking-[0.08em] text-faint">
                <th className="px-5 py-3 font-medium">SEVERITY</th>
                <th className="py-3 font-medium">SIGNAL</th>
                <th className="py-3 font-medium">SERVICE</th>
                <th className="py-3 font-medium">SOURCE</th>
                <th className="py-3 font-medium">SENTIMENT</th>
                <th className="px-5 py-3 text-right font-medium">OBSERVED</th>
              </tr>
            </thead>
            <tbody>
              {err && (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center">
                    <div className="mx-auto flex max-w-md flex-col items-center gap-2 text-muted">
                      <AlertTriangle className="h-6 w-6 text-warn" />
                      <div className="text-[14px] text-txt">Could not load signals</div>
                      <div className="font-mono text-[12px] text-faint">{err}</div>
                      <button
                        onClick={() => fetchPage(q)}
                        className="mt-2 rounded-lg border border-border px-3 py-1.5 text-[13px] text-muted transition-colors hover:bg-soft hover:text-txt"
                      >
                        Retry
                      </button>
                    </div>
                  </td>
                </tr>
              )}

              {!err && loading && data.rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-muted">
                    <Loader2 className="mx-auto h-5 w-5 animate-spin text-blue" />
                    <div className="mt-2 text-[13px]">Loading voc360 signals…</div>
                  </td>
                </tr>
              )}

              {!err && !loading && data.rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-muted">
                    <Radio className="mx-auto h-6 w-6 text-faint" />
                    <div className="mt-2 text-[14px] text-txt">No signals match these filters</div>
                    <div className="mt-1 text-[13px] text-faint">Try clearing a filter or the search term.</div>
                  </td>
                </tr>
              )}

              {!err &&
                data.rows.map((s) => {
                  const sev = sevKey(s.severity)
                  const body = (s.text_clean || s.text || '').trim()
                  const ar = isArabic(body)
                  return (
                    <tr
                      key={String(s.record_id)}
                      className="border-t border-border/70 transition-colors hover:bg-soft/50"
                    >
                      <td className="px-5 py-3.5 align-top">
                        <span className={`inline-flex items-center gap-1.5 text-[13px] ${SEV_TEXT[sev] ?? 'text-muted'}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${SEV_DOT[sev] ?? 'bg-faint'}`} />
                          {s.severity ? sev[0].toUpperCase() + sev.slice(1) : '—'}
                        </span>
                      </td>
                      <td className="max-w-[480px] py-3.5 align-top">
                        <div
                          dir={ar ? 'rtl' : 'ltr'}
                          className={`line-clamp-2 text-[13.5px] text-txt ${ar ? 'text-right font-sans' : ''}`}
                        >
                          {body || <span className="text-faint">—</span>}
                        </div>
                        <span className="mt-0.5 block font-mono text-[11px] text-faint">
                          #{String(s.record_id)}
                          {s.source_platform ? ` · ${s.source_platform}` : ''}
                          {typeof s.rating === 'number' ? ` · ★${s.rating}` : ''}
                        </span>
                      </td>
                      <td className="py-3.5 align-top">
                        <span dir="auto" className="text-[13px] text-txt">
                          {s.service_id ?? <span className="text-faint">—</span>}
                        </span>
                        {s.governorate && (
                          <span dir="auto" className="mt-0.5 block text-[12px] text-muted">
                            {s.governorate}
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 align-top">
                        <span dir="auto" className="font-mono text-[12px] text-muted">
                          {s.source_type ?? '—'}
                        </span>
                      </td>
                      <td className="py-3.5 align-top">
                        <span className={`text-[12.5px] ${sentTone(s.sentiment_label)}`}>
                          {s.sentiment_label ? s.sentiment_label.replace(/_/g, ' ') : '—'}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-right align-top">
                        <span className="font-mono text-[13px] tnum text-muted">{timeAgo(s.observed_at)}</span>
                      </td>
                    </tr>
                  )
                })}
            </tbody>
          </table>

          {/* footer / pagination */}
          <div className="flex items-center justify-between border-t border-border px-5 py-3">
            <span className="text-[12.5px] text-muted">
              {total === 0 ? 'No results' : `${from.toLocaleString()}–${to.toLocaleString()} of ${total.toLocaleString()}`}
            </span>
            <div className="flex items-center gap-2">
              <span className="text-[12.5px] text-faint">
                Page {q.page + 1} / {pageCount}
              </span>
              <button
                disabled={q.page === 0 || loading}
                onClick={() => setQ((p) => ({ ...p, page: Math.max(0, p.page - 1) }))}
                className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-muted transition-colors hover:bg-soft hover:text-txt disabled:cursor-not-allowed disabled:opacity-40"
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                disabled={q.page + 1 >= pageCount || loading}
                onClick={() => setQ((p) => ({ ...p, page: p.page + 1 }))}
                className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-muted transition-colors hover:bg-soft hover:text-txt disabled:cursor-not-allowed disabled:opacity-40"
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
