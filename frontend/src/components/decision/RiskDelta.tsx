interface Props {
  riskBefore: number
  riskAfter: number
  riskReduction: string
}

export default function RiskDelta({ riskBefore, riskAfter, riskReduction }: Props) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-[10px] font-semibold tracking-[0.14em] text-faint mb-4">RISK DELTA</div>
      <div className="space-y-4">
        {/* Before bar */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[12px] text-muted">Before</span>
            <span className="font-mono text-[13px] text-danger">{riskBefore} (critical)</span>
          </div>
          <div className="h-4 w-full rounded-full bg-bg overflow-hidden">
            <div className="h-full rounded-full bg-danger" style={{ width: `${riskBefore}%` }} />
          </div>
        </div>
        {/* After bar */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[12px] text-muted">After</span>
            <span className="font-mono text-[13px] text-good">{riskAfter} (nominal)</span>
          </div>
          <div className="h-4 w-full rounded-full bg-bg overflow-hidden">
            <div className="h-full rounded-full bg-good" style={{ width: `${riskAfter}%` }} />
          </div>
        </div>
        {/* Delta */}
        <div className="text-right">
          <span className="font-mono text-[22px] font-semibold text-good">Δ {riskReduction}</span>
        </div>
      </div>
    </div>
  )
}
