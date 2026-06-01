import { ArrowLeft, ArrowRight, Lock } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useWizardStore, stepRoute, type WizardStep } from '../../stores/wizardStore'

const GUARD_HINTS: Partial<Record<WizardStep, string>> = {
  4: 'Select a solution to continue',
  5: 'Simulation must show risk reduction',
  6: 'Authorization required',
}

export default function StepFooter() {
  const { step, guards, caseId, completeStep, setStep } = useWizardStore()
  const navigate = useNavigate()

  const canContinue = guards[step]
  const isLast = step === 7
  const isDecide = step === 6

  const goBack = () => {
    if (step <= 1) return
    const prev = (step - 1) as WizardStep
    setStep(prev)
    navigate(stepRoute(prev, caseId))
  }

  const goNext = () => {
    if (!canContinue) return
    completeStep(step)
    if (isLast) {
      navigate('/')
      useWizardStore.getState().reset()
      return
    }
    const next = (step + 1) as WizardStep
    setStep(next)
    navigate(stepRoute(next, caseId))
  }

  return (
    <div className="fixed bottom-0 left-[248px] right-0 z-50 border-t border-border bg-card/95 backdrop-blur-sm px-6 py-3">
      <div className="flex items-center justify-between">
        {/* back */}
        <button
          onClick={goBack}
          disabled={step <= 1}
          className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-[13px] font-medium text-muted transition-colors hover:bg-cardhi hover:text-txt disabled:opacity-30 disabled:pointer-events-none"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>

        {/* hint when blocked */}
        {!canContinue && !isLast && GUARD_HINTS[step] && (
          <span className="text-[12px] text-faint">{GUARD_HINTS[step]}</span>
        )}

        {/* forward */}
        {isLast ? (
          <button
            onClick={goNext}
            className="rounded-lg bg-blue px-5 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8]"
          >
            Close Case
          </button>
        ) : isDecide ? (
          canContinue ? (
            <button
              onClick={goNext}
              className="flex items-center gap-2 rounded-lg bg-blue px-6 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-bluehi"
            >
              <Lock className="h-4 w-4" />
              Proceed to Outcome
            </button>
          ) : (
            <span className="text-[12px] text-faint">Complete authorization above to proceed</span>
          )
        ) : (
          <button
            onClick={goNext}
            disabled={!canContinue}
            className={`flex items-center gap-2 rounded-lg px-5 py-2.5 text-[13.5px] font-semibold transition-colors ${
              canContinue
                ? 'bg-blue text-white hover:bg-[#2f76e8]'
                : 'bg-card text-faint cursor-not-allowed border border-border'
            }`}
          >
            Continue
            <ArrowRight className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  )
}
