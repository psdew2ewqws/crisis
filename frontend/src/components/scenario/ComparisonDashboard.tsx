// ComparisonDashboard — the redesigned "Before vs After" view (لوحة المقارنة).
// Clean, understandable charts built from already-streamed data:
//   1. Headline banner (3 biggest wins)
//   2. KPI comparison cards (before → after + delta)
//   3. "% reduction by metric" horizontal bar chart (uniform 0-100 scale)
//   4. Risk-over-time line chart (before vs after trajectory)
//   5. Affected-area governorate bars (before vs after)
// All Jordan-based; population shown in context.

import { motion } from 'motion/react'
import {
  TrendingDown, MapPin, HeartPulse, Home, Users, Building2, Activity, Gauge,
} from 'lucide-react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import type { AbmEvent, AbmImpactTimeline } from '../../lib/voc'

const SEV_AR: Record<string, string> = { low: 'منخفضة', elevated: 'مرتفعة', critical: 'حرجة' }
const SEV_RANK: Record<string, number> = { low: 0, elevated: 1, critical: 2 }
const C_DEATH = 1_500_000, C_DISP = 2_000, C_AFFECT = 200

const fmt = (n: number) =>
  !isFinite(n) ? '—'
  : Math.abs(n) >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M`
  : Math.abs(n) >= 1_000 ? `${(n / 1_000).toFixed(1)}K`
  : Math.round(n).toLocaleString('en-US')
const fmtUsd = (n: number) =>
  n >= 1_000_000_000 ? `$${(n / 1_000_000_000).toFixed(1)}B`
  : n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(0)}M` : `$${fmt(n)}`
const peakHosp = (t: AbmImpactTimeline | null) =>
  t?.steps?.length ? Math.max(...t.steps.map(s => s.hospital_load_pct || 0)) : 0
const econ = (t: AbmImpactTimeline | null) =>
  t?.totals ? t.totals.casualties * C_DEATH + t.totals.displaced * C_DISP + t.totals.affected * C_AFFECT : 0

function byGovPeak(t: AbmImpactTimeline | null): Map<string, { name_ar: string; affected: number }> {
  const m = new Map<string, { name_ar: string; affected: number }>()
  for (const step of t?.steps ?? [])
    for (const g of step.by_gov ?? []) {
      const cur = m.get(g.gov)
      if (!cur || g.affected > cur.affected) m.set(g.gov, { name_ar: g.name_ar, affected: g.affected })
    }
  return m
}

const DASH = '#0d1117'
const RED = '#ef4444', GREEN = '#22c55e', GREY = '#62646D'

