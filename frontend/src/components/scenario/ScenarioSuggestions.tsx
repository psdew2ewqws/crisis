// ScenarioSuggestions — ready-made crisis scenarios + "what-if" questions the operator
// can run with a single click (fills the box and runs). Lowers the blank-page barrier.

import { motion } from 'motion/react'
import { Sparkles, Wand2, HelpCircle } from 'lucide-react'

const SCENARIOS: string[] = [
  'انقطاع المياه وتلوّث محتمل في شبكة الزرقاء منذ ثلاثة أيام مع تصاعد الشكاوى',
  'اكتظاظ في قسم الطوارئ بمستشفى حكومي ونقص حادّ في الكوادر الطبية',
  'تأخّر صرف المعونة المالية من صندوق المعونة الوطنية لأشهر',
  'تكدّس النفايات في أحياء عمّان بعد توقف خدمة الجمع',
  'أعطال متكررة في الخدمات الإلكترونية الحكومية وتعذّر إنجاز المعاملات',
  'ازدحام مروري خانق في إربد بعد إغلاق طريق رئيسي للصيانة',
]

const QUESTIONS: string[] = [
  'ماذا يحدث لو استمرّ انقطاع المياه في الزرقاء أسبوعًا كاملًا؟',
  'ما أثر إضراب موظفي النقل العام على رضا المواطنين؟',
  'هل ستتصاعد شكاوى الخدمات الإلكترونية إذا استمرّ العطل الحالي؟',
  'كيف تتطوّر أزمة نقص الكوادر في المستشفيات إذا لم يُتدخَّل؟',
]

function Chip({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      dir="auto"
      className="rounded-full border border-border bg-bg px-3 py-1.5 text-[12.5px] text-muted transition-colors hover:border-blue/40 hover:bg-blue/[0.06] hover:text-txt disabled:opacity-50"
    >
      {label}
    </button>
  )
}

export default function ScenarioSuggestions({
  onPick,
  disabled,
  compact,
}: {
  onPick: (text: string) => void
  disabled?: boolean
  compact?: boolean
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl border border-border bg-card p-5"
    >
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-blue" />
        <h2 className="text-[15px] font-semibold text-txt" dir="auto">
          {compact ? 'جرّب مثالًا آخر' : 'أمثلة جاهزة'}
        </h2>
        <span className="text-[12px] text-faint" dir="auto">· شغّلها بنقرة واحدة</span>
      </div>

      <div className="mb-1.5 flex items-center gap-1.5 text-[12px] uppercase tracking-wide text-faint" dir="auto">
        <Wand2 className="h-3.5 w-3.5" /> سيناريوهات
      </div>
      <div className="flex flex-wrap gap-2">
        {(compact ? SCENARIOS.slice(0, 3) : SCENARIOS).map((s) => (
          <Chip key={s} label={s} onClick={() => onPick(s)} disabled={disabled} />
        ))}
      </div>

      {!compact && (
        <>
          <div className="mb-1.5 mt-4 flex items-center gap-1.5 text-[12px] uppercase tracking-wide text-faint" dir="auto">
            <HelpCircle className="h-3.5 w-3.5" /> أسئلة «ماذا لو»
          </div>
          <div className="flex flex-wrap gap-2">
            {QUESTIONS.map((q) => (
              <Chip key={q} label={q} onClick={() => onPick(q)} disabled={disabled} />
            ))}
          </div>
        </>
      )}
    </motion.div>
  )
}
