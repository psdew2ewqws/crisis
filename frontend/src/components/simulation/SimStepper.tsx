import { Check } from 'lucide-react'

interface Props {
  elapsed: number
  estimated: number
}

const steps = ['Queued', 'Running (WNTR/EPANET)', 'Complete']

export default function SimStepper({ elapsed, estimated }: Props) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-center gap-0">
        {steps.map((label, i) => (
          <div key={label} className="flex items-center">
            {i > 0 && <div className="h-px w-16 bg-good sm:w-24" />}
            <div className="flex flex-col items-center gap-1.5">
              <div className="grid h-7 w-7 place-items-center rounded-full bg-good">
                <Check className="h-3.5 w-3.5 text-white" />
              </div>
              <span className="text-[12px] text-txt whitespace-nowrap">{label}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 text-center font-mono text-[12px] text-muted">
        Elapsed: {elapsed}s / est. {estimated}s
      </div>
    </div>
  )
}
