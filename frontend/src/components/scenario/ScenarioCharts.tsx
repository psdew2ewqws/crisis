// ScenarioCharts — the simulation readout for a single scenario run. Reads the
// 'simulate' ScenarioEvent and renders the Mesa SEIR result in the same visual
// language as the Simulation page: a row of 4 StatCards, then two before/after
// AREA charts (mean negativity, critical nodes) where BEFORE is a dashed grey
// line and AFTER is the solid intervention line with a gradient fill. Plus a
// small escalation chip sourced from the forecast/simulation. Arabic-first.
//
// Every field is read defensively — a partial payload (fallback engine, empty
// graph) still renders the empty state instead of throwing. Matches AEGIS tokens.

import { useMemo } from 'react'
import { ShieldCheck, TrendingUp } from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { motion } from 'motion/react'
import type { ScenarioEvent, ScenarioSeriesPoint } from '../../lib/voc'

// --------------------------------------------------------------------------- //
// Helpers — never trust the payload to be complete.                           //
// --------------------------------------------------------------------------- //

function num(v: unknown, fallback = 0): number {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : fallback
}

function asSeries(v: unknown): ScenarioSeriesPoint[] {
  if (!Array.isArray(v)) return []
  return v
    .filter((p): p is Record<string, unknown> => !!p && typeof p === 'object')
    .map((p, i) => ({
      step: num(p.step, i),
      mean_negativity: num(p.mean_negativity, 0),
      n_critical: Math.round(num(p.n_critical, 0)),
    }))
}

