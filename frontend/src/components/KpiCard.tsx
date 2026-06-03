import { ArrowUpRight, ArrowDownRight, Info } from 'lucide-react'
import { motion } from 'motion/react'
import type { Kpi, Tone } from '../lib/data'

// Plain-language explainer for the dashboard KPIs, matched by keyword so it holds up
// regardless of the exact title the backend returns. Surfaced as a hover tooltip.
function kpiHelp(title: string): string | undefined {
  const t = title.toLowerCase()
  if (t.includes('cluster') || t.includes('root')) return 'Active RIL problem clusters — grouped root causes, ranked by size × severity.'
  if (t.includes('critical') || t.includes('high')) return 'Citizen signals flagged high or critical by severity.'
  if (t.includes('service')) return 'Distinct government services with signals in the current scope.'
  if (t.includes('signal')) return 'Total citizen reports in the voc360 database (the_data) for the current scope.'
  return undefined
}

const badgeTone: Record<Tone, string> = {
  danger: 'text-danger border-danger/30 bg-danger/10',
  good: 'text-good border-good/30 bg-good/10',
  warn: 'text-warn border-warn/30 bg-warn/10',
  neutral: 'text-muted border-border bg-soft',
}
const trendTone: Record<Tone, string> = {
  danger: 'text-danger',
  good: 'text-good',
  warn: 'text-warn',
  neutral: 'text-muted',
}
// Tone-tinted accent used for the hairline top edge + a soft corner glow on hover.
const accent: Record<Tone, string> = {
  danger: 'from-danger/70',
  good: 'from-good/70',
  warn: 'from-warn/70',
  neutral: 'from-blue/60',
}
// baseline accent bar colour per tone (21st.dev KPI-card touch)
const barTone: Record<Tone, string> = {
  danger: 'bg-danger/60',
  good: 'bg-good/60',
  warn: 'bg-warn/60',
  neutral: 'bg-blue/50',
}

export default function KpiCard({ kpi, index = 0 }: { kpi: Kpi; index?: number }) {
  const Arrow = kpi.trend.dir === 'up' ? ArrowUpRight : ArrowDownRight
  const tone = kpi.badge.tone
  const help = kpiHelp(kpi.title)
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.4, ease: 'easeOut' }}
      whileHover={{ y: -3 }}
      className="group relative overflow-hidden rounded-xl border border-border bg-card p-5 transition-[border-color,background-color,box-shadow] duration-200 hover:border-border/80 hover:bg-cardhi hover:shadow-xl hover:shadow-black/20"
    >
      {/* tone-tinted hairline along the top edge */}
      <div
        className={`pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r to-transparent ${accent[tone]}`}
      />
      {/* soft corner glow, revealed on hover */}
      <div
        className={`pointer-events-none absolute -right-10 -top-10 h-24 w-24 rounded-full bg-gradient-to-br to-transparent opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-50 ${accent[tone]}`}
      />
      {/* stacked corner-pulse rings (21st.dev KPI-card detail) */}
      <span className="pointer-events-none absolute -right-6 -top-6 h-16 w-16 rounded-full bg-txt/[0.04]" />
      <span className="pointer-events-none absolute -right-2 -top-2 h-8 w-8 rounded-full bg-txt/[0.04]" />

      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-[13px] text-muted">
          {kpi.title}
          {help && (
            <span title={help} aria-label={help} className="cursor-help text-faint transition-colors hover:text-muted">
              <Info className="h-3.5 w-3.5" />
            </span>
          )}
        </span>
        <span
          className={`rounded-md border px-2 py-0.5 font-mono text-[11px] font-medium tnum ${badgeTone[tone]}`}
        >
          {kpi.badge.text}
        </span>
      </div>

      <div className="mt-3.5 flex items-end gap-1.5">
        <span className="text-[42px] font-semibold leading-none tracking-[-0.02em] text-txt tnum">
          {kpi.value}
        </span>
        {kpi.unit && <span className="pb-1.5 text-[15px] text-muted">{kpi.unit}</span>}
      </div>

      <div className="mt-3.5 flex items-center justify-between">
        <span
          className={`inline-flex items-center gap-1.5 rounded-md bg-soft/70 px-2 py-1 text-[12.5px] font-medium ${trendTone[kpi.trend.tone]}`}
        >
          <Arrow className="h-3.5 w-3.5" />
          {kpi.trend.text}
        </span>
        <span className="truncate pl-3 text-right text-[12px] text-faint">{kpi.sub}</span>
      </div>

      {/* tiny baseline accent bar (21st.dev KPI-card touch) */}
      <div className={`mt-3 h-0.5 w-14 rounded-full opacity-70 ${barTone[tone]}`} />
    </motion.div>
  )
}
