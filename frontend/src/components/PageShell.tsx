// PageShell — shared T2 scaffolding for the AEGIS console pages (Signals, Root
// Cause, Solutions, Simulation, Decisions). Exposes three reusable primitives,
// all styled against the existing AEGIS Tailwind tokens (see frontend/
// tailwind.config) and matching the layout already used by RootCausePage:
//
//   <PageShell>   page chrome — title, subtitle, optional meta + action buttons,
//                 scroll container, max-width gutter, and slots for an inline
//                 error / loading state.
//   <FilterBar>   a row of segmented filter pills (range / facet selectors) plus
//                 an optional free-text search box and right-aligned children.
//   <DataGrid>    a generic, column-driven table over REAL voc360 rows. Columns
//                 are described declaratively so each console page can project
//                 only the voc360 fields it actually has.
//
// Design notes
// ------------
// - Tokens only: bg/sidebar/card/cardhi/border/soft/txt/muted/faint/blue/bluehi/
//   danger/good/warn, plus Geist / Geist Mono via font-mono. No hard-coded hexes
//   except inside the small SEV map (kept in sync with LiveGraph / RootCausePage).
// - Import-safe: this file imports only React + lucide-react (already a project
//   dependency) and degrades gracefully — every optional prop has a fallback, the
//   Arabic/RTL helpers are local, and DataGrid copes with missing columns, empty
//   data, null cells, and loading without throwing.
// - Real voc360 columns only: the helpers + types here describe and render the
//   actual columns the backend returns (record_id, source_type, service_id,
//   governorate, severity, sentiment_label, text/text_clean, cluster_id,
//   member_count, severity_avg, …). No demo/Zarqa fixtures are referenced.

import {
  type ReactNode,
  type CSSProperties,
  type Key,
  useMemo,
} from 'react'
import {
  Loader2,
  AlertTriangle,
  Database,
  Search,
  Inbox,
  ChevronUp,
  ChevronDown,
} from 'lucide-react'

/* ----------------------------------------------------------------- tokens */

// Severity palette — kept identical to LiveGraph / RootCausePage so colours read
// consistently across the graph and the console pages.
export const SEV = {
  alert: '#F04359', // danger
  warn: '#FBBF24', // warn
  calm: '#34D399', // good
  neutral: '#8B8D96', // muted
} as const

export type SevKey = keyof typeof SEV

// Arabic detection / direction helpers (voc360 text is Arabic; labels mixed).
const AR_RE = /[؀-ۿݐ-ݿ]/
export const isAr = (s: unknown): boolean => typeof s === 'string' && AR_RE.test(s)
export const dirOf = (s: unknown): 'rtl' | 'ltr' => (isAr(s) ? 'rtl' : 'ltr')

// Map a voc360 severity (string label or 0..1 average) to a palette key.
// Accepts: 'critical'|'high'|'medium'|'low' (the_data.severity) OR a numeric
// severity_avg in [0,1] (ril_problem_clusters.severity_avg).
export function sevKey(sev: unknown): SevKey {
  if (typeof sev === 'number' && Number.isFinite(sev)) {
    if (sev >= 0.5) return 'alert'
    if (sev >= 0.3) return 'warn'
    if (sev > 0) return 'calm'
    return 'neutral'
  }
  const s = String(sev ?? '').trim().toLowerCase()
  if (s === 'critical' || s === 'high' || s === 'high_severity_complaint') return 'alert'
  if (s === 'medium') return 'warn'
  if (s === 'low') return 'calm'
  return 'neutral'
}
export const sevColor = (sev: unknown): string => SEV[sevKey(sev)]

// Sentiment → palette key (the_data.sentiment_label).
export function sentimentKey(label: unknown): SevKey {
  const s = String(label ?? '').trim().toLowerCase()
  if (s.includes('high_severity') || s.startsWith('negative')) return 'alert'
  if (s.startsWith('positive')) return 'calm'
  if (s.startsWith('neutral')) return 'neutral'
  return 'neutral'
}

// Number formatting that never throws on null/NaN.
export function fmtNum(v: unknown): string {
  const n = typeof v === 'number' ? v : Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString()
}

/* ============================================================== PageShell */