const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`
const fmt0 = (n: number) => Math.round(n).toLocaleString('en-US')
// risk_before / risk_after / risk_reduction are already a 0..100 risk SCORE — show
// them as a point value out of 100, NOT as a fraction multiplied by 100.
const fmtRisk = (n: number) => n.toFixed(1)

// Merge before/after series, step-aligned, into one row-per-step frame.
interface MergedPoint {
  step: number
  before: number
  after: number
}
function mergeSeries(
  before: ScenarioSeriesPoint[],
  after: ScenarioSeriesPoint[],
  key: 'mean_negativity' | 'n_critical',
): MergedPoint[] {
  const len = Math.max(before.length, after.length)
  const out: MergedPoint[] = []
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
// Design-system constants.                                                     //
// --------------------------------------------------------------------------- //

const TOOLTIP = {
  contentStyle: {
    background: '#131417',
    border: '1px solid #212228',
    borderRadius: 10,
    fontSize: 12,
  },
  labelStyle: { color: '#8B8D96' },
  itemStyle: { color: '#ECEDEE' },
}

const BEFORE_COLOR = '#62646D'

type Tone = 'good' | 'danger' | 'warn' | 'blue' | 'neutral'
const TONE_TEXT: Record<Tone, string> = {
  good: 'text-good',
  danger: 'text-danger',
  warn: 'text-warn',
  blue: 'text-blue',
  neutral: 'text-txt',
}

// --------------------------------------------------------------------------- //
// StatCard — small label, big tnum value, faint hint.                          //
// --------------------------------------------------------------------------- //

function StatCard({
  label,
  value,
  hint,
  tone = 'neutral',
}: {
  label: string
  value: string
  hint?: string
  tone?: Tone
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-[13px] text-muted" dir="auto">
        {label}
      </div>
      <div
        className={`mt-3 text-[30px] font-semibold leading-none tracking-tight tnum ${TONE_TEXT[tone]}`}
      >
        {value}
      </div>
      {hint && (
        <div className="mt-2 text-[12.5px] text-faint" dir="auto">
          {hint}
        </div>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Before/after AREA chart.                                                      //
// --------------------------------------------------------------------------- //

function CompareChart({
  title,
  sub,
  before,
  after,
  metricKey,
  color,
  domain,
  format,
}: {
  title: string
  sub: string
  before: ScenarioSeriesPoint[]
  after: ScenarioSeriesPoint[]
  metricKey: 'mean_negativity' | 'n_critical'
  color: string
  domain: [number | 'auto', number | 'auto']
  format: (n: number) => string
}) {
  const data = useMemo(
    () => mergeSeries(before, after, metricKey),
    [before, after, metricKey],
  )
  const gradId = `scen-grad-${metricKey}`
  const hasData = data.some((d) => Number.isFinite(d.before) || Number.isFinite(d.after))

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <div className="text-[15px] font-semibold text-txt" dir="auto">
            {title}
          </div>
          <div className="mt-0.5 text-[12.5px] text-muted" dir="auto">
            {sub}
          </div>
        </div>
        <div className="flex items-center gap-3 text-[11.5px]">
          <span className="flex items-center gap-1.5 text-faint" dir="auto">
            <span
              className="inline-block h-0.5 w-4 rounded-full"
              style={{ background: BEFORE_COLOR }}
            />
            قبل
          </span>
          <span className="flex items-center gap-1.5 text-txt" dir="auto">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
            بعد التدخّل
          </span>
        </div>
      </div>

      {hasData ? (
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -16 }}>
            <defs>
              <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.28} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
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
              domain={domain}
              tick={{ fill: '#62646D', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v) => format(num(v))}
            />
            <Tooltip
              {...TOOLTIP}
              cursor={{ stroke: color, strokeWidth: 1, strokeDasharray: '3 3' }}
              labelFormatter={(l) => `خطوة ${l}`}
              formatter={(v, name) => [format(num(v)), name === 'before' ? 'قبل' : 'بعد التدخّل']}
            />
            <Legend
              iconType="plainline"
              wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
              formatter={(value) => (
                <span className="text-muted">{value === 'before' ? 'قبل' : 'بعد التدخّل'}</span>
              )}
            />
            <Area
              type="monotone"
              dataKey="before"
              name="before"
              stroke={BEFORE_COLOR}
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
              name="after"
              stroke={color}
              strokeWidth={2.5}
              fill={`url(#${gradId})`}
              dot={false}
              connectNulls
              activeDot={{ r: 4, fill: color, stroke: '#0A0A0B', strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex h-[220px] items-center justify-center text-[13px] text-faint" dir="auto">
          لا توجد بيانات محاكاة
        </div>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Component.                                                                    //
// --------------------------------------------------------------------------- //

export default function ScenarioCharts({ sim }: { sim: ScenarioEvent }) {
  const before = useMemo(() => asSeries(sim.series_before), [sim.series_before])
  const after = useMemo(() => asSeries(sim.series_after), [sim.series_after])

  const riskBefore = num(sim.risk_before)
  const riskAfter = num(sim.risk_after)
  const riskReduction = num(sim.risk_reduction)
  const settle = sim.seir_before?.ticks_to_settle
  const hasSettle = typeof settle === 'number' && Number.isFinite(settle)

  const esc = sim.escalation
  const escalating = !!esc?.escalating
  const escSource =
    esc?.source === 'forecast'
      ? 'المصدر: التنبّؤ الزمني'
      : esc?.source === 'simulation'
        ? 'المصدر: المحاكاة'
        : null

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-4"
    >
      {/* Escalation chip */}
      {esc && (
        <div className="flex items-center gap-3">
          <span
            className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[12px] font-medium ${
              escalating
                ? 'border-warn/30 bg-warn/10 text-warn'
                : 'border-good/30 bg-good/10 text-good'
            }`}
            dir="auto"
          >
            {escalating ? (
              <TrendingUp className="h-3.5 w-3.5" />
            ) : (
              <ShieldCheck className="h-3.5 w-3.5" />
            )}
            {escalating ? 'تصاعد متوقّع' : 'اتجاه مستقر'}
          </span>
          {(escSource || esc.note) && (
            <span className="text-[12px] text-faint" dir="auto">
              {esc.note ?? escSource}
            </span>
          )}
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="الخطر المتوقّع (قبل)"
          value={fmtRisk(riskBefore)}
          hint="من ١٠٠ · قبل أي تدخّل"
          tone="neutral"
        />
        <StatCard
          label="بعد التدخّل"
          value={fmtRisk(riskAfter)}
          hint="من ١٠٠ · بعد تطبيق التدخّل"
          tone="good"
        />
        <StatCard
          label="انخفاض الخطر"
          value={`${riskReduction > 0 ? '−' : ''}${fmtRisk(Math.abs(riskReduction))}`}
          hint={`${fmtRisk(riskBefore)} ← ${fmtRisk(riskAfter)} نقطة`}
          tone={riskReduction > 0 ? 'good' : 'neutral'}
        />
        <StatCard
          label="خطوات الاستقرار"
          value={hasSettle ? fmt0(num(settle)) : '—'}
          hint="عدد الخطوات حتى استقرار النظام"
          tone="blue"
        />
      </div>

      {/* Before/after charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CompareChart
          title="متوسط السلبية"
          sub="متوسط حمولة المشاعر عبر العُقد"
          before={before}
          after={after}
          metricKey="mean_negativity"
          color="#F04359"
          domain={[0, 1]}
          format={fmtPct}
        />
        <CompareChart
          title="العُقد الحرجة"
          sub="عدد العُقد فوق عتبة الخطورة"
          before={before}
          after={after}
          metricKey="n_critical"
          color="#3B82F6"
          domain={[0, 'auto']}
          format={fmt0}
        />
      </div>
    </motion.div>
  )
}
