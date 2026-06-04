import { motion } from 'motion/react'
import { CheckCircle2, XCircle, History } from 'lucide-react'
import type { ScenarioCitation } from '../../lib/voc'

interface PrecedentCardsProps {
  cases: ScenarioCitation[]
  bestRelevance?: number
}

/** "تقديري" | "محاكاة" | "مقيس" — neutral risk-source chip. */
function riskSourceLabel(c: ScenarioCitation): string {
  return c.risk_source_ar ?? c.risk_source ?? 'تقديري'
}

export default function PrecedentCards({ cases, bestRelevance }: PrecedentCardsProps) {
  if (cases.length === 0) {
    return (
      <section>
        <header className="mb-4 flex items-center gap-2.5">
          <History className="h-4 w-4 text-faint" />
          <h2 className="text-[15px] font-semibold text-txt" dir="auto">السوابق التاريخية</h2>
          <span className="text-[12px] uppercase tracking-wide text-faint">· RETRIEVED PRECEDENTS</span>
        </header>
        <div className="rounded-xl border border-border bg-card p-10 text-center">
          <p dir="auto" className="text-[13px] text-faint">
            لا توجد سوابق تاريخية قريبة لهذا الموقف
          </p>
        </div>
      </section>
    )
  }

  // Scale relevance to [0..1] against the best retrieved relevance (fallback 1).
  const denom = bestRelevance && bestRelevance > 0 ? bestRelevance : 1

  return (
    <section>
      <header className="mb-4 flex items-center gap-2.5">
        <History className="h-4 w-4 text-faint" />
        <h2 className="text-[15px] font-semibold text-txt">السوابق التاريخية</h2>
        <span className="text-[12px] uppercase tracking-wide text-faint">· RETRIEVED PRECEDENTS</span>
        <span className="ml-auto rounded-full border border-border bg-cardhi px-2.5 py-0.5 text-[12px] font-medium text-muted tnum">
          {cases.length}
        </span>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {cases.map((c, i) => {
          const success = c.kind === 'success'
          const failure = c.kind === 'failure'
          const rel = typeof c.relevance === 'number' ? Math.max(0, Math.min(1, c.relevance / denom)) : 0

          return (
            <motion.article
              key={`${c.source_case_id ?? 'case'}-${i}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: Math.min(i * 0.05, 0.4) }}
              className="flex flex-col rounded-xl border border-border bg-card p-5 transition-colors hover:bg-cardhi"
            >
              {/* Top row: kind tag · ts · risk-source chip */}
              <div className="mb-3 flex items-center gap-2">
                {success && (
                  <span dir="auto" className="inline-flex items-center gap-1 rounded-full border border-good/30 bg-good/10 px-2 py-0.5 text-[12px] font-medium text-good">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    نجح
                  </span>
                )}
                {failure && (
                  <span dir="auto" className="inline-flex items-center gap-1 rounded-full border border-danger/30 bg-danger/10 px-2 py-0.5 text-[12px] font-medium text-danger">
                    <XCircle className="h-3.5 w-3.5" />
                    فشل
                  </span>
                )}

                {c.ts && <span className="font-mono text-[12px] text-faint tnum">{c.ts}</span>}

                <span
                  dir="auto"
                  className="ml-auto inline-flex items-center rounded-full border border-border bg-cardhi px-2 py-0.5 text-[12px] font-medium text-muted"
                >
                  {riskSourceLabel(c)}
                </span>
              </div>

              {/* Body: lesson text */}
              <p dir="auto" className="line-clamp-3 flex-1 text-[13px] leading-relaxed text-muted">
                {c.lesson ?? c.outcome_ar ?? c.outcome ?? '—'}
              </p>

              {/* Footer: source case id · relevance mini-bar */}
              <div className="mt-4 flex items-center gap-3">
                <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-faint">
                  {c.source_case_id ?? '—'}
                </span>
                <div className="h-1 w-16 shrink-0 overflow-hidden rounded-full bg-soft" title={`${(rel * 100).toFixed(1)}%`}>
                  <div className="h-full rounded-full bg-blue" style={{ width: `${rel * 100}%` }} />
                </div>
              </div>
            </motion.article>
          )
        })}
      </div>
    </section>
  )
}
