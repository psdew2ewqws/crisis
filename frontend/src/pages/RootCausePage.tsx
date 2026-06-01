// RootCausePage — T2 console page (real voc360 RIL clusters as root causes).
//
// Renders the ranked RIL problem clusters returned by GET /api/rootcause:
// English + Arabic labels (English via an optional build-time labels map, with a
// graceful fallback to the backend's canonical_label_en / canonical_label_ar),
// member counts, average severity, evidence segments, and an optional matched
// "valid solution" (cause → countermeasure) pulled from getSolutions when that
// endpoint exists. A "View in graph" action links the selected cluster across to
// the Root Cause graph view.
//
// Import-safe: every external dependency beyond ../lib/voc#getRootCause is
// resolved through optional dynamic imports with deterministic fallbacks, so the
// page compiles and runs today against the existing backend and degrades cleanly
// while T3 (labels map + solution engine) lands.

import { useEffect, useMemo, useState } from 'react'
import {
  Network,
  RefreshCw,
  Loader2,
  AlertTriangle,
  Quote,
  Lightbulb,
  Database,
  ChevronRight,
} from 'lucide-react'
import { getRootCause, type RootCause } from '../lib/voc'

/* ------------------------------------------------------------------ tokens */

const SEV = { alert: '#F04359', warn: '#FBBF24', calm: '#34D399', neutral: '#8B8D96' } as const
const isAr = (s: string | null | undefined) => !!s && /[؀-ۿ]/.test(s)
const dir = (s: string | null | undefined) => (isAr(s) ? 'rtl' : 'ltr')

// Severity bands match the LiveGraph convention (sev avg is 0..~1).
function sevColor(sev: number): string {
  if (sev >= 0.5) return SEV.alert
  if (sev >= 0.3) return SEV.warn
  return SEV.calm
}
function sevLabel(sev: number): string {
  if (sev >= 0.5) return 'Critical'
  if (sev >= 0.3) return 'Elevated'
  return 'Nominal'
}

/* -------------------------------------------------- optional labels map (T3) */
// English translations of the Arabic cluster labels are produced at build time
// (Track 3). We consume that map if it exists; otherwise we fall back to the
// backend-supplied label_en, then to the raw Arabic label.
type LabelEntry = { en?: string; ar?: string }
type LabelsMap = Record<string, LabelEntry | string>

async function loadLabels(): Promise<LabelsMap> {
  try {
    const mod: any = await import(/* @vite-ignore */ '../lib/labels')
    return (mod?.LABELS ?? mod?.labels ?? mod?.default ?? {}) as LabelsMap
  } catch {
    return {}
  }
}

function englishLabel(c: RootCause, labels: LabelsMap): string {
  const raw = labels[c.cluster_id]
  const fromMap = typeof raw === 'string' ? raw : raw?.en
  return (fromMap || c.label_en || '').trim() || '(untranslated cluster)'
}
function arabicLabel(c: RootCause, labels: LabelsMap): string {
  const raw = labels[c.cluster_id]
  const fromMap = typeof raw === 'string' ? undefined : raw?.ar
  return (fromMap || c.label_ar || '').trim()
}

/* ----------------------------------------------- optional solution engine (T3) */
// The "valid solution" engine (cause → countermeasure, feasibility, expected
// impact) is exposed via getSolutions in a later track. We probe for it without
// hard-coupling so this page stays import-safe before that endpoint exists.
interface Solution {
  cluster_id: string
  countermeasure: string
  feasibility?: string
  expected_impact?: string
  owner?: string
}

async function loadSolutions(): Promise<Record<string, Solution>> {
  try {
    const voc: any = await import('../lib/voc')
    const fn = voc?.getSolutions
    if (typeof fn !== 'function') return {}
    const res = await fn()
    const list: Solution[] = Array.isArray(res) ? res : (res?.solutions ?? [])
    const out: Record<string, Solution> = {}
    for (const s of list) if (s && s.cluster_id) out[s.cluster_id] = s
    return out
  } catch {
    return {}
  }
}

/* ----------------------------------------------------------------- component */