export interface PageShellMeta {
  icon?: ReactNode
  text: ReactNode
}

export interface PageShellProps {
  title: string
  subtitle?: ReactNode
  // Small line under the subtitle (e.g. "20 clusters · 903 segments"); rendered
  // with a Database glyph by default to echo RootCausePage's "from voc360" note.
  meta?: PageShellMeta | ReactNode
  // Right-aligned action buttons (Refresh, Open graph, Run…). Caller styles them.
  actions?: ReactNode
  // Inline async states. When `loading` is true and there are no children yet a
  // centred spinner is shown; pass `loadingLabel` to customise it.
  loading?: boolean
  loadingLabel?: string
  // Error string — rendered in the danger banner used across the console.
  error?: string | null
  // Width of the centred gutter; matches RootCausePage's 1340px by default.
  maxWidth?: number
  children?: ReactNode
}

function isMeta(x: unknown): x is PageShellMeta {
  return !!x && typeof x === 'object' && 'text' in (x as Record<string, unknown>)
}

export default function PageShell({
  title,
  subtitle,
  meta,
  actions,
  loading = false,
  loadingLabel = 'Loading…',
  error = null,
  maxWidth = 1340,
  children,
}: PageShellProps) {
  const hasChildren =
    children != null && (!Array.isArray(children) || children.length > 0)

  return (
    <div className="flex-1 overflow-y-auto bg-bg">
      <div className="mx-auto px-8 py-7" style={{ maxWidth }}>
        {/* header */}
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-[28px] font-semibold tracking-tight text-txt">{title}</h1>
            {subtitle != null && (
              <p className="mt-1.5 text-[14px] leading-snug text-muted">{subtitle}</p>
            )}
            {meta != null && (
              <p className="mt-1.5 flex items-center gap-2 text-[13px] text-faint">
                {isMeta(meta) ? (
                  <>
                    <span className="grid place-items-center text-muted">
                      {meta.icon ?? <Database className="h-3.5 w-3.5" />}
                    </span>
                    <span>{meta.text}</span>
                  </>
                ) : (
                  meta
                )}
              </p>
            )}
          </div>
          {actions != null && (
            <div className="flex shrink-0 items-center gap-2">{actions}</div>
          )}
        </div>

        {/* error banner — shared danger style */}
        {error && (
          <div className="mt-6 flex items-center gap-2 rounded-lg border border-danger/40 bg-card px-4 py-3 text-[13px] text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span dir={dirOf(error)}>{error}</span>
          </div>
        )}

        {/* body */}
        {hasChildren ? (
          <div className="mt-6">{children}</div>
        ) : (
          !error &&
          loading && (
            <div className="mt-10 flex items-center justify-center gap-2 text-[13px] text-muted">
              <Loader2 className="h-4 w-4 animate-spin" />
              {loadingLabel}
            </div>
          )
        )}
      </div>
    </div>
  )
}

/* =============================================================== FilterBar */

export interface FilterOption {
  // Stable value passed back to onChange; `label` is what the user sees.
  value: string
  label?: ReactNode
  // Optional small count shown to the right of the label (e.g. row counts).
  count?: number | string
}

export interface FilterGroup {
  id: string
  label?: string
  options: FilterOption[]
  value?: string
  onChange?: (value: string) => void
}

export interface FilterBarProps {
  // Segmented pill groups (each a single-select). Empty/undefined → omitted.
  groups?: FilterGroup[]
  // Optional free-text search box.
  search?: {
    value: string
    onChange: (value: string) => void
    placeholder?: string
  }
  // Right-aligned extra controls (sort menu, density toggle, export…).
  children?: ReactNode
}

