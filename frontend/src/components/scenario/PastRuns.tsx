import { motion } from 'motion/react'
import { History } from 'lucide-react'
import type { ScenarioPastRun } from '../../lib/voc'

export default function PastRuns({ runs, total }: { runs: ScenarioPastRun[]; total?: number }) {
  if (!runs.length) return null
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl border border-border bg-card p-4"
    >
      <div className="mb-2.5 flex flex-wrap items-center gap-2">
        <History className="h-4 w-4 text-blue" />
        <h2 className="text-[14px] font-semibold text-txt" dir="auto">محاكاة سابقة مشابهة</h2>
        <span className="text-[12px] text-faint" dir="auto">
          · سبق أن حاكيت {runs.length} موقفًا مشابهًا{typeof total === 'number' ? ` (إجمالي ${total})` : ''}
        </span>
      </div>
      <div className="space-y-2">
        {runs.map((r) => (
          <div
            key={r.id}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border bg-bg px-3 py-2 text-[12.5px]"
          >
            <span className="max-w-[44ch] truncate text-txt" dir="auto">{r.text}</span>
            {r.severity_ar && <span className="text-faint" dir="auto">شدّة: {r.severity_ar}</span>}
            {r.likely_outcome_ar && <span className="text-faint" dir="auto">النتيجة: {r.likely_outcome_ar}</span>}
            {r.confidence_band_ar && <span className="text-faint" dir="auto">ثقة: {r.confidence_band_ar}</span>}
            {r.ts && <span className="ms-auto font-mono text-faint">{r.ts.slice(0, 10)}</span>}
          </div>
        ))}
      </div>
    </motion.div>
  )
}
