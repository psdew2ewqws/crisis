import type { Signal } from '../../lib/data'

const sevDot: Record<string, string> = {
  Critical: 'bg-danger',
  Elevated: 'bg-warn',
  Nominal: 'bg-good',
}

const srcBg: Record<string, string> = {
  SCADA: 'bg-blue/10 text-blue',
  '911-CAD': 'bg-danger/10 text-danger',
  HIS: 'bg-warn/10 text-warn',
  TRAFFIC: 'bg-good/10 text-good',
  SOCIAL: 'bg-faint/20 text-muted',
}

interface Props {
  signal: Signal
  selected: boolean
  onSelect: (s: Signal) => void
}

export default function SignalCard({ signal, selected, onSelect }: Props) {
  const time = signal.timestamp.slice(11, 19) + 'Z'
  return (
    <button
      onClick={() => onSelect(signal)}
      className={`w-full text-left rounded-xl border p-4 transition-colors ${
        selected
          ? 'border-blue bg-cardhi'
          : 'border-border bg-card hover:bg-cardhi'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${sevDot[signal.severity]}`} />
          <span className="font-mono text-[12px] text-muted">{signal.id}</span>
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${srcBg[signal.source]}`}>
            {signal.source}
          </span>
        </div>
        <span className="font-mono text-[11px] text-faint">{time}</span>
      </div>
      <div className="mt-2">
        <div className="text-[13.5px] font-medium text-txt">{signal.entity}</div>
        <div className="mt-0.5 text-[12.5px] text-muted">{signal.observation}</div>
      </div>
      <div className="mt-2 flex items-center gap-4">
        <span className="font-mono text-[12px] text-txt">Δ {signal.delta}</span>
        <span className="font-mono text-[12px] text-muted">Z {signal.zScore}</span>
      </div>
    </button>
  )
}
