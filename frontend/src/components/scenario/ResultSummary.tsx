// ResultSummary — the plain-language "end result" of a scenario run, shown FIRST and
// prominently so an average operator gets the conclusion at a glance, without reading
// the agent roster, propagation charts, or confidence breakdown.

import { motion } from 'motion/react'
import { AlertTriangle, ShieldAlert, ShieldCheck } from 'lucide-react'
import type { ScenarioDetection, ScenarioPrediction, ScenarioConfidence } from '../../lib/voc'

export default function ResultSummary({
  detection,
  prediction,
  confidence,
}: {
  detection: ScenarioDetection
  prediction: ScenarioPrediction
  confidence: ScenarioConfidence
}) {
  const sev = detection.severity // 'low' | 'elevated' | 'critical'
  const tone = sev === 'critical' ? 'danger' : sev === 'elevated' ? 'warn' : 'good'
  const border = { danger: 'border-l-danger', warn: 'border-l-warn', good: 'border-l-good' }[tone]
  const text = { danger: 'text-danger', warn: 'text-warn', good: 'text-good' }[tone]
  const Icon = sev === 'critical' ? ShieldAlert : sev === 'elevated' ? AlertTriangle : ShieldCheck
  const w = prediction.which_intervention_worked

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`rounded-xl border border-l-4 border-border bg-card p-5 ${border}`}
    >
      <div className="mb-1.5 flex items-center gap-2">
        <Icon className={`h-4 w-4 ${text}`} />
        <span className="text-[12px] uppercase tracking-wide text-faint" dir="auto">الخلاصة · RESULT</span>
      </div>

      <div className={`text-[20px] font-semibold leading-snug ${text}`} dir="auto">
        {detection.is_crisis ? 'أزمة قائمة' : 'وضع تحت المراقبة'} · الشدّة {detection.severity_ar}
      </div>

      <ul className="mt-2.5 space-y-1.5 text-[14px] leading-relaxed text-txt" dir="auto">
        <li>
          {detection.escalating
            ? '• الاتجاه: تصاعد متوقّع — يتطلّب تحرّكًا عاجلًا.'
            : '• الاتجاه: مستقر، دون تصاعد متوقّع.'}
        </li>
        {prediction.likely_outcome_ar && (
          <li>• النتيجة الأرجح: {prediction.likely_outcome_ar}.</li>
        )}
        {w && (
          <li>
            • أفضل تدخّل تاريخيًّا: «{w.intervention}»
            {typeof w.risk_reduction === 'number'
              ? ` (يخفّض الخطر بنحو ${Math.abs(w.risk_reduction).toFixed(0)} نقطة).`
              : '.'}
          </li>
        )}
        <li>• مستوى الثقة في هذه النتيجة: {confidence.band_ar}.</li>
      </ul>
    </motion.div>
  )
}
