import { ArrowDownRight, CheckCircle2, Clock, Coins } from 'lucide-react'
import type { Solution } from '../types'

export default function SolutionReview({
  solutions,
  current,
  onPick,
}: {
  solutions: Solution[]
  current: number
  onPick: (i: number) => void
}) {
  return (
    <div className="grid h-full grid-cols-1 gap-3 md:grid-cols-3">
      {solutions.map((s, i) => {
        const rec = s.recommended
        const sel = i === current
        const sym = s.id === 'SOL-C'
        return (
          <button
            key={s.id}
            onClick={() => onPick(i)}
            className={`flex flex-col rounded-md border p-3.5 text-left transition-colors ${
              sel
                ? 'border-signal/60 bg-raised'
                : rec
                  ? 'border-calm/40 bg-calm/[0.05]'
                  : 'border-hair bg-panel'
            } ${!rec && !sel ? 'opacity-85' : ''}`}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] text-txt">{s.id}</span>
              {rec ? (
                <span className="flex items-center gap-1 rounded-sm bg-calm/15 px-1.5 py-0.5 font-mono text-[8px] tracking-[0.14em] text-calm">
                  <CheckCircle2 className="h-3 w-3" />
                  RECOMMENDED
                </span>
              ) : sym ? (
                <span className="rounded-sm bg-alert/10 px-1.5 py-0.5 font-mono text-[8px] tracking-[0.14em] text-alert/80">
                  SYMPTOM-ONLY
                </span>
              ) : null}
            </div>
            <div className="mt-2 text-[12.5px] leading-snug text-txt">{s.title}</div>
            <ul className="mt-2 space-y-0.5">
              {s.actions.map((a) => (
                <li key={a} className="flex gap-1.5 text-[11px] text-muted">
                  <span className="text-signal">›</span>
                  {a}
                </li>
              ))}
            </ul>
            <div className="mt-auto flex items-center gap-3 pt-3 font-mono text-[11px]">
              <span
                className="flex items-center gap-1"
                style={{ color: s.projectedRisk < 50 ? '#2DD4BF' : s.projectedRisk < 65 ? '#FBBF24' : '#F43F5E' }}
              >
                <ArrowDownRight className="h-3.5 w-3.5" />
                {s.projectedRisk}
              </span>
              <span className="flex items-center gap-1 text-muted">
                <Clock className="h-3 w-3" />
                {s.etaMin}m
              </span>
              <span className="flex items-center gap-1 text-muted">
                <Coins className="h-3 w-3" />
                {s.cost.replace('$', '')}
              </span>
            </div>
          </button>
        )
      })}
    </div>
  )
}
