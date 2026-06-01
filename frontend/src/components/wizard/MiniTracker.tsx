import { Play, X } from 'lucide-react'
import { useWizardStore, WIZARD_STEPS } from '../../stores/wizardStore'

export default function MiniTracker() {
  const { step, completedSteps, setMinimized, reset } = useWizardStore()
  const cfg = WIZARD_STEPS[step - 1]

  return (
    <div className="fixed bottom-4 right-4 z-50 rounded-xl border border-border bg-card shadow-lg p-3 min-w-[280px]">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="text-[12px] font-medium text-txt">
            Step {step}/7 · {cfg.label}
          </div>
          <div className="mt-1 flex items-center gap-1">
            {WIZARD_STEPS.map((s) => (
              <div
                key={s.step}
                className={`h-2 w-2 rounded-full ${
                  completedSteps.has(s.step)
                    ? 'bg-good'
                    : s.step === step
                      ? 'bg-blue'
                      : 'bg-faint/40'
                }`}
              />
            ))}
          </div>
          <div className="mt-0.5 text-[10px] text-faint">Zarqa Trunk-Main Cascade</div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setMinimized(false)}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-[11px] font-medium text-txt hover:bg-cardhi"
          >
            <Play className="h-3 w-3" /> Resume
          </button>
          <button
            onClick={reset}
            className="grid h-7 w-7 place-items-center rounded-lg border border-border text-muted hover:text-txt hover:bg-cardhi"
            title="End wizard"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  )
}
