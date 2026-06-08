// CaseStudiesPanel — shows historical crisis precedents from ai_case_studies DB.
// Cases are sorted by geographic proximity: Jordan first, then Middle East, then global.
// Each card shows crisis description, real impact figures, and proven solutions.

import { motion } from 'motion/react'
import { BookMarked, MapPin, Lightbulb, AlertTriangle } from 'lucide-react'
import type { AbmCaseStudy } from '../../lib/voc'

const GEO_BADGE: Record<number, { label: string; cls: string }> = {
  0: { label: 'Jordan',       cls: 'border-good/40 bg-good/10 text-good' },
  1: { label: 'Middle East',  cls: 'border-blue/40 bg-blue/10 text-blue' },
  2: { label: 'Global',       cls: 'border-border bg-soft text-faint' },
}

function fmt(n?: number | null): string {
  if (!n) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

export default function CaseStudiesPanel({ cases }: { cases: AbmCaseStudy[] }) {
  if (!cases.length) return null
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <BookMarked className="h-4 w-4 text-blue" />
        <h3 className="text-[14px] font-semibold text-txt" dir="auto">الحالات التاريخية المشابهة</h3>
        <span className="text-[12px] uppercase tracking-wide text-faint">· HISTORICAL PRECEDENTS</span>
        <span className="ms-auto rounded-full border border-border px-2 py-0.5 text-[11px] text-muted">
          {cases.length} حالة
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {cases.map((c) => {
          const geo = GEO_BADGE[c.geo_tier] ?? GEO_BADGE[2]
          const nums = c.impact_numbers
          return (
            <div key={c.id}
              className="flex flex-col rounded-lg border border-border bg-bg p-3 gap-2">
              {/* header */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-[12.5px] font-semibold leading-snug text-txt line-clamp-2" dir="auto">
                    {c.title}
                  </p>
                  <div className="mt-1 flex items-center gap-1.5 text-[10.5px] text-faint">
                    <MapPin className="h-3 w-3 shrink-0" />
                    <span className="truncate">{c.country}</span>
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <span className={`rounded border px-1.5 py-0.5 text-[9px] font-medium ${geo.cls}`}>
                    {geo.label}
                  </span>
                  <span className="rounded bg-soft px-1.5 py-0.5 text-[9px] text-faint">
                    {c.disaster_type}
                  </span>
                </div>
              </div>

              {/* real impact numbers when extracted */}
              {(nums.deaths || nums.displaced || nums.affected) && (
                <div className="flex flex-wrap gap-1.5">
                  {nums.deaths && (
                    <span className="rounded border border-danger/30 bg-danger/10 px-2 py-0.5 text-[10px] text-danger">
                      {fmt(nums.deaths)} وفاة
                    </span>
                  )}
                  {nums.displaced && (
                    <span className="rounded border border-blue/30 bg-blue/10 px-2 py-0.5 text-[10px] text-blue">
                      {fmt(nums.displaced)} نازح
                    </span>
                  )}
                  {nums.affected && (
                    <span className="rounded border border-warn/30 bg-warn/10 px-2 py-0.5 text-[10px] text-warn">
                      {fmt(nums.affected)} متأثّر
                    </span>
                  )}
                </div>
              )}

              {/* what happened */}
              {c.crisis && (
                <div>
                  <div className="mb-0.5 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-faint">
                    <AlertTriangle className="h-3 w-3" /> ما حدث
                  </div>
                  <p className="text-[11.5px] leading-relaxed text-muted line-clamp-3" dir="auto">
                    {c.crisis}
                  </p>
                </div>
              )}

              {/* what worked */}
              {c.solution && (
                <div className="mt-auto">
                  <div className="mb-0.5 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-good">
                    <Lightbulb className="h-3 w-3" /> الحلّ الموثّق
                  </div>
                  <p className="text-[11.5px] leading-relaxed text-txt line-clamp-3" dir="auto">
                    {c.solution}
                  </p>
                </div>
              )}

              <div className="text-[9px] text-faint uppercase">{c.source_site}</div>
            </div>
          )
        })}
      </div>
    </motion.div>
  )
}
