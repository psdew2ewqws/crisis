import { Radio, ExternalLink } from 'lucide-react'
import type { Signal } from '../../lib/data'

const sevBadge: Record<string, string> = {
  Critical: 'bg-danger/10 text-danger border-danger/30',
  Elevated: 'bg-warn/10 text-warn border-warn/30',
  Nominal: 'bg-good/10 text-good border-good/30',
}

interface Props {
  signal: Signal | null
  onViewInGraph?: () => void
}

export default function SignalDetail({ signal, onViewInGraph }: Props) {
  if (!signal) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <Radio className="mx-auto mb-3 h-10 w-10 text-faint" />
          <p className="text-muted">Select a signal to inspect</p>
        </div>
      </div>
    )
  }

  const time = signal.timestamp.slice(11, 19) + 'Z'

  return (
    <div className="overflow-y-auto p-5">
      {/* header */}
      <div className="flex items-center gap-3">
        <span className="font-mono text-[14px] font-medium text-txt">{signal.id}</span>
        <span className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${sevBadge[signal.severity]}`}>
          {signal.severity}
        </span>
        <span className="ml-auto font-mono text-[12px] text-muted">{time}</span>
      </div>

      {/* entity */}
      <div className="mt-5">
        <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">ENTITY</div>
        <div className="mt-1 text-[14px] font-medium text-txt">{signal.entity}</div>
        <div className="mt-0.5 font-mono text-[12px] text-faint">{signal.entityId}</div>
      </div>

      {/* metrics */}
      <div className="mt-5 grid grid-cols-3 gap-4">
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">OBSERVATION</div>
          <div className="mt-1 text-[13px] text-txt">{signal.observation}</div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">Δ VALUE</div>
          <div className="mt-1 font-mono text-[13px] text-txt">{signal.delta}</div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">Z-SCORE</div>
          <div className="mt-1 font-mono text-[13px] text-txt">{signal.zScore}</div>
        </div>
      </div>

      {/* source + geo */}
      <div className="mt-5 grid grid-cols-2 gap-4">
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">SOURCE</div>
          <div className="mt-1 text-[13px] text-txt">{signal.source}</div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">GEO</div>
          <div className="mt-1 font-mono text-[12px] text-muted">{signal.lat}, {signal.lng}</div>
        </div>
      </div>

      {/* raw payload */}
      <div className="mt-5">
        <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">RAW PAYLOAD</div>
        <pre className="mt-2 rounded-lg bg-bg p-4 font-mono text-[11px] text-muted overflow-x-auto">
          {JSON.stringify(signal.rawPayload, null, 2)}
        </pre>
      </div>

      {/* similar past signals */}
      <div className="mt-5">
        <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">SIMILAR PAST SIGNALS</div>
        <p className="mt-2 text-[12px] text-faint italic">
          pgvector similarity search — requires backend
        </p>
      </div>

      {/* cross-page link */}
      {onViewInGraph && (
        <button
          onClick={onViewInGraph}
          className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-soft px-4 py-2 text-[12px] font-medium text-txt transition-colors hover:bg-cardhi"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          View in Graph
        </button>
      )}
    </div>
  )
}
