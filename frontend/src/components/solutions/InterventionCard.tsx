import { Star, Check } from 'lucide-react'
import type { Intervention } from '../../lib/data'

const borderColor: Record<string, string> = {
  good: 'border-l-good',
  warn: 'border-l-warn',
  neutral: 'border-l-muted',
  danger: 'border-l-danger',
}

interface Props {
  intervention: Intervention
  selected: boolean
  onSelect: () => void
}

export default function InterventionCard({ intervention: iv, selected, onSelect }: Props) {
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left rounded-xl border bg-card p-5 transition-all border-l-4 ${borderColor[iv.severityBand]} ${
        selected ? 'ring-2 ring-blue border-border' : 'border-border hover:bg-cardhi'
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[12px] text-faint">{iv.id}</span>
            <span className="text-[14px] font-semibold text-txt">{iv.title}</span>
          </div>
          {iv.recommended && (
            <span className="mt-1.5 inline-flex items-center gap-1 rounded-md bg-good/10 px-2 py-0.5 text-[11px] font-medium text-good">
              <Star className="h-3 w-3" /> Recommended
            </span>
          )}
        </div>
        {selected && (
          <div className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-blue">
            <Check className="h-3.5 w-3.5 text-white" />
          </div>
        )}
      </div>

      <div className="mt-3">
        <div className="text-[11px] font-semibold tracking-[0.1em] text-faint mb-1.5">ACTIONS</div>
        <ul className="space-y-1">
          {iv.actions.map((a, i) => (
            <li key={i} className="flex items-start gap-2 text-[13px] text-muted">
              <span className="mt-0.5 text-faint">•</span>
              {a}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-4 flex items-center gap-6 border-t border-border/50 pt-3">
        <div>
          <span className="text-[10px] font-semibold tracking-[0.1em] text-faint">RISK</span>
          <div className="font-mono text-[14px] font-semibold text-txt">{iv.projectedRisk}</div>
        </div>
        <div>
          <span className="text-[10px] font-semibold tracking-[0.1em] text-faint">ETA</span>
          <div className="font-mono text-[14px] text-txt">{iv.etaMinutes} min</div>
        </div>
        <div>
          <span className="text-[10px] font-semibold tracking-[0.1em] text-faint">COST</span>
          <div className="font-mono text-[14px] text-txt">${iv.costUsd.toLocaleString()}</div>
        </div>
        {iv.feasible && (
          <span className="ml-auto flex items-center gap-1 text-[12px] text-good">
            <Check className="h-3.5 w-3.5" /> Feasible
          </span>
        )}
      </div>
    </button>
  )
}
