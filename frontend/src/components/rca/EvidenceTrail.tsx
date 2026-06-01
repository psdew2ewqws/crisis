import type { RootCauseResult } from '../../lib/data'

export default function EvidenceTrail({ evidence }: { evidence: RootCauseResult['evidence'] }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-[10px] font-semibold tracking-[0.14em] text-faint mb-4">EVIDENCE TRAIL</div>
      <div className="space-y-3">
        {evidence.map((e) => (
          <div key={e.rank} className="flex items-baseline gap-3">
            <span className="shrink-0 font-mono text-[13px] text-muted">{e.rank}.</span>
            <span className="flex-1 text-[13.5px] text-txt">{e.description}</span>
            <span className="shrink-0 border-b border-dotted border-border" style={{ width: 40 }} />
            <span className="shrink-0 font-mono text-[13px] text-muted text-right w-14">
              {e.weight.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
