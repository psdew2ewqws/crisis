import { Target } from 'lucide-react'
import type { RootCauseResult } from '../../lib/data'
import { useChartColors } from '../../stores/themeStore'

export default function ApexCard({ rca }: { rca: RootCauseResult }) {
  const c = useChartColors()
  return (
    <div className="apex-glow rounded-xl border border-danger bg-card p-6" style={{ background: `linear-gradient(135deg, rgba(240,67,89,0.05) 0%, ${c.card} 40%)` }}>
      <div className="flex items-start gap-4">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-danger/10">
          <Target className="h-5 w-5 text-danger" />
        </div>
        <div className="flex-1">
          <div className="text-[18px] font-semibold text-txt">
            {rca.apexNodeId} — Trunk-main rupture, Zone 3
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-6">
            <div>
              <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">CONFIDENCE</div>
              <div className="mt-0.5 font-mono text-[28px] font-semibold leading-none text-txt">{rca.confidence}</div>
            </div>
            <div>
              <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">METHOD</div>
              <div className="mt-0.5">
                <span className="rounded-md border border-border bg-soft px-2 py-0.5 font-mono text-[12px] text-muted">
                  {rca.method}
                </span>
              </div>
            </div>
            <div>
              <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">LEAD TIME</div>
              <div className="mt-0.5 text-[14px] text-txt">
                {rca.leadTimeMinutes} min <span className="text-muted">before first downstream signal</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
