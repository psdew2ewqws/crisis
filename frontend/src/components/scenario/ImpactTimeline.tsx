// ImpactTimeline — renders a concrete step-by-step crisis impact simulation:
// what actually happens over time (Hour 0 → Day 3 → Week 1 …), with casualties,
// displaced, hospital load and a per-phase narrative. Used for both the crisis
// (no intervention) and the solution (intervention) timelines. Arabic-first.

import { motion } from 'motion/react'
import { Users, HeartPulse, Home, Activity } from 'lucide-react'
import type { AbmImpactTimeline, AbmImpactStep } from '../../lib/voc'

const PHASE_TONE: Record<string, string> = {
  impact:   'border-danger/50 bg-danger/10 text-danger',
  response: 'border-warn/50 bg-warn/10 text-warn',
  relief:   'border-blue/50 bg-blue/10 text-blue',
  recovery: 'border-good/50 bg-good/10 text-good',
}
const PHASE_DOT: Record<string, string> = {
  impact: 'bg-danger', response: 'bg-warn', relief: 'bg-blue', recovery: 'bg-good',
}

const fmt = (n: number) => n.toLocaleString('en-US')

function StepRow({ s }: { s: AbmImpactStep }) {
  return (
    <div className="relative pb-5 ps-6">
      {/* timeline rail dot */}
      <span className={`absolute right-0 top-1 h-3 w-3 -translate-x-1/2 rounded-full ring-4 ring-card ${PHASE_DOT[s.phase] ?? 'bg-muted'}`}
        style={{ insetInlineStart: '-1.5px', insetInlineEnd: 'auto' }} />
      <div className="rounded-lg border border-border bg-soft/30 p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-faint">{s.t}</span>
            <span className="text-[13px] font-semibold text-txt" dir="rtl">{s.label_ar}</span>
          </div>
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${PHASE_TONE[s.phase] ?? 'border-border text-faint'}`}>
            {s.phase}
          </span>
        </div>

        {/* concrete impact metrics */}
        <div className="mb-2 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
          <Metric icon={Users}      label="متأثّرون"      value={fmt(s.affected)}  tone="text-txt" />
          <Metric icon={HeartPulse} label="وفيات (تقدير)" value={fmt(s.casualties)} tone="text-danger" />
          <Metric icon={Activity}   label="إصابات"        value={fmt(s.injured)}   tone="text-warn" />
          <Metric icon={Home}       label="نازحون"        value={fmt(s.displaced)} tone="text-blue" />
        </div>

        {/* hospital load bar */}
        <div className="mb-2 flex items-center gap-2">
          <span className="text-[10px] text-faint" dir="auto">إشغال المستشفيات</span>
          <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-border">
            <div className={`h-full rounded-full ${s.hospital_load_pct > 100 ? 'bg-danger' : s.hospital_load_pct > 70 ? 'bg-warn' : 'bg-good'}`}
              style={{ width: `${Math.min(100, s.hospital_load_pct)}%` }} />
          </div>
          <span className={`font-mono text-[10px] ${s.hospital_load_pct > 100 ? 'text-danger' : 'text-muted'}`}>
            {s.hospital_load_pct}%
          </span>
        </div>

        {s.infrastructure && (
          <p className="mb-1 text-[11px] text-faint" dir="rtl">🏗 {s.infrastructure}</p>
        )}
        <p className="text-[12.5px] leading-relaxed text-txt" dir="rtl">{s.narrative_ar}</p>

        {/* per-governorate breakdown */}
        {s.by_gov.length > 1 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {s.by_gov.map((g) => (
              <span key={g.gov} className="rounded border border-border/60 bg-card px-1.5 py-0.5 text-[10px] text-muted" dir="rtl">
                {g.name_ar}: {fmt(g.affected)}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function Metric({ icon: Icon, label, value, tone }: {
  icon: typeof Users; label: string; value: string; tone: string
}) {
  return (
    <div className="rounded border border-border/50 bg-card px-2 py-1">
      <div className="flex items-center gap-1 text-[9px] text-faint" dir="auto">
        <Icon className="h-3 w-3" />{label}
      </div>
      <div className={`font-mono text-[13px] font-semibold ${tone}`}>{value}</div>
    </div>
  )
}

export default function ImpactTimeline({
  timeline, accent,
}: { timeline: AbmImpactTimeline; accent: 'crisis' | 'solution' }) {
  const t = timeline
  const tot = t.totals
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border bg-card p-5">
      <div className="mb-1 flex items-center justify-between gap-2">
        <h3 className="text-[14px] font-semibold text-txt" dir="auto">
          {accent === 'crisis' ? 'المسار الفعلي للأزمة — بدون تدخّل' : 'المسار الفعلي مع التدخّل والحلّ'}
        </h3>
        <span className="rounded bg-soft px-1.5 py-0.5 font-mono text-[10px] text-faint">
          {t.engine === 'llm' ? 'AI + data' : 'data model'} · {t.domain}
        </span>
      </div>
      <p className="mb-3 text-[11px] text-faint" dir="auto">
        السكان المعرّضون: {fmt(t.exposed_population)} · المحافظات: {t.affected_governorates.join('، ')}
      </p>

      {/* peak totals */}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <PeakStat label="ذروة المتأثّرين" value={fmt(tot.affected)} tone="text-txt" />
        <PeakStat label="إجمالي الوفيات" value={fmt(tot.casualties)} tone="text-danger" />
        <PeakStat label="إجمالي الإصابات" value={fmt(tot.injured)} tone="text-warn" />
        <PeakStat label="ذروة النازحين" value={fmt(tot.displaced)} tone="text-blue" />
      </div>

      {/* vertical timeline */}
      <div className="relative border-e-2 border-border pe-1" style={{ marginInlineStart: '4px' }}>
        {t.steps.map((s, i) => <StepRow key={i} s={s} />)}
      </div>

      <p className="mt-1 text-[10px] leading-relaxed text-faint" dir="rtl">{t.method_note_ar}</p>
    </motion.div>
  )
}

function PeakStat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-lg border border-border/60 bg-soft/40 px-3 py-2">
      <div className="text-[10px] text-faint" dir="auto">{label}</div>
      <div className={`mt-0.5 font-mono text-[16px] font-semibold ${tone}`}>{value}</div>
    </div>
  )
}