export default function RootCausePage({
  onNavigate,
}: {
  // App.tsx drives views via onNavigate(label); 'Root Cause' opens the graph view.
  onNavigate?: (view: string) => void
}) {
  const [causes, setCauses] = useState<RootCause[]>([])
  const [recommendation, setRecommendation] = useState<string | null>(null)
  const [labels, setLabels] = useState<LabelsMap>({})
  const [solutions, setSolutions] = useState<Record<string, Solution>>({})
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setErr(null)
    try {
      const [rc, lbls, sols] = await Promise.all([getRootCause(), loadLabels(), loadSolutions()])
      const ranked = rc.root_causes ?? []
      setCauses(ranked)
      setRecommendation(rc.recommendation ?? null)
      setLabels(lbls)
      setSolutions(sols)
      setSelected((prev) => prev ?? ranked[0]?.cluster_id ?? null)
    } catch (e) {
      setErr(String(e))
      setCauses([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  // Normalise the member bar against the dominant cluster so bars stay readable.
  const maxMembers = useMemo(
    () => causes.reduce((m, c) => Math.max(m, c.members || 0), 1),
    [causes],
  )
  const selectedCause = useMemo(
    () => causes.find((c) => c.cluster_id === selected) ?? null,
    [causes, selected],
  )

  const totalMembers = useMemo(
    () => causes.reduce((s, c) => s + (c.members || 0), 0),
    [causes],
  )

  return (
    <div className="flex-1 overflow-y-auto bg-bg">
      <div className="mx-auto max-w-[1340px] px-8 py-7">
        {/* header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-[28px] font-semibold tracking-tight text-txt">Root Cause Analysis</h1>
            <p className="mt-1.5 flex items-center gap-2 text-[14px] text-muted">
              <Database className="h-3.5 w-3.5" />
              Ranked RIL problem clusters from voc360
              {causes.length > 0 && (
                <span className="text-faint">
                  · {causes.length} clusters · {totalMembers.toLocaleString()} citizen reports
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onNavigate?.('Root Cause')}
              className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-[13px] text-muted transition-colors hover:bg-soft hover:text-txt"
            >
              <Network className="h-4 w-4" />
              Open graph
            </button>
            <button
              onClick={() => void load()}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-60"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              {loading ? 'Loading…' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* recommendation banner */}
        {recommendation && (
          <div
            className="mt-6 rounded-xl border border-blue/30 bg-blue/10 p-4 text-[13.5px] leading-snug text-txt"
            dir={dir(recommendation)}
          >
            <div className="mb-1 flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] text-bluehi">
              <Lightbulb className="h-3.5 w-3.5" />
              RECOMMENDATION
            </div>
            {recommendation}
          </div>
        )}

        {/* error */}
        {err && (
          <div className="mt-6 flex items-center gap-2 rounded-lg border border-danger/40 bg-card px-4 py-3 text-[13px] text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            Could not load root causes — {err}
          </div>
        )}

        {/* empty / loading */}
        {!err && loading && causes.length === 0 && (
          <div className="mt-10 flex items-center justify-center gap-2 text-[13px] text-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Ranking clusters…
          </div>
        )}
        {!err && !loading && causes.length === 0 && (
          <div className="mt-10 rounded-xl border border-border bg-card px-5 py-8 text-center text-[13px] text-muted">
            No root-cause clusters returned by voc360.
          </div>
        )}

        {causes.length > 0 && (
          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_400px]">
            {/* ranked list */}
            <div className="overflow-hidden rounded-xl border border-border bg-card">
              <div className="border-b border-border px-5 py-3 font-mono text-[10px] tracking-[0.14em] text-faint">
                RANKED ROOT CAUSES · RIL CLUSTERS
              </div>
              <ul>
                {causes.map((c) => {
                  const col = sevColor(c.severity_avg)
                  const en = englishLabel(c, labels)
                  const ar = arabicLabel(c, labels)
                  const active = c.cluster_id === selected
                  return (
                    <li key={c.cluster_id}>
                      <button
                        onClick={() => setSelected(c.cluster_id)}
                        className={`flex w-full items-start gap-3 border-t border-border/70 px-5 py-3.5 text-left transition-colors first:border-t-0 hover:bg-soft/60 ${
                          active ? 'bg-soft' : ''
                        }`}
                      >
                        <span className="mt-0.5 w-7 shrink-0 font-mono text-[12px] text-muted">
                          #{c.rank}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-baseline justify-between gap-3">
                            <span className="truncate text-[14px] font-medium text-txt">{en}</span>
                            <span
                              className="shrink-0 font-mono text-[11px]"
                              style={{ color: col }}
                            >
                              {c.members} · sev {c.severity_avg}
                            </span>
                          </div>
                          {ar && (
                            <div
                              className="mt-0.5 truncate text-[12.5px] text-muted"
                              dir="rtl"
                            >
                              {ar}
                            </div>
                          )}
                          <div className="mt-2 h-1 overflow-hidden rounded-full bg-soft">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${Math.min(100, ((c.members || 0) / maxMembers) * 100)}%`,
                                background: col,
                              }}
                            />
                          </div>
                        </div>
                        <ChevronRight
                          className={`mt-1 h-4 w-4 shrink-0 transition-colors ${
                            active ? 'text-txt' : 'text-faint'
                          }`}
                        />
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>

            {/* detail panel */}
            <ClusterDetail
              cause={selectedCause}
              labels={labels}
              solution={selectedCause ? solutions[selectedCause.cluster_id] : undefined}
              onOpenGraph={() => onNavigate?.('Root Cause')}
            />
          </div>
        )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------- detail panel */

function ClusterDetail({
  cause,
  labels,
  solution,
  onOpenGraph,
}: {
  cause: RootCause | null
  labels: LabelsMap
  solution?: Solution
  onOpenGraph: () => void
}) {
  if (!cause) {
    return (
      <aside className="rounded-xl border border-border bg-card p-5 text-[13px] text-muted">
        Select a cluster to inspect its evidence and recommended countermeasure.
      </aside>
    )
  }

  const col = sevColor(cause.severity_avg)
  const en = englishLabel(cause, labels)
  const ar = arabicLabel(cause, labels)

  return (
    <aside className="flex flex-col gap-4 self-start rounded-xl border border-border bg-card p-5">
      {/* title */}
      <div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: col }} />
          <span className="font-mono text-[10px] tracking-[0.14em] text-faint">
            CLUSTER · RANK #{cause.rank}
          </span>
        </div>
        <h2 className="mt-2 text-[18px] font-semibold leading-snug tracking-tight text-txt">{en}</h2>
        {ar && (
          <p className="mt-1 text-[14px] leading-snug text-muted" dir="rtl">
            {ar}
          </p>
        )}
        <p className="mt-2 font-mono text-[11px] text-faint">{cause.cluster_id}</p>
      </div>

      {/* metrics */}
      <div className="grid grid-cols-3 gap-2">
        <Metric label="REPORTS" value={cause.members.toLocaleString()} />
        <Metric label="SEVERITY" value={String(cause.severity_avg)} tone={col} sub={sevLabel(cause.severity_avg)} />
        <Metric label="SCORE" value={String(cause.score)} />
      </div>

      {/* evidence */}
      <div>
        <div className="mb-2 flex items-center gap-1.5 font-mono text-[10px] tracking-[0.14em] text-faint">
          <Quote className="h-3 w-3" />
          EVIDENCE SEGMENTS
        </div>
        {cause.evidence.length > 0 ? (
          <ul className="space-y-2">
            {cause.evidence.map((ev, i) => (
              <li
                key={i}
                className="rounded-lg border border-border bg-cardhi px-3 py-2 text-[12.5px] leading-snug text-txt"
                dir={dir(ev)}
              >
                {ev}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[12px] text-muted">No sample segments returned for this cluster.</p>
        )}
      </div>

      {/* valid solution (optional, from solution engine) */}
      {solution && (
        <div className="rounded-lg border border-good/30 bg-good/10 p-3">
          <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[10px] tracking-[0.14em] text-good">
            <Lightbulb className="h-3 w-3" />
            VALID SOLUTION
          </div>
          <p className="text-[13px] leading-snug text-txt" dir={dir(solution.countermeasure)}>
            {solution.countermeasure}
          </p>
          {(solution.feasibility || solution.expected_impact || solution.owner) && (
            <dl className="mt-2 space-y-1 text-[11.5px]">
              {solution.owner && <SolutionRow k="Owner" v={solution.owner} />}
              {solution.feasibility && <SolutionRow k="Feasibility" v={solution.feasibility} />}
              {solution.expected_impact && <SolutionRow k="Expected impact" v={solution.expected_impact} />}
            </dl>
          )}
        </div>
      )}

      {/* link to graph */}
      <button
        onClick={onOpenGraph}
        className="mt-1 flex items-center justify-center gap-2 rounded-lg border border-border px-3 py-2 text-[13px] text-muted transition-colors hover:bg-soft hover:text-txt"
      >
        <Network className="h-4 w-4" />
        View this cluster in the graph
      </button>
    </aside>
  )
}

function Metric({
  label,
  value,
  sub,
  tone,
}: {
  label: string
  value: string
  sub?: string
  tone?: string
}) {
  return (
    <div className="rounded-lg border border-border bg-cardhi px-3 py-2.5">
      <div className="font-mono text-[9px] tracking-[0.12em] text-faint">{label}</div>
      <div className="mt-1 font-mono text-[16px] text-txt" style={tone ? { color: tone } : undefined}>
        {value}
      </div>
      {sub && <div className="font-mono text-[10px] text-muted">{sub}</div>}
    </div>
  )
}

function SolutionRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2">
      <dt className="shrink-0 font-mono text-faint">{k}:</dt>
      <dd className="text-muted" dir={dir(v)}>
        {v}
      </dd>
    </div>
  )
}
