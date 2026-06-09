// ComparisonDashboard — the "Before vs After" view (لوحة المقارنة).
// Reads the already-streamed simulation data and presents a side-by-side
// comparison: a headline banner, a Before/After KPI grid with delta chips,
// the before/after trajectory charts (ScenarioCharts), and per-governorate
// affected-area bars. All numbers come from existing data — nothing refetched.

import { motion } from 'motion/react'
import { TrendingDown, Activity, MapPin, ArrowLeft } from 'lucide-react'
import ScenarioCharts from './ScenarioCharts'
import type { AbmEvent, AbmImpactTimeline, ScenarioEvent } from '../../lib/voc'

const SEV_AR: Record<string, string> = { low: 'منخفضة', elevated: 'مرتفعة', critical: 'حرجة' }
const SEV_RANK: Record<string, number> = { low: 0, elevated: 1, critical: 2 }

// Derived economic-impact constants (USD, conservative, clearly labelled تقديري).
const C_DEATH = 1_500_000   // value-of-statistical-life proxy
const C_DISP = 2_000        // short-term displacement cost / person
const C_AFFECT = 200        // minor disruption cost / affected person

function fmt(n: number): string {
  if (!isFinite(n)) return '—'
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return Math.round(n).toLocaleString('en-US')
}
function fmtUsd(n: number): string {
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(0)}M`
  return `$${fmt(n)}`
}
function peakHospital(t: AbmImpactTimeline | null): number {
  if (!t?.steps?.length) return 0
  return Math.max(...t.steps.map(s => s.hospital_load_pct || 0))
}
function econ(t: AbmImpactTimeline | null): number {
  if (!t?.totals) return 0
  return t.totals.casualties * C_DEATH + t.totals.displaced * C_DISP + t.totals.affected * C_AFFECT
}

// Aggregate peak affected per governorate across timeline steps.
function byGovPeak(t: AbmImpactTimeline | null): Map<string, { name_ar: string; affected: number }> {
  const m = new Map<string, { name_ar: string; affected: number }>()
  if (!t?.steps) return m
  for (const step of t.steps) {
    for (const g of step.by_gov ?? []) {
      const cur = m.get(g.gov)
      if (!cur || g.affected > cur.affected) m.set(g.gov, { name_ar: g.name_ar, affected: g.affected })
    }
  }
  return m
}

interface KpiRow {
  label: string
  before: string
  after: string
  reductionPct: number | null   // null = non-numeric (severity)
  betterAfter: boolean
}

function buildKpis(sim: AbmEvent, crisis: AbmImpactTimeline | null, sol: AbmImpactTimeline | null): KpiRow[] {
  const rows: KpiRow[] = []
  const num = (a: number, b: number, fmtFn: (n: number) => string, label: string, suffix = '') => {
    const red = a > 0 ? Math.round(((a - b) / a) * 100) : 0
    rows.push({ label, before: fmtFn(a) + suffix, after: fmtFn(b) + suffix, reductionPct: red, betterAfter: b <= a })
  }

  const rb = sim.risk_before ?? 0, ra = sim.risk_after ?? 0
  num(rb, ra, n => `${n.toFixed(1)}`, 'مؤشّر الخطر', '٪')

  // severity (non-numeric)
  const sb = sim.seir_before?.severity ?? 'low', sa = sim.seir_after?.severity ?? 'low'
  rows.push({
    label: 'درجة الخطورة',
    before: SEV_AR[sb] ?? sb, after: SEV_AR[sa] ?? sa,
    reductionPct: null, betterAfter: (SEV_RANK[sa] ?? 0) <= (SEV_RANK[sb] ?? 0),
  })

  if (crisis?.totals && sol?.totals) {
    num(crisis.totals.casualties, sol.totals.casualties, fmt, 'الوفيات (تقدير)')
    num(crisis.totals.injured,   sol.totals.injured,   fmt, 'الإصابات')
    num(crisis.totals.displaced, sol.totals.displaced, fmt, 'النازحون')
    num(crisis.totals.affected,  sol.totals.affected,  fmt, 'المتأثّرون')
  }
  num(peakHospital(crisis), peakHospital(sol), n => `${Math.round(n)}`, 'ذروة إشغال المستشفيات', '٪')
  if (crisis && sol) num(econ(crisis), econ(sol), fmtUsd, 'الأثر الاقتصادي (تقديري)')
  return rows
}

export default function ComparisonDashboard({
  sim, crisisImpact, solutionImpact, synthesis,
}: {
  sim: AbmEvent
  crisisImpact: AbmImpactTimeline | null
  solutionImpact: AbmImpactTimeline | null
  synthesis: string | null
}) {
  const kpis = buildKpis(sim, crisisImpact, solutionImpact)

  // headline wins
  const riskRed = Math.round(sim.risk_reduction ?? 0)
  const casPrev = (crisisImpact?.totals.casualties ?? 0) - (solutionImpact?.totals.casualties ?? 0)
  const dispAvoid = (crisisImpact?.totals.displaced ?? 0) - (solutionImpact?.totals.displaced ?? 0)

  // governorate bars
  const beforeGov = byGovPeak(crisisImpact)
  const afterGov = byGovPeak(solutionImpact)
  const govKeys = Array.from(new Set([...beforeGov.keys(), ...afterGov.keys()]))
  const maxAffected = Math.max(1, ...govKeys.map(k => beforeGov.get(k)?.affected ?? 0))
  const govRows = govKeys
    .map(k => ({
      gov: k,
      name_ar: beforeGov.get(k)?.name_ar ?? afterGov.get(k)?.name_ar ?? k,
      before: beforeGov.get(k)?.affected ?? 0,
      after: afterGov.get(k)?.affected ?? 0,
    }))
    .sort((a, b) => b.before - a.before)

  return (
    <div className="space-y-5">
      {/* headline banner */}
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
        className="rounded-xl border border-good/30 bg-gradient-to-l from-good/10 to-transparent p-5">
        <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-txt" dir="auto">
          <TrendingDown className="h-4 w-4 text-good" /> أثر التدخّل — ملخّص المقارنة
        </div>
        {synthesis && <p className="mb-3 text-[13px] leading-relaxed text-muted" dir="rtl">{synthesis}</p>}
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
          <WinStat label="انخفاض مؤشّر الخطر" value={`${riskRed} نقطة`} />
          <WinStat label="وفيات يمكن تفاديها" value={fmt(Math.max(0, casPrev))} />
          <WinStat label="نزوح يمكن تفاديه" value={fmt(Math.max(0, dispAvoid))} />
        </div>
      </motion.div>

      {/* before/after KPI grid */}
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
        className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
          <Activity className="h-3.5 w-3.5" /> المؤشّرات: قبل التدخّل ← بعد التدخّل
        </div>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {kpis.map((k) => (
            <div key={k.label} className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-soft/30 px-4 py-3">
              <span className="text-[12.5px] text-txt" dir="auto">{k.label}</span>
              <div className="flex items-center gap-2">
                <span className="rounded-md bg-danger/10 px-2 py-1 font-mono text-[13px] font-semibold text-danger">{k.before}</span>
                <ArrowLeft className="h-3.5 w-3.5 text-faint" />
                <span className="rounded-md bg-good/10 px-2 py-1 font-mono text-[13px] font-semibold text-good">{k.after}</span>
                {k.reductionPct !== null ? (
                  <span className={`flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    k.reductionPct > 0 ? 'bg-good/15 text-good' : k.reductionPct < 0 ? 'bg-danger/15 text-danger' : 'bg-soft text-faint'
                  }`}>
                    {k.reductionPct > 0 ? '↓' : k.reductionPct < 0 ? '↑' : ''} {Math.abs(k.reductionPct)}٪
                  </span>
                ) : (
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${k.betterAfter ? 'bg-good/15 text-good' : 'bg-soft text-faint'}`}>
                    {k.betterAfter ? 'تحسّن' : '—'}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[10px] text-faint" dir="rtl">
          الأثر الاقتصادي تقدير مشتق (قيمة الحياة + تكلفة النزوح + الاضطراب) — لدعم القرار لا قياسًا فعليًّا.
        </p>
      </motion.div>

      {/* before/after trajectory charts */}
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
        className="rounded-xl border border-border bg-card p-5">
        <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-txt" dir="auto">
          <Activity className="h-4 w-4 text-blue" /> مسار الأزمة: قبل وبعد التدخّل
        </div>
        <ScenarioCharts sim={sim as unknown as ScenarioEvent} />
      </motion.div>

      {/* affected-area governorate bars */}
      {govRows.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border bg-card p-5">
          <div className="mb-4 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
            <MapPin className="h-3.5 w-3.5" /> المناطق المتأثّرة — قبل (أحمر) مقابل بعد (أخضر)
          </div>
          <div className="space-y-3">
            {govRows.map((g) => (
              <div key={g.gov}>
                <div className="mb-1 flex items-center justify-between text-[11px]" dir="rtl">
                  <span className="text-txt">{g.name_ar}</span>
                  <span className="font-mono text-faint">{fmt(g.before)} ← {fmt(g.after)}</span>
                </div>
                <div className="space-y-1">
                  <div className="h-2 rounded-full bg-soft/50">
                    <div className="h-full rounded-full bg-danger/70" style={{ width: `${(g.before / maxAffected) * 100}%` }} />
                  </div>
                  <div className="h-2 rounded-full bg-soft/50">
                    <div className="h-full rounded-full bg-good/70" style={{ width: `${(g.after / maxAffected) * 100}%` }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  )
}

function WinStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-good/20 bg-card px-3 py-2.5">
      <div className="text-[10px] text-faint" dir="auto">{label}</div>
      <div className="mt-0.5 font-mono text-[18px] font-bold text-good">{value}</div>
    </div>
  )
}
