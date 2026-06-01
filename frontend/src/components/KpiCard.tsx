import { ArrowUpRight, ArrowDownRight } from 'lucide-react'
import type { Kpi, Tone } from '../lib/data'

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

export default function KpiCard({ kpi }: { kpi: Kpi }) {
  const Arrow = kpi.trend.dir === 'up' ? ArrowUpRight : ArrowDownRight
  return (
    <div className="rounded-xl border border-border bg-card p-5 transition-colors hover:border-border/80 hover:bg-cardhi">
      <div className="flex items-center justify-between">
        <span className="text-[13px] text-muted">{kpi.title}</span>
        <span
          className={`rounded-md border px-2 py-0.5 font-mono text-[11px] font-medium tnum ${badgeTone[kpi.badge.tone]}`}
        >
          {kpi.badge.text}
        </span>
      </div>
      <div className="mt-3 flex items-end gap-1.5">
        <span className="text-[40px] font-semibold leading-none tracking-tight text-txt tnum">
          {kpi.value}
        </span>
        {kpi.unit && <span className="pb-1.5 text-[15px] text-muted">{kpi.unit}</span>}
      </div>
      <div className={`mt-3 flex items-center gap-1.5 text-[13px] ${trendTone[kpi.trend.tone]}`}>
        <span className="text-txt">{kpi.trend.text}</span>
        <Arrow className="h-4 w-4" />
      </div>
      <div className="mt-1 text-[12.5px] text-faint">{kpi.sub}</div>
    </div>
  )
}
