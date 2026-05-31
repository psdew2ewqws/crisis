import { Check } from 'lucide-react'

export const STEPS = [
  'Signals',
  'Stitched Incident',
  'Root Cause',
  'Candidate Solutions',
  'Validation / Sim',
  'Decide & Authorize',
  'Outcome',
]

export default function WizardRail({
  step,
  authorized,
  onJump,
}: {
  step: number
  authorized: boolean
  onJump: (i: number) => void
}) {
  return (
    <div className="rounded-md border border-hair bg-panel p-3 shadow-panel">
      <div className="mb-3 flex items-center justify-between px-1">
        <span className="font-mono text-[10px] tracking-[0.18em] text-muted">CASE WIZARD</span>
        <span className="font-mono text-[10px] text-signal">
          {String(step + 1).padStart(2, '0')}/07
        </span>
      </div>
      <ol className="space-y-1">
        {STEPS.map((label, i) => {
          const done = i < step || (i === 6 && authorized)
          const active = i === step
          return (
            <li key={label}>
              <button
                onClick={() => onJump(i)}
                className={`group flex w-full items-center gap-3 rounded-sm px-2 py-2 text-left transition-colors ${
                  active ? 'bg-raised' : 'hover:bg-raised/50'
                }`}
              >
                <span
                  className={`grid h-6 w-6 shrink-0 place-items-center rounded-sm border font-mono text-[11px] ${
                    done
                      ? 'border-calm/50 bg-calm/15 text-calm'
                      : active
                        ? 'border-signal/60 bg-signal/15 text-signal'
                        : 'border-hair text-muted'
                  }`}
                >
                  {done ? <Check className="h-3.5 w-3.5" /> : i + 1}
                </span>
                <span
                  className={`text-[13px] ${
                    active ? 'text-txt' : done ? 'text-muted' : 'text-muted/70'
                  }`}
                >
                  {label}
                </span>
                {i === 5 && (
                  <span className="ml-auto font-mono text-[9px] tracking-wider text-alert/80">
                    GATE
                  </span>
                )}
              </button>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
