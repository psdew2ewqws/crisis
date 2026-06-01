import type { OutcomeRecord } from '../../lib/data'

export default function ClosedLoopSummary({ outcome }: { outcome: OutcomeRecord }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="grid grid-cols-2 gap-x-8 gap-y-4 md:grid-cols-3">
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">CASE</div>
          <div className="mt-0.5 font-mono text-[14px] text-txt">{outcome.caseId}</div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">DURATION</div>
          <div className="mt-0.5 text-[14px] text-txt">{outcome.duration}</div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">STATUS</div>
          <div className="mt-0.5">
            <span className="rounded-full bg-good/10 px-3 py-1 text-[12px] font-medium text-good">
              {outcome.status} ✓
            </span>
          </div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">ROOT CAUSE</div>
          <div className="mt-0.5 font-mono text-[14px] text-txt">{outcome.rootCause}</div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">FIX</div>
          <div className="mt-0.5 text-[14px] text-txt">{outcome.fix}</div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">AUDIT</div>
          <div className="mt-0.5 font-mono text-[13px] text-muted">{outcome.auditId}</div>
        </div>
      </div>
      <div className="mt-4 border-t border-border/50 pt-3">
        <span className="text-[13px] text-muted">Risk: </span>
        <span className="font-mono text-[14px] text-danger">{outcome.riskBefore}</span>
        <span className="text-[13px] text-muted"> → </span>
        <span className="font-mono text-[14px] text-good">{outcome.riskActual}</span>
        <span className="text-[12px] text-muted"> (actual)</span>
      </div>
    </div>
  )
}
