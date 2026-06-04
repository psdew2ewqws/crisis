import { motion } from 'motion/react'
import { CheckCircle2, AlertTriangle, Sparkles } from 'lucide-react'
import type { ScenarioSolutionEval } from '../../lib/voc'

const ALIGN_TONE: Record<string, string> = {
  aligned_with_success: 'border-good/30 bg-good/10 text-good',
  matches_anti_pattern: 'border-warn/30 bg-warn/10 text-warn',
  novel: 'border-border bg-soft text-muted',
}
const BAND_TONE: Record<string, string> = { high: 'text-good', medium: 'text-warn', low: 'text-muted' }

function Metric({
  label,
  value,
  tone = 'text-txt',
  signed = false,
}: {
  label: string
  value?: number | null
  tone?: string
  signed?: boolean
}) {
  const v = typeof value === 'number' ? value : null
  return (
    <div>
      <div className="text-[11.5px] text-faint" dir="auto">{label}</div>
      <div className={`text-[20px] font-semibold tnum ${tone}`}>
        {v === null ? '—' : `${signed && v > 0 ? '−' : ''}${Math.abs(v).toFixed(1)}`}
      </div>
    </div>
  )
}

export default function SolutionEval({ ev }: { ev: ScenarioSolutionEval }) {
  const er = ev.expected_results || {}
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl border border-border bg-card p-5"
    >
      <div className="mb-4 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-blue" />
        <h2 className="text-[15px] font-semibold text-txt" dir="auto">تقييم الحل المقترح</h2>
        <span className="text-[12px] uppercase tracking-wide text-faint">· SOLUTION VALIDATOR</span>
      </div>

      {/* alignment */}
      <div className="flex flex-wrap items-center gap-2.5">
        <span
          className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[12.5px] font-medium ${ALIGN_TONE[ev.alignment] ?? ALIGN_TONE.novel}`}
          dir="auto"
        >
          {ev.alignment === 'aligned_with_success' && <CheckCircle2 className="h-3.5 w-3.5" />}
          {ev.alignment === 'matches_anti_pattern' && <AlertTriangle className="h-3.5 w-3.5" />}
          {ev.alignment_ar}
        </span>
        <span className="text-[12px] text-faint" dir="auto">
          درجة التطابق مع ما نجح: {(ev.alignment_score * 100).toFixed(0)}%
        </span>
      </div>

      {ev.matched_anti_pattern && (
        <div className="mt-3 rounded-lg border border-warn/30 bg-warn/10 p-3 text-[13px] leading-relaxed text-warn" dir="auto">
          ✗ {ev.matched_anti_pattern.warning}
        </div>
      )}

      {/* optimized solution */}
      <div className="mt-4">
        <div className="text-[12px] uppercase tracking-wide text-faint" dir="auto">الحل المُحسَّن · OPTIMIZED</div>
        <p className="mt-1.5 rounded-lg border border-blue/20 bg-blue/[0.06] p-3 text-[13.5px] leading-relaxed text-txt" dir="auto">
          {ev.optimized_solution}
        </p>
        {ev.matched_success?.source_case_id && (
          <p className="mt-2 text-[12px] text-faint" dir="auto">
            مستند إلى سابقة ناجحة: {ev.matched_success.source_case_id}
            {ev.matched_success.ts ? ` · ${ev.matched_success.ts}` : ''}
          </p>
        )}
      </div>

      {/* expected results */}
      <div className="mt-4">
        <div className="mb-2 text-[12px] uppercase tracking-wide text-faint" dir="auto">الأثر المتوقّع · EXPECTED RESULTS</div>
        <div className="flex flex-wrap items-end gap-x-5 gap-y-2">
          <Metric label="الخطر قبل" value={er.risk_before} />
          <span className="pb-1.5 text-faint">←</span>
          <Metric label="بعد الحل" value={er.risk_after} tone="text-good" />
          <Metric label="انخفاض الخطر" value={er.risk_reduction} tone="text-good" signed />
          <div className="pb-1">
            <div className="text-[11.5px] text-faint" dir="auto">الثقة</div>
            <div className={`text-[15px] font-semibold ${BAND_TONE[ev.confidence_band] ?? 'text-muted'}`} dir="auto">
              {ev.confidence_band_ar}
            </div>
          </div>
          {er.escalating && (
            <span className="pb-1.5 text-[12px] text-warn" dir="auto">⚠ تصاعد متوقّع دون تدخّل</span>
          )}
        </div>
        <p className="mt-2 text-[11.5px] text-faint" dir="auto">تقدير من المحاكاة — يعتمد على مدى تطابق حلّك مع تدخّلات ناجحة سابقة.</p>
      </div>
    </motion.div>
  )
}