export default function ComparisonDashboard({
  sim, crisisImpact, solutionImpact, synthesis,
}: {
  sim: AbmEvent
  crisisImpact: AbmImpactTimeline | null
  solutionImpact: AbmImpactTimeline | null
  synthesis: string | null
}) {
  const rb = sim.risk_before ?? 0, ra = sim.risk_after ?? 0
  const ct = crisisImpact?.totals, st = solutionImpact?.totals
  const exposed = crisisImpact?.exposed_population ?? 0
  const national = crisisImpact?.national_population ?? 0

  // headline wins
  const riskRed = Math.round(sim.risk_reduction ?? 0)
  const casPrev = Math.max(0, (ct?.casualties ?? 0) - (st?.casualties ?? 0))
  const dispAvoid = Math.max(0, (ct?.displaced ?? 0) - (st?.displaced ?? 0))

  // KPI cards
  const sevB = sim.seir_before?.severity ?? 'low', sevA = sim.seir_after?.severity ?? 'low'
  type Kpi = { icon: typeof Users; label: string; before: string; after: string; pct: number | null; better: boolean }
  const pctRed = (a: number, b: number) => (a > 0 ? Math.round(((a - b) / a) * 100) : 0)
  const kpis: Kpi[] = [
    { icon: Gauge, label: 'مؤشّر الخطر', before: `${rb.toFixed(0)}٪`, after: `${ra.toFixed(0)}٪`, pct: pctRed(rb, ra), better: ra <= rb },
    { icon: Activity, label: 'درجة الخطورة', before: SEV_AR[sevB], after: SEV_AR[sevA], pct: null, better: (SEV_RANK[sevA] ?? 0) <= (SEV_RANK[sevB] ?? 0) },
    { icon: HeartPulse, label: 'الوفيات (تقدير)', before: fmt(ct?.casualties ?? 0), after: fmt(st?.casualties ?? 0), pct: pctRed(ct?.casualties ?? 0, st?.casualties ?? 0), better: true },
    { icon: HeartPulse, label: 'الإصابات', before: fmt(ct?.injured ?? 0), after: fmt(st?.injured ?? 0), pct: pctRed(ct?.injured ?? 0, st?.injured ?? 0), better: true },
    { icon: Home, label: 'النازحون', before: fmt(ct?.displaced ?? 0), after: fmt(st?.displaced ?? 0), pct: pctRed(ct?.displaced ?? 0, st?.displaced ?? 0), better: true },
    { icon: Users, label: 'المتأثّرون', before: fmt(ct?.affected ?? 0), after: fmt(st?.affected ?? 0), pct: pctRed(ct?.affected ?? 0, st?.affected ?? 0), better: true },
    { icon: Building2, label: 'ذروة إشغال المستشفيات', before: `${peakHosp(crisisImpact)}٪`, after: `${peakHosp(solutionImpact)}٪`, pct: pctRed(peakHosp(crisisImpact), peakHosp(solutionImpact)), better: true },
    { icon: TrendingDown, label: 'الأثر الاقتصادي (تقديري)', before: fmtUsd(econ(crisisImpact)), after: fmtUsd(econ(solutionImpact)), pct: pctRed(econ(crisisImpact), econ(solutionImpact)), better: true },
  ]

  // reduction-by-metric bar data (uniform 0-100 scale)
  const redData = [
    { name: 'الخطر', v: pctRed(rb, ra) },
    { name: 'الوفيات', v: pctRed(ct?.casualties ?? 0, st?.casualties ?? 0) },
    { name: 'الإصابات', v: pctRed(ct?.injured ?? 0, st?.injured ?? 0) },
    { name: 'النازحون', v: pctRed(ct?.displaced ?? 0, st?.displaced ?? 0) },
    { name: 'إشغال المستشفيات', v: pctRed(peakHosp(crisisImpact), peakHosp(solutionImpact)) },
  ].map(d => ({ ...d, v: Math.max(0, d.v) }))

  // risk-over-time line data (mean_negativity % before vs after)
  const sb = sim.series_before ?? [], sa = sim.series_after ?? []
  const trajLen = Math.max(sb.length, sa.length)
  const traj = Array.from({ length: trajLen }, (_, i) => ({
    step: i,
    before: sb[i] ? Math.round(sb[i].mean_negativity * 100) : null,
    after: sa[i] ? Math.round(sa[i].mean_negativity * 100) : null,
  }))

  // governorate bars
  const bg = byGovPeak(crisisImpact), ag = byGovPeak(solutionImpact)
  const govKeys = Array.from(new Set([...bg.keys(), ...ag.keys()]))
  const maxAff = Math.max(1, ...govKeys.map(k => bg.get(k)?.affected ?? 0))
  const govRows = govKeys.map(k => ({
    name_ar: bg.get(k)?.name_ar ?? ag.get(k)?.name_ar ?? k,
    before: bg.get(k)?.affected ?? 0, after: ag.get(k)?.affected ?? 0,
  })).sort((a, b) => b.before - a.before)

  return (
    <div className="space-y-5">
      {/* headline banner */}
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
        className="rounded-xl border border-good/30 bg-gradient-to-l from-good/10 to-transparent p-5">
        <div className="mb-2 flex items-center gap-2 text-[14px] font-semibold text-txt" dir="auto">
          <TrendingDown className="h-4 w-4 text-good" /> أثر التدخّل — ملخّص المقارنة
        </div>
        {synthesis && <p className="mb-3 text-[13px] leading-relaxed text-muted" dir="rtl">{synthesis}</p>}
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
          <Win label="انخفاض مؤشّر الخطر" value={`${riskRed} نقطة`} />
          <Win label="وفيات يمكن تفاديها" value={fmt(casPrev)} />
          <Win label="نزوح يمكن تفاديه" value={fmt(dispAvoid)} />
        </div>
        {exposed > 0 && (
          <p className="mt-3 text-[11px] text-faint" dir="rtl">
            السكان المعرّضون في المحافظات المتأثّرة: {fmt(exposed)}
            {national > 0 && ` من إجمالي سكان الأردن ${fmt(national)}`}
          </p>
        )}
      </motion.div>

      {/* KPI comparison cards */}
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
        className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
          <Activity className="h-3.5 w-3.5" /> المؤشّرات: قبل ← بعد التدخّل
        </div>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
          {kpis.map((k) => (
            <div key={k.label} className="rounded-lg border border-border/60 bg-soft/30 p-3">
              <div className="mb-2 flex items-center gap-1.5 text-[11px] text-faint" dir="auto">
                <k.icon className="h-3.5 w-3.5" /> {k.label}
              </div>
              <div className="flex items-center justify-between gap-1">
                <div className="text-center">
                  <div className="font-mono text-[15px] font-bold text-danger">{k.before}</div>
                  <div className="text-[8px] text-faint">قبل</div>
                </div>
                <span className="text-faint">←</span>
                <div className="text-center">
                  <div className="font-mono text-[15px] font-bold text-good">{k.after}</div>
                  <div className="text-[8px] text-faint">بعد</div>
                </div>
                {k.pct !== null && (
                  <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${k.pct > 0 ? 'bg-good/15 text-good' : 'bg-soft text-faint'}`}>
                    ↓{Math.abs(k.pct)}٪
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

      {/* reduction-by-metric + risk trajectory: two clean charts side by side */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* % reduction bar chart */}
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border bg-card p-5">
          <div className="mb-3 text-[13px] font-semibold text-txt" dir="auto">نسبة انخفاض الأثر بعد التدخّل (٪)</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={redData} layout="vertical" margin={{ left: 20, right: 30, top: 4, bottom: 4 }}>
              <CartesianGrid horizontal={false} stroke="#1c2333" />
              <XAxis type="number" domain={[0, 100]} tick={{ fill: GREY, fontSize: 11 }} unit="٪" />
              <YAxis type="category" dataKey="name" width={90} tick={{ fill: '#ECEDEE', fontSize: 11 }} />
              <Tooltip cursor={{ fill: '#ffffff08' }}
                contentStyle={{ background: DASH, border: '1px solid #212228', borderRadius: 8, fontSize: 12 }}
                formatter={((v: number) => [`${v}٪`, 'انخفاض']) as never} />
              <Bar dataKey="v" radius={[0, 4, 4, 0]}>
                {redData.map((d, i) => (
                  <Cell key={i} fill={d.v >= 50 ? GREEN : d.v >= 20 ? '#fbbf24' : '#f97316'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* risk trajectory line chart */}
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border bg-card p-5">
          <div className="mb-3 text-[13px] font-semibold text-txt" dir="auto">مسار الخطر عبر الزمن — قبل مقابل بعد</div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={traj} margin={{ left: 4, right: 12, top: 4, bottom: 4 }}>
              <CartesianGrid stroke="#1c2333" />
              <XAxis dataKey="step" tick={{ fill: GREY, fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: GREY, fontSize: 11 }} unit="٪" />
              <Tooltip contentStyle={{ background: DASH, border: '1px solid #212228', borderRadius: 8, fontSize: 12 }}
                formatter={((v: number, k: string) => [`${v}٪`, k === 'before' ? 'دون تدخّل' : 'مع التدخّل']) as never}
                labelFormatter={(l) => `الخطوة ${l}`} />
              <Line type="monotone" dataKey="before" stroke={RED} strokeWidth={2} dot={false} strokeDasharray="5 3" connectNulls />
              <Line type="monotone" dataKey="after" stroke={GREEN} strokeWidth={2.5} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
          <div className="mt-2 flex items-center gap-4 text-[10px] text-faint">
            <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-4 bg-danger" /> دون تدخّل</span>
            <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-4 bg-good" /> مع التدخّل</span>
          </div>
        </motion.div>
      </div>

      {/* affected-area governorate bars */}
      {govRows.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border bg-card p-5">
          <div className="mb-4 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
            <MapPin className="h-3.5 w-3.5" /> المتأثّرون حسب المحافظة — قبل (أحمر) مقابل بعد (أخضر)
          </div>
          <div className="space-y-3">
            {govRows.map((g) => (
              <div key={g.name_ar}>
                <div className="mb-1 flex items-center justify-between text-[11px]" dir="rtl">
                  <span className="text-txt">{g.name_ar}</span>
                  <span className="font-mono text-faint">{fmt(g.before)} ← {fmt(g.after)}</span>
                </div>
                <div className="space-y-1">
                  <div className="h-2 rounded-full bg-soft/50"><div className="h-full rounded-full" style={{ width: `${(g.before / maxAff) * 100}%`, background: RED }} /></div>
                  <div className="h-2 rounded-full bg-soft/50"><div className="h-full rounded-full" style={{ width: `${(g.after / maxAff) * 100}%`, background: GREEN }} /></div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  )
}

function Win({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-good/20 bg-card px-3 py-2.5">
      <div className="text-[10px] text-faint" dir="auto">{label}</div>
      <div className="mt-0.5 font-mono text-[20px] font-bold text-good">{value}</div>
    </div>
  )
}
