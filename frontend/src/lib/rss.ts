// rss.ts — typed client for the live Middle East crisis-signal RSS feed.
// Backed by the in-memory aggregator in backend/app/news_rss.py, served by
// api_rss.py at /api/rss/{signals,sources,stats}. Same BASE + graceful-fallback
// contract as lib/voc2.ts: a getter never throws — it returns an empty payload
// so the map stays mounted when the backend is unreachable.

const BASE =
  (import.meta.env.VITE_API as string | undefined) ??
  (typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'http://127.0.0.1:8000')

async function jf<T>(path: string, fallback: T): Promise<T> {
  try {
    const r = await fetch(BASE + path)
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

// ── Types (mirror the backend CrisisSignal pydantic model) ──────────────────
export type RssCategory = 'conflict' | 'disaster' | 'health' | 'political' | 'economic' | 'other'
export type RssSeverity = 'critical' | 'high' | 'medium' | 'low'

export interface RssSignal {
  id: string
  title: string
  summary: string
  source: string
  link: string
  published: string // ISO 8601
  country: string | null
  lat: number | null
  lng: number | null
  category: RssCategory
  severity: RssSeverity
}

export interface RssSignalsResponse {
  signals: RssSignal[]
  last_fetch: string | null
  source_count: number
  total_count: number
  error?: string
}

export interface RssSource {
  name: string
  url: string
  status: 'ok' | 'error' | 'pending'
  last_fetch: string | null
  item_count: number
}

export interface RssSourcesResponse {
  sources: RssSource[]
  error?: string
}

export interface RssStatsResponse {
  total_signals: number
  by_country: Record<string, number>
  by_category: Record<string, number>
  by_severity: Record<string, number>
  error?: string
}

export interface RssSignalQuery {
  country?: string
  category?: string
  severity?: string
  limit?: number
}

// ── Severity → AEGIS-aligned marker colour + radius ─────────────────────────
export const SEVERITY_COLOR: Record<RssSeverity, string> = {
  critical: '#ef4444', // danger red
  high:     '#f97316', // warn orange
  medium:   '#eab308', // warn yellow
  low:      '#3b82f6', // neutral blue
}

export const SEVERITY_RADIUS: Record<RssSeverity, number> = {
  critical: 10, high: 8, medium: 6, low: 5,
}

export const CATEGORIES: RssCategory[] = [
  'conflict', 'disaster', 'health', 'political', 'economic', 'other',
]
export const SEVERITIES: RssSeverity[] = ['critical', 'high', 'medium', 'low']

const EMPTY_SIGNALS: RssSignalsResponse = {
  signals: [], last_fetch: null, source_count: 0, total_count: 0,
}
const EMPTY_SOURCES: RssSourcesResponse = { sources: [] }
const EMPTY_STATS: RssStatsResponse = {
  total_signals: 0, by_country: {}, by_category: {}, by_severity: {},
}

// ── Getters ─────────────────────────────────────────────────────────────────
export const getRssSignals = (params: RssSignalQuery = {}): Promise<RssSignalsResponse> =>
  jf<RssSignalsResponse>(
    `/api/rss/signals${qs(params as Record<string, string | number | undefined>)}`,
    EMPTY_SIGNALS,
  )

export const getRssSources = (): Promise<RssSourcesResponse> =>
  jf<RssSourcesResponse>('/api/rss/sources', EMPTY_SOURCES)

export const getRssStats = (): Promise<RssStatsResponse> =>
  jf<RssStatsResponse>('/api/rss/stats', EMPTY_STATS)

// Relative-time formatter shared by the map + feed sidebar.
export function relTime(iso: string | null): string {
  if (!iso) return ''
  const ms = new Date(iso).getTime()
  if (Number.isNaN(ms)) return ''
  const s = (Date.now() - ms) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}
