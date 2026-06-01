// SimulationPage — Mesa agent-based simulation of complaint/sentiment propagation
// across the live voc360 graph (services × governorates × sources × root-cause
// clusters). Before/after A/B of the intervention lever, charted on the three real
// SimResult variables: mean_negativity, complaint_volume, n_critical.
//
// Data source: getSimulate() → backend mesa_sim.simulate(case, intervene=True),
// which returns the BeforeAfter shape:
//   { before:{series[]}, after:{series[]}, delta:{...}, root_cause:{...},
//     engine, mesa_available, params? }
// Real voc360 columns only. Import-safe: every field is read defensively so a
// partial/empty payload (or a backend running the deterministic fallback engine)
// still renders without throwing. Matches AEGIS tokens + existing module sigs.

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  GitBranch,
  Loader2,
  Play,
  RotateCcw,
  ShieldCheck,
  TrendingDown,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getSimulate, type Sim, type SimSeries } from '../lib/voc'

// --------------------------------------------------------------------------- //
// Defensive accessors — the typed `Sim` is the happy path, but we never trust  //
// the payload to be complete (fallback engine, empty graph, transport hiccup). //
// --------------------------------------------------------------------------- //

type Loose = Record<string, unknown>

function asSeries(v: unknown): SimSeries[] {
  if (!Array.isArray(v)) return []
  return v
    .filter((p): p is Loose => !!p && typeof p === 'object')
    .map((p, i) => ({
      step: num(p.step, i),
      mean_negativity: num(p.mean_negativity, 0),
      complaint_volume: num(p.complaint_volume, 0),
      n_critical: Math.round(num(p.n_critical, 0)),
    }))
}

function num(v: unknown, fallback = 0): number {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : fallback
}

function lastOf(series: SimSeries[]): SimSeries | null {
  return series.length ? series[series.length - 1] : null
}

function peak(series: SimSeries[], key: keyof SimSeries): number {
  return series.reduce((m, p) => Math.max(m, num(p[key], 0)), 0)
}

// Backend nests run params under before/after.params; expose them if present.
function readParams(sim: Sim | null): {
  steps?: number
  spread_rate?: number
  decay?: number
  inflow?: number
  intervention_strength?: number
  seed?: number
} {
  if (!sim) return {}
  const top = (sim as unknown as Loose).params
  const after = ((sim as unknown as Loose).after as Loose | undefined)?.params
  const src = (top ?? after) as Loose | undefined
  if (!src || typeof src !== 'object') return {}
  return {
    steps: numU(src.steps),
    spread_rate: numU(src.spread_rate),
    decay: numU(src.decay),
    inflow: numU(src.inflow),
    intervention_strength: numU(src.intervention_strength),
    seed: numU(src.seed),
  }
}
function numU(v: unknown): number | undefined {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : undefined
}

// Merge before/after into one row-per-step frame for the comparison charts.
interface Merged {
  step: number
  before: number
  after: number
}
function mergeSeries(
  before: SimSeries[],
  after: SimSeries[],
  key: keyof SimSeries,
): Merged[] {
  const len = Math.max(before.length, after.length)
  const out: Merged[] = []
  for (let i = 0; i < len; i++) {
    const b = before[i]
    const a = after[i]
    out.push({
      step: num(b?.step ?? a?.step, i),
      before: b ? num(b[key], 0) : NaN,
      after: a ? num(a[key], 0) : NaN,
    })
  }
  return out
}

// --------------------------------------------------------------------------- //
// Formatting helpers.                                                          //
// --------------------------------------------------------------------------- //

