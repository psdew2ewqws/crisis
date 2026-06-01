import { Check, Minus } from 'lucide-react'
import { motion } from 'motion/react'
import { useWizardStore, WIZARD_STEPS, stepRoute, type WizardStep } from '../../stores/wizardStore'
import { useNavigate } from 'react-router-dom'

export default function ProgressRail() {
  const { step, completedSteps, highestReached, caseId, setStep, setMinimized } = useWizardStore()
  const navigate = useNavigate()

  const jumpTo = (target: WizardStep) => {
    if (target > highestReached && !completedSteps.has(target)) return
    setStep(target)
    navigate(stepRoute(target, caseId))
  }

  return (
    <div className="fixed top-0 left-[248px] right-0 z-50 border-b border-border bg-card/95 backdrop-blur-sm px-6 py-3">
      <div className="flex items-center gap-1">
        {/* steps */}
        <div className="flex items-center gap-0 flex-1">
          {WIZARD_STEPS.map((cfg, i) => {
            const s = cfg.step
            const completed = completedSteps.has(s)
            const active = s === step
            const reachable = s <= highestReached || completed

            return (
              <div key={s} className="flex items-center">
                {i > 0 && (
                  <div className={`h-px w-6 sm:w-10 ${completed || s <= step ? 'bg-good' : 'border-t border-dashed border-faint'}`} />
                )}
                <button
                  onClick={() => reachable && jumpTo(s)}
                  disabled={!reachable}
                  className="flex flex-col items-center gap-1 group"
                  title={cfg.label}
                >
                  <div
                    className={`grid h-6 w-6 place-items-center rounded-full text-[10px] font-semibold transition-colors ${
                      completed
                        ? 'bg-good text-white'
                        : active
                          ? 'bg-blue text-white animate-pulse'
                          : reachable
                            ? 'border border-faint text-faint group-hover:border-muted group-hover:text-muted'
                            : 'border border-faint/50 text-faint/50'
                    }`}
                  >
                    {completed ? <Check className="h-3 w-3" /> : s}
                  </div>
                  <motion.span
                    key={active ? 'active' : 'idle'}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className={`text-[10px] whitespace-nowrap ${
                      active ? 'font-semibold text-blue' : completed ? 'text-good' : 'text-faint'
                    }`}
                  >
                    {cfg.label}
                  </motion.span>
                </button>
              </div>
            )
          })}
        </div>

        {/* info + minimize */}
        <div className="flex items-center gap-4 shrink-0 ml-4">
          <span className="text-[12px] text-muted">
            Step {step} of 7 · <span className="text-txt font-medium">{WIZARD_STEPS[step - 1].label}</span>
          </span>
          <span className="font-mono text-[11px] text-faint">~{(7 - step) * 30}s</span>
          <button
            onClick={() => setMinimized(true)}
            className="grid h-6 w-6 place-items-center rounded-md border border-border text-muted hover:text-txt hover:bg-cardhi"
          >
            <Minus className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  )
}
