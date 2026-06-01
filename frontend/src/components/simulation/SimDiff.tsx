import type { RiskSnapshot } from '../../lib/data'

interface Props {
  before: RiskSnapshot
  after: RiskSnapshot
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-[13px] text-muted">{label}</span>
      <span className="font-mono text-[13px] text-txt">{value}</span>
    </div>
  )
}

function RiskBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="mt-3">
      <div className="h-3 w-full rounded-full bg-bg overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <div className="mt-1 font-mono text-[12px] text-muted">{(value / 100).toFixed(2)}</div>
    </div>
  )
}

export default function SimDiff({ before, after }: Props) {
  return (
    <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
      {/* Before */}
      <div className="rounded-xl border border-danger/30 bg-card p-5">
        <div className="text-[10px] font-semibold tracking-[0.14em] text-faint mb-3">BEFORE</div>
        <div className="font-mono text-[32px] font-semibold text-danger leading-none">{before.nationalRisk}</div>
        <div className="text-[11px] text-danger/70 mb-3">critical</div>
        <div className="divide-y divide-border/50">
          <MetricRow label="911 Call Surge" value={before.callSurge} />
          <MetricRow label="Hospital Load" value={before.hospitalLoad} />
          <MetricRow label="Pipeline Pressure" value={before.pipelinePressure} />
        </div>
        <RiskBar value={before.nationalRisk} color="bg-danger" />
      </div>

      {/* After */}
      <div className="rounded-xl border border-good/30 bg-card p-5">
        <div className="flex items-center justify-between">
          <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">AFTER</div>
        </div>
        <div className="font-mono text-[32px] font-semibold text-good leading-none">{after.nationalRisk}</div>
        <div className="flex items-center gap-1.5 text-[11px] text-good/70 mb-3">
          nominal <span className="text-good">✓</span>
        </div>
        <div className="divide-y divide-border/50">
          <MetricRow label="911 Call Surge" value={after.callSurge} />
          <MetricRow label="Hospital Load" value={after.hospitalLoad} />
          <MetricRow label="Pipeline Pressure" value={after.pipelinePressure} />
        </div>
        <RiskBar value={after.nationalRisk} color="bg-good" />
        <div className="mt-1 text-[11px] text-good">✓ validated</div>
      </div>
    </div>
  )
}