export function FilterBar({ groups = [], search, children }: FilterBarProps) {
  const hasGroups = groups.some((g) => g.options.length > 0)
  if (!hasGroups && !search && !children) return null

  return (
    <div className="flex flex-wrap items-center gap-3">
      {groups.map((g) =>
        g.options.length === 0 ? null : (
          <div key={g.id} className="flex items-center gap-2">
            {g.label && (
              <span className="font-mono text-[10px] tracking-[0.12em] text-faint">
                {g.label}
              </span>
            )}
            <div className="flex items-center gap-1 rounded-lg border border-border bg-bg p-1">
              {g.options.map((opt) => {
                const on = g.value === opt.value
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => g.onChange?.(opt.value)}
                    className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-[12.5px] transition-colors ${
                      on
                        ? 'bg-cardhi font-medium text-txt'
                        : 'text-muted hover:text-txt'
                    }`}
                  >
                    {opt.label ?? opt.value}
                    {opt.count != null && (
                      <span
                        className={`font-mono text-[11px] tnum ${
                          on ? 'text-muted' : 'text-faint'
                        }`}
                      >
                        {opt.count}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        ),
      )}

      {search && (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
          <input
            value={search.value}
            onChange={(e) => search.onChange(e.target.value)}
            placeholder={search.placeholder ?? 'Search…'}
            dir={dirOf(search.value)}
            className="h-9 w-[260px] rounded-lg border border-border bg-card pl-9 pr-3 text-[13px] text-txt outline-none transition-colors placeholder:text-faint focus:border-blue/60"
          />
        </div>
      )}

      {children && <div className="ml-auto flex items-center gap-2">{children}</div>}
    </div>
  )
}

/* ================================================================ DataGrid */

export interface DataGridColumn<Row> {
  // Stable key; also used as the default accessor (Row[key]) when no `accessor`.
  key: string
  header: ReactNode
  // How to pull / render the cell. `render` wins over `accessor`; default is the
  // raw Row[key] value (stringified, em-dash for null/undefined/'').
  accessor?: (row: Row) => unknown
  render?: (row: Row, value: unknown) => ReactNode
  align?: 'left' | 'right' | 'center'
  // Render the cell in monospace + tabular-nums (ids, counts, timestamps).
  mono?: boolean
  // Auto-direction the cell text for Arabic voc360 fields (text/text_clean,
  // canonical_label_ar, segment_text). Default false (ltr).
  rtlAware?: boolean
  // Fixed column width (px) or any CSS width string.
  width?: number | string
  // Optional sort handler — when provided, header becomes clickable.
  sortable?: boolean
}

export type SortState = { key: string; dir: 'asc' | 'desc' } | null

export interface DataGridProps<Row> {
  columns: Array<DataGridColumn<Row>>
  rows: Row[]
  // Row identity — falls back to array index when omitted.
  rowKey?: (row: Row, index: number) => Key
  // Optional row click (e.g. select a cluster / open a signal).
  onRowClick?: (row: Row, index: number) => void
  // Highlight the active row.
  isRowActive?: (row: Row, index: number) => boolean
  loading?: boolean
  // Empty / loading copy.
  emptyLabel?: ReactNode
  loadingLabel?: string
  // Controlled sort (optional). When `onSort` is supplied, sortable headers call
  // it; otherwise sortable headers are inert (purely presentational).
  sort?: SortState
  onSort?: (next: SortState) => void
  // Optional header strip above the table (mono caption, à la RootCausePage).
  caption?: ReactNode
  className?: string
}

function alignClass(a?: 'left' | 'right' | 'center'): string {
  if (a === 'right') return 'text-right'
  if (a === 'center') return 'text-center'
  return 'text-left'
}

function defaultCell(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string') return value.trim() === '' ? '—' : value
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : '—'
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  return String(value)
}

export function DataGrid<Row>({
  columns,
  rows,
  rowKey,
  onRowClick,
  isRowActive,
  loading = false,
  emptyLabel = 'No matching voc360 records.',
  loadingLabel = 'Loading…',
  sort = null,
  onSort,
  caption,
  className,
}: DataGridProps<Row>) {
  // Guard against an empty column set so we never render a bare <table>.
  const cols = useMemo(() => columns.filter(Boolean), [columns])
  const colSpan = Math.max(cols.length, 1)

  const handleSort = (col: DataGridColumn<Row>) => {
    if (!col.sortable || !onSort) return
    const sameKey = sort?.key === col.key
    const nextDir: 'asc' | 'desc' = sameKey && sort?.dir === 'asc' ? 'desc' : 'asc'
    onSort({ key: col.key, dir: nextDir })
  }

  return (
    <div
      className={`overflow-hidden rounded-xl border border-border bg-card ${className ?? ''}`}
    >
      {caption != null && (
        <div className="border-b border-border px-5 py-3 font-mono text-[10px] tracking-[0.14em] text-faint">
          {caption}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="text-[11px] font-medium tracking-[0.08em] text-faint">
              {cols.map((col, i) => {
                const sorted = sort?.key === col.key
                const clickable = !!(col.sortable && onSort)
                const style: CSSProperties | undefined = col.width
                  ? { width: col.width }
                  : undefined
                return (
                  <th
                    key={col.key}
                    style={style}
                    className={`py-3 font-medium ${alignClass(col.align)} ${
                      i === 0 ? 'pl-5' : ''
                    } ${i === cols.length - 1 ? 'pr-5' : 'pr-3'}`}
                  >
                    {clickable ? (
                      <button
                        type="button"
                        onClick={() => handleSort(col)}
                        className={`inline-flex items-center gap-1 transition-colors hover:text-muted ${
                          sorted ? 'text-muted' : ''
                        } ${col.align === 'right' ? 'flex-row-reverse' : ''}`}
                      >
                        {col.header}
                        {sorted &&
                          (sort?.dir === 'asc' ? (
                            <ChevronUp className="h-3 w-3" />
                          ) : (
                            <ChevronDown className="h-3 w-3" />
                          ))}
                      </button>
                    ) : (
                      col.header
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>

          <tbody>
            {/* loading (no rows yet) */}
            {loading && rows.length === 0 && (
              <tr>
                <td colSpan={colSpan} className="px-5 py-10 text-center">
                  <span className="inline-flex items-center gap-2 text-[13px] text-muted">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {loadingLabel}
                  </span>
                </td>
              </tr>
            )}

            {/* empty */}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={colSpan} className="px-5 py-10 text-center">
                  <span className="inline-flex items-center gap-2 text-[13px] text-muted">
                    <Inbox className="h-4 w-4" />
                    {emptyLabel}
                  </span>
                </td>
              </tr>
            )}

            {/* rows */}
            {rows.map((row, ri) => {
              const key = rowKey ? rowKey(row, ri) : ri
              const active = isRowActive?.(row, ri) ?? false
              const clickable = !!onRowClick
              return (
                <tr
                  key={key}
                  onClick={clickable ? () => onRowClick!(row, ri) : undefined}
                  className={`border-t border-border/70 transition-colors ${
                    active ? 'bg-soft' : ''
                  } ${clickable ? 'cursor-pointer hover:bg-soft/60' : ''}`}
                >
                  {cols.map((col, ci) => {
                    const raw = col.accessor
                      ? col.accessor(row)
                      : (row as Record<string, unknown>)[col.key]
                    const content: ReactNode = col.render
                      ? col.render(row, raw)
                      : defaultCell(raw)
                    const useRtl = col.rtlAware && isAr(raw)
                    return (
                      <td
                        key={col.key}
                        dir={useRtl ? 'rtl' : undefined}
                        className={`py-3.5 text-[13px] ${alignClass(col.align)} ${
                          col.mono ? 'font-mono tnum text-muted' : 'text-txt'
                        } ${ci === 0 ? 'pl-5' : ''} ${
                          ci === cols.length - 1 ? 'pr-5' : 'pr-3'
                        }`}
                      >
                        {content}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ---------------------------------------------------- small shared cells */

// A severity chip for voc360 severity / severity_avg — reusable inside DataGrid
// columns or detail panels.
export function SevBadge({
  sev,
  label,
}: {
  sev: unknown
  label?: ReactNode
}) {
  const k = sevKey(sev)
  const col = SEV[k]
  const text =
    label ??
    (typeof sev === 'number'
      ? sev.toFixed(2)
      : defaultCell(sev))
  return (
    <span className="inline-flex items-center gap-1.5 text-[13px]" style={{ color: col }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: col }} />
      {text}
    </span>
  )
}

// A neutral pill for categorical voc360 fields (source_type, service_id,
// governorate, sentiment_label, status…).
export function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-border bg-soft px-2 py-0.5 font-mono text-[11px] text-muted">
      {children}
    </span>
  )
}
