// JordanDroughtStudy — the cited, multi-sector "no rain for 1 year" study, rendered when
// the engine routes to the WEF-nexus cascade. Shows sector stress, the Monte-Carlo band,
// and real-data charts (dam collapse, crop loss). Honest framing: structured what-if, not
// a calibrated prediction. Every number here came seeded from sourced baseline constants.

import { useMemo } from 'react'
import { motion } from 'motion/react'
import { Droplets, AlertTriangle } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ScenarioEvent } from '../../lib/voc'

const SECTOR_AR: Record<string, string> = {
  water_supply: 'إمداد المياه',
  agriculture: 'الزراعة',
  groundwater: 'المياه الجوفية',
  social: 'التوتر الاجتماعي',
}
const TOOLTIP = {
  contentStyle: { background: '#131417', border: '1px solid #212228', borderRadius: 10, fontSize: 12 },
  labelStyle: { color: '#8B8D96' },
  itemStyle: { color: '#ECEDEE' },
}

function num(v: unknown, d = 0): number {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : d
}

function StressBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  const tone = pct >= 70 ? 'bg-danger' : pct >= 42 ? 'bg-warn' : 'bg-good'
  const txt = pct >= 70 ? 'text-danger' : pct >= 42 ? 'text-warn' : 'text-good'
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[12.5px]">
        <span className="text-muted" dir="auto">{label}</span>
        <span className={`tnum font-medium ${txt}`}>{pct}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-soft">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function JordanDroughtStudy({ sim }: { sim: ScenarioEvent }) {
  const sectors = sim.sectors_after || {}
  const mc = sim.montecarlo || {}
  const deficit = Math.round((1 - num(sim.rainfall_ratio, 1)) * 100)

  const damData = useMemo(() => {
    const v = (sim.baseline?.dam_storage_mcm?.value || {}) as Record<string, number>
    const labels: Record<string, string> = { '2023': '2023', '2024': '2024', '2025_nov': 'نوفمبر 2025' }
    return Object.keys(v).map((k) => ({ name: labels[k] ?? k, mcm: num(v[k]) }))
  }, [sim.baseline])

  const cropData = useMemo(() => {
    const v = (sim.baseline?.crop_loss_pct?.value || {}) as Record<string, number>
    const labels: Record<string, string> = { wheat: 'قمح', barley: 'شعير', olives: 'زيتون' }
    return Object.keys(v).map((k) => ({ name: labels[k] ?? k, loss: Math.abs(num(v[k])) }))
  }, [sim.baseline])

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl border border-border bg-card p-5"
    >
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <Droplets className="h-4 w-4 text-blue" />
        <h2 className="text-[15px] font-semibold text-txt" dir="auto">دراسة جفاف الأردن</h2>
        <span className="text-[12px] uppercase tracking-wide text-faint">· JORDAN DROUGHT STUDY</span>
        <span className="ms-auto rounded-md border border-warn/30 bg-warn/10 px-2 py-0.5 text-[11.5px] text-warn tnum" dir="auto">
          عجز الأمطار {deficit}%
        </span>
      </div>
      {sim.label && <p className="mb-4 text-[12px] text-faint" dir="auto">{sim.label}</p>}

      {/* sector stress */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {Object.keys(sectors).map((k) => (
          <StressBar key={k} label={SECTOR_AR[k] ?? k} value={num(sectors[k])} />
        ))}
      </div>

      {/* Monte-Carlo band */}
      {mc.available && (
        <div className="mt-5 rounded-lg border border-border bg-bg p-3">
          <div className="mb-2 text-[12px] uppercase tracking-wide text-faint" dir="auto">
            نطاق عدم اليقين · MONTE-CARLO (N={mc.n})
          </div>
          <div className="flex items-center gap-3 text-[13px]">
            <span className="text-faint" dir="auto">متفائل P10</span>
            <span className="tnum text-good">{mc.p10}</span>
            <div className="relative h-2 flex-1 rounded-full bg-soft">
              <div className="absolute inset-y-0 rounded-full bg-blue/40"
                   style={{ left: `${num(mc.p10)}%`, right: `${100 - num(mc.p90)}%` }} />
              <div className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 bg-txt"
                   style={{ left: `${num(mc.p50)}%` }} title={`P50 ${mc.p50}`} />
            </div>
            <span className="tnum text-danger">{mc.p90}</span>
            <span className="text-faint" dir="auto">متشائم P90</span>
          </div>
          <div className="mt-1 text-[11.5px] text-faint" dir="auto">الوسيط P50 = {mc.p50} · الاتساع {mc.spread}</div>
        </div>
      )}

      {/* real-data charts */}
      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {damData.length > 0 && (
          <div className="rounded-lg border border-border bg-bg p-4">
            <div className="mb-3 text-[13px] font-semibold text-txt" dir="auto">تراجع تخزين السدود (مليون م³)</div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={damData} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid stroke="#1A1B20" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#62646D', fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#62646D', fontSize: 11 }} tickLine={false} axisLine={false} width={44} />
                <Tooltip {...TOOLTIP} formatter={(v) => [`${num(v)} م³`, 'تخزين']} />
                <Bar dataKey="mcm" radius={[4, 4, 0, 0]}>
                  {damData.map((_, i) => (
                    <Cell key={i} fill={i === damData.length - 1 ? '#F04359' : '#3B82F6'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        {cropData.length > 0 && (
          <div className="rounded-lg border border-border bg-bg p-4">
            <div className="mb-3 text-[13px] font-semibold text-txt" dir="auto">خسارة المحاصيل (% من الغلّة)</div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={cropData} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid stroke="#1A1B20" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#62646D', fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#62646D', fontSize: 11 }} tickLine={false} axisLine={false} width={36} />
                <Tooltip {...TOOLTIP} formatter={(v) => [`−${num(v)}%`, 'خسارة']} />
                <Bar dataKey="loss" fill="#FBBF24" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* non-mitigating note */}
      {sim.non_mitigating && sim.non_mitigating.length > 0 && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-warn/30 bg-warn/10 p-3 text-[12.5px] text-warn" dir="auto">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>لا يخفّف الأزمة خلال السنة: {sim.non_mitigating.join('، ')}.</span>
        </div>
      )}
    </motion.div>
  )
}
