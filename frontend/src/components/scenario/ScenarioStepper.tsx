import { motion } from 'motion/react'
import { Check } from 'lucide-react'

export type StageKey = 'parse' | 'retrieve' | 'select_agents' | 'simulate' | 'detect_predict'

interface ScenarioStepperProps {
  done: StageKey[]
  current: StageKey | null
}

const STEPS: { key: StageKey; label: string; en: string }[] = [
  { key: 'parse', label: 'تحليل النص', en: 'Parse' },
  { key: 'retrieve', label: 'استرجاع السوابق', en: 'Retrieve' },
  { key: 'select_agents', label: 'اختيار الوكلاء', en: 'Select agents' },
  { key: 'simulate', label: 'المحاكاة', en: 'Simulate' },
  { key: 'detect_predict', label: 'الكشف والتنبؤ', en: 'Detect & predict' },
]

export default function ScenarioStepper({ done, current }: ScenarioStepperProps) {
  const doneSet = new Set<StageKey>(done)
  const currentIndex = current ? STEPS.findIndex((s) => s.key === current) : -1

  // Fill the rail through the furthest-reached node (last done, or the active one).
  const lastDoneIndex = STEPS.reduce((acc, s, i) => (doneSet.has(s.key) ? i : acc), -1)
  const reached = Math.max(lastDoneIndex, currentIndex)

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex flex-wrap items-start justify-between gap-x-2 gap-y-4"
    >
      {STEPS.map((step, i) => {
        const isDone = doneSet.has(step.key)
        const isCurrent = step.key === current
        const stateTone = isDone ? 'text-good' : isCurrent ? 'text-blue' : 'text-faint'

        return (
          <div
            key={step.key}
            className="relative flex min-w-[88px] flex-1 flex-col items-center text-center"
          >
            {/* Rail segment to the right of this node (skip on the last node) */}
            {i < STEPS.length - 1 && (
              <span className="absolute left-1/2 top-[13px] h-px w-full bg-border" aria-hidden>
                <motion.span
                  className="block h-px bg-good"
                  initial={false}
                  animate={{ width: i < reached ? '100%' : '0%' }}
                  transition={{ duration: 0.4, ease: 'easeOut' }}
                />
              </span>
            )}

            {/* Node marker */}
            <span className="relative z-10 flex h-7 w-7 items-center justify-center">
              {isDone ? (
                <span className="flex h-6 w-6 items-center justify-center rounded-full border border-good/40 bg-good/15 text-good">
                  <Check className="h-3.5 w-3.5" />
                </span>
              ) : isCurrent ? (
                <span className="relative flex h-6 w-6 items-center justify-center">
                  <motion.span
                    className="absolute inset-0 rounded-full border border-blue"
                    initial={{ opacity: 0.55, scale: 1 }}
                    animate={{ opacity: 0, scale: 1.9 }}
                    transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
                  />
                  <span className="h-2.5 w-2.5 rounded-full bg-blue" />
                </span>
              ) : (
                <span className="h-2.5 w-2.5 rounded-full border border-faint/60" />
              )}
            </span>

            {/* Labels — Arabic primary, English secondary in faint */}
            <span
              dir="auto"
              className={`mt-2 text-[12px] font-medium leading-tight ${stateTone}`}
            >
              {step.label}
            </span>
            <span dir="auto" className="text-[10.5px] uppercase tracking-wide text-faint">
              {step.en}
            </span>
          </div>
        )
      })}
    </motion.div>
  )
}