const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`
const fmt2 = (n: number) => n.toFixed(2)
const fmt0 = (n: number) => Math.round(n).toLocaleString()
const signed = (n: number, f: (x: number) => string) => `${n > 0 ? '+' : ''}${f(n)}`

// --------------------------------------------------------------------------- //
// Chart metric registry.                                                       //
// --------------------------------------------------------------------------- //

interface MetricDef {
  key: keyof SimSeries
  title: string
  sub: string
  color: string
  format: (n: number) => string
  domain?: [number | 'auto', number | 'auto']
}
const METRICS: MetricDef[] = [
  {
    key: 'mean_negativity',
    title: 'Mean Negativity',
    sub: 'Average sentiment load across all seated nodes',
    color: '#F04359',
    format: fmtPct,
    domain: [0, 1],
  },
  {
    key: 'complaint_volume',
    title: 'Complaint Volume',
    sub: 'Aggregate weighted inflow across the graph',
    color: '#FBBF24',
    format: fmt0,
    domain: ['auto', 'auto'],
  },
  {
    key: 'n_critical',
    title: 'Critical Nodes',
    sub: 'Nodes with sentiment > 0.7 (critical threshold)',
    color: '#3B82F6',
    format: fmt0,
    domain: [0, 'auto'],
  },
]

const CHART_TOOLTIP = {
  contentStyle: {
    background: '#131417',
    border: '1px solid #212228',
    borderRadius: 10,
    fontSize: 12,
  },
  labelStyle: { color: '#8B8D96' },
  itemStyle: { color: '#ECEDEE' },
}

// --------------------------------------------------------------------------- //
// Small presentational pieces.                                                 //
// --------------------------------------------------------------------------- //

function StatCard({
  label,
  value,
  hint,
  tone = 'neutral',
  icon: Icon,
}: {
  label: string
  value: string
  hint?: string
  tone?: 'good' | 'danger' | 'warn' | 'blue' | 'neutral'
  icon?: typeof Activity
}) {
  const toneCls: Record<string, string> = {
    good: 'text-good',
    danger: 'text-danger',
    warn: 'text-warn',
    blue: 'text-blue',
    neutral: 'text-txt',
  }
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between">
        <span className="text-[13px] text-muted">{label}</span>
        {Icon && <Icon className={`h-4 w-4 ${toneCls[tone]}`} />}
      </div>
      <div className={`mt-3 text-[30px] font-semibold leading-none tracking-tight tnum ${toneCls[tone]}`}>
        {value}
      </div>
      {hint && <div className="mt-2 text-[12.5px] text-faint">{hint}</div>}
    </div>
  )
}

function MetricChart({
  metric,
  before,
  after,
}: {
  metric: MetricDef
  before: SimSeries[]
  after: SimSeries[]
}) {
  const data = useMemo(
    () => mergeSeries(before, after, metric.key),
    [before, after, metric.key],
  )
  const gradId = `grad-${metric.key}`
  const hasData = data.some((d) => Number.isFinite(d.before) || Number.isFinite(d.after))

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <div className="text-[15px] font-semibold text-txt">{metric.title}</div>
          <div className="mt-0.5 text-[12.5px] text-muted">{metric.sub}</div>
        </div>
        <div className="flex items-center gap-3 text-[11.5px]">
          <span className="flex items-center gap-1.5 text-faint">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'var(--color-faint)' }} />
            Before
          </span>
          <span className="flex items-center gap-1.5 text-txt">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: metric.color }} />
            After fix
          </span>
        </div>
      </div>

      {hasData ? (
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -16 }}>
            <defs>
              <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={metric.color} stopOpacity={0.28} />
                <stop offset="100%" stopColor={metric.color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1A1B20" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="step"
              tick={{ fill: '#62646D', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              dy={6}
            />
            <YAxis
              domain={metric.domain ?? ['auto', 'auto']}
              tick={{ fill: '#62646D', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v) => metric.format(num(v))}
            />
            <Tooltip
              {...CHART_TOOLTIP}
              cursor={{ stroke: metric.color, strokeWidth: 1, strokeDasharray: '3 3' }}
              labelFormatter={(l) => `Step ${l}`}
              formatter={(v, name) => [metric.format(num(v)), name === 'before' ? 'Before' : 'After fix']}
            />
            <Area
              type="monotone"
              dataKey="before"
              stroke="#62646D"
              strokeWidth={1.75}
              strokeDasharray="4 3"
              fill="none"
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="after"
              stroke={metric.color}
              strokeWidth={2.5}
              fill={`url(#${gradId})`}
              dot={false}
              connectNulls
              activeDot={{ r: 4, fill: metric.color, stroke: '#0A0A0B', strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex h-[220px] items-center justify-center text-[13px] text-faint">
          No series data
        </div>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Page.                                                                        //
// --------------------------------------------------------------------------- //

export default function SimulationPage({ caseId }: { caseId?: string } = {}) {
  const [sim, setSim] = useState<Sim | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    getSimulate(caseId)
      .then((s) => setSim(s))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Simulation failed'))
      .finally(() => setLoading(false))
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  const before = useMemo(() => asSeries((sim as unknown as Loose)?.before && ((sim as unknown as Loose).before as Loose).series), [sim])
  const after = useMemo(() => asSeries((sim as unknown as Loose)?.after && ((sim as unknown as Loose).after as Loose).series), [sim])

  const bLast = lastOf(before)
  const aLast = lastOf(after)
  const params = readParams(sim)

  // Delta: prefer backend-computed values; fall back to deriving from series.
  const rawDelta = (sim?.delta ?? {}) as Record<string, number>
  const negDelta =
    'mean_negativity_final' in rawDelta
      ? num(rawDelta.mean_negativity_final)
      : num(bLast?.mean_negativity) - num(aLast?.mean_negativity)
  const critDelta =
    'n_critical_final' in rawDelta
      ? num(rawDelta.n_critical_final)
      : num(bLast?.n_critical) - num(aLast?.n_critical)
  const peakDelta =
    'peak_mean_negativity' in rawDelta
      ? num(rawDelta.peak_mean_negativity)
      : peak(before, 'mean_negativity') - peak(after, 'mean_negativity')
  const settle = num(rawDelta.ticks_to_settle, after.length)

  const rc = sim?.root_cause ?? null
  const rcLabel = rc?.canonical_label_ar
  const rcMembers = rc?.member_count
  const engine = sim?.engine ?? '—'
  const mesaAvailable = !!sim?.mesa_available

  const hasResult = before.length > 0 || after.length > 0

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[1340px] px-8 py-7">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-[28px] font-semibold tracking-tight text-txt">Simulation</h1>
            <p className="mt-1.5 text-[14px] text-muted">
              Agent-based sentiment propagation across the live voc360 graph ·{' '}
              <span className="font-medium text-txt">before vs after</span> the root-cause fix
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={load}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-3.5 py-2.5 text-[13.5px] font-medium text-muted transition-colors hover:bg-cardhi hover:text-txt disabled:opacity-50"
            >
              <RotateCcw className="h-4 w-4" />
              Reset
            </button>
            <button
              onClick={load}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-60"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-white" />}
              {loading ? 'Simulating…' : 'Re-run simulation'}
            </button>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mt-6 flex items-center gap-2.5 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-[13px] text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>
              Could not reach the simulation engine: <span className="font-mono">{error}</span>
            </span>
          </div>
        )}

        {/* Loading skeleton (first load, no prior data) */}
        {loading && !hasResult && !error && (
          <div className="mt-16 flex flex-col items-center justify-center gap-3 text-muted">
            <Loader2 className="h-6 w-6 animate-spin text-blue" />
            <span className="text-[13.5px]">Building case graph and propagating sentiment…</span>
          </div>
        )}

        {/* Empty (resolved but nothing came back) */}
        {!loading && !hasResult && !error && (
          <div className="mt-16 flex flex-col items-center justify-center gap-2 text-faint">
            <Activity className="h-6 w-6" />
            <span className="text-[13.5px]">No simulation result yet.</span>
          </div>
        )}

        {hasResult && (
          <>
            {/* Intervention / root-cause context */}
            <div className="mt-6 rounded-xl border border-border bg-card p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-lg border border-blue/30 bg-blue/10 p-2">
                    <GitBranch className="h-5 w-5 text-blue" />
                  </div>
                  <div>
                    <div className="text-[12px] uppercase tracking-wide text-faint">Intervention target</div>
                    {rcLabel ? (
                      <div className="mt-1 text-[16px] font-semibold text-txt" dir="auto">
                        {rcLabel}
                      </div>
                    ) : (
                      <div className="mt-1 text-[15px] font-medium text-muted">
                        Top-ranked root-cause cluster (auto-targeted)
                      </div>
                    )}
                    <div className="mt-1 text-[12.5px] text-muted">
                      {rcMembers != null
                        ? `${fmt0(rcMembers)} member segments damped at the source node`
                        : 'Dominant cluster damped at the source node'}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 font-mono text-[11px] ${
                      mesaAvailable
                        ? 'border-good/30 bg-good/10 text-good'
                        : 'border-warn/30 bg-warn/10 text-warn'
                    }`}
                  >
                    <ShieldCheck className="h-3.5 w-3.5" />
                    engine: {engine}
                  </span>
                  {!mesaAvailable && (
                    <span className="rounded-md border border-border bg-soft px-2.5 py-1 font-mono text-[11px] text-muted">
                      mesa unavailable · deterministic fallback
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Delta summary */}
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="Δ Mean negativity"
                value={signed(negDelta, fmtPct)}
                hint={`${fmtPct(num(bLast?.mean_negativity))} → ${fmtPct(num(aLast?.mean_negativity))} at final step`}
                tone={negDelta > 0 ? 'good' : negDelta < 0 ? 'danger' : 'neutral'}
                icon={TrendingDown}
              />
              <StatCard
                label="Δ Critical nodes"
                value={signed(-critDelta, (n) => fmt0(Math.abs(n)))}
                hint={`${fmt0(num(bLast?.n_critical))} → ${fmt0(num(aLast?.n_critical))} nodes over threshold`}
                tone={critDelta > 0 ? 'good' : critDelta < 0 ? 'danger' : 'neutral'}
                icon={AlertTriangle}
              />
              <StatCard
                label="Δ Peak negativity"
                value={signed(peakDelta, fmtPct)}
                hint="Reduction in worst-tick sentiment load"
                tone={peakDelta > 0 ? 'good' : peakDelta < 0 ? 'danger' : 'neutral'}
                icon={Activity}
              />
              <StatCard
                label="Ticks to settle"
                value={fmt0(settle)}
                hint="Steps until the fixed system stabilizes"
                tone="blue"
                icon={GitBranch}
              />
            </div>

            {/* Run parameters */}
            {(params.steps != null ||
              params.spread_rate != null ||
              params.decay != null ||
              params.inflow != null ||
              params.intervention_strength != null) && (
              <div className="mt-4 rounded-xl border border-border bg-card px-5 py-4">
                <div className="mb-3 text-[12px] uppercase tracking-wide text-faint">Run parameters</div>
                <div className="flex flex-wrap gap-x-8 gap-y-2.5 font-mono text-[12.5px]">
                  <Param label="steps" value={params.steps} format={fmt0} />
                  <Param label="spread_rate" value={params.spread_rate} format={fmt2} />
                  <Param label="decay" value={params.decay} format={(n) => n.toFixed(3)} />
                  <Param label="inflow" value={params.inflow} format={(n) => n.toFixed(3)} />
                  <Param
                    label="intervention_strength"
                    value={params.intervention_strength}
                    format={fmt2}
                  />
                  <Param label="seed" value={params.seed} format={fmt0} />
                </div>
              </div>
            )}

            {/* Before/after metric charts */}
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <MetricChart metric={METRICS[0]} before={before} after={after} />
              <MetricChart metric={METRICS[2]} before={before} after={after} />
            </div>
            <div className="mt-4">
              <MetricChart metric={METRICS[1]} before={before} after={after} />
            </div>

            {/* Trajectory overlay — all three after-fix variables, one frame */}
            <TrajectoryOverlay after={after} />
          </>
        )}
      </div>
    </div>
  )
}

function Param({
  label,
  value,
  format,
}: {
  label: string
  value: number | undefined
  format: (n: number) => string
}) {
  if (value == null) return null
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="text-faint">{label}</span>
      <span className="text-txt">{format(value)}</span>
    </span>
  )
}

// Normalized after-fix trajectory so all three series share one axis (0..1).
function TrajectoryOverlay({ after }: { after: SimSeries[] }) {
  const data = useMemo(() => {
    const maxVol = Math.max(1, peak(after, 'complaint_volume'))
    const maxCrit = Math.max(1, peak(after, 'n_critical'))
    return after.map((p, i) => ({
      step: num(p.step, i),
      neg: num(p.mean_negativity),
      vol: num(p.complaint_volume) / maxVol,
      crit: num(p.n_critical) / maxCrit,
    }))
  }, [after])

  if (!data.length) return null

  return (
    <div className="mt-4 rounded-xl border border-border bg-card p-5">
      <div className="mb-4">
        <div className="text-[15px] font-semibold text-txt">After-fix trajectory</div>
        <div className="mt-0.5 text-[12.5px] text-muted">
          All three variables normalized to [0,1] over the post-intervention run
        </div>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid stroke="#1A1B20" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="step"
            tick={{ fill: '#62646D', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            dy={6}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: '#62646D', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={36}
            tickFormatter={(v) => fmt2(num(v))}
          />
          <Tooltip
            {...CHART_TOOLTIP}
            cursor={{ stroke: '#3B82F6', strokeWidth: 1, strokeDasharray: '3 3' }}
            labelFormatter={(l) => `Step ${l}`}
            formatter={(v, name) => {
              const labels: Record<string, string> = {
                neg: 'Mean negativity',
                vol: 'Complaint volume (norm)',
                crit: 'Critical nodes (norm)',
              }
              return [fmt2(num(v)), labels[name as string] ?? String(name)]
            }}
          />
          <Legend
            iconType="plainline"
            wrapperStyle={{ fontSize: 12, color: '#8B8D96', paddingTop: 8 }}
            formatter={(value) => {
              const labels: Record<string, string> = {
                neg: 'Mean negativity',
                vol: 'Complaint volume',
                crit: 'Critical nodes',
              }
              return <span className="text-muted">{labels[value] ?? value}</span>
            }}
          />
          <Line type="monotone" dataKey="neg" stroke="#F04359" strokeWidth={2.25} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="vol" stroke="#FBBF24" strokeWidth={2.25} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="crit" stroke="#3B82F6" strokeWidth={2.25} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
