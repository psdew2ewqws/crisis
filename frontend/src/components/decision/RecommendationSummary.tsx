import type { DecisionRecord } from '../../lib/data'

export default function RecommendationSummary({ decision }: { decision: DecisionRecord }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint mb-1">ROOT CAUSE</div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-danger" />
            <span className="text-[14px] font-medium text-txt">{decision.rootCause}</span>
          </div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint mb-1">INTERVENTION</div>
          <div className="text-[14px] text-txt">{decision.intervention}</div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint mb-1">VALIDATION</div>
          <div className="text-[13px] text-txt">
            Confidence: <span className="font-mono text-good">{decision.confidence}</span>
            <span className="text-muted"> · </span>
            Sim: <span className="text-good">✓ validated</span>
            <span className="text-muted"> · </span>
            Risk: <span className="font-mono">{decision.riskBefore} → {decision.riskAfter}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
