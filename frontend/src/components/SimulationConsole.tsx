import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { BadgeCheck } from 'lucide-react'
import type { Sim } from '../types'

export default function SimulationConsole({ sim }: { sim: Sim }) {
  return (
    <div className="grid h-full grid-cols-1 gap-3 lg:grid-cols-[1.4fr_1fr]">
      <div className="rounded-md border border-hair bg-panel p-3.5">
        <div className="mb-1 flex items-center justify-between">
          <span className="font-mono text-[10px] tracking-[0.16em] text-muted">
            COUNTERFACTUAL · WNTR / EPANET
          </span>
          <span className="font-mono text-[10px] text-muted">{sim.solutionId}</span>
        </div>
        <ResponsiveContainer width="100%" height={150}>
          <LineChart data={sim.series} margin={{ top: 6, right: 10, bottom: 0, left: -20 }}>
            <CartesianGrid stroke="#1A2230" strokeDasharray="3 3" />
            <XAxis
              dataKey="t"
              unit="m"
              tick={{ fill: '#8A97A6', fontFamily: 'JetBrains Mono', fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: '#232C3A' }}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: '#8A97A6', fontFamily: 'JetBrains Mono', fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: '#232C3A' }}
            />
            <ReferenceLine y={75} stroke="#F43F5E" strokeDasharray="2 4" />
            <Line type="monotone" dataKey="before" stroke="#F43F5E" strokeWidth={2} dot={false} />
            <Line
              type="monotone"
              dataKey="after"
              stroke="#2DD4BF"
              strokeWidth={2.5}
              dot={{ r: 2.5, fill: '#2DD4BF' }}
            />
          </LineChart>
        </ResponsiveContainer>
        <div className="mt-1 flex gap-4 font-mono text-[10px]">
          <span className="flex items-center gap-1.5 text-alert">
            <span className="h-[2px] w-4 bg-alert" />
            no action
          </span>
          <span className="flex items-center gap-1.5 text-calm">
            <span className="h-[2px] w-4 bg-calm" />
            {sim.solutionId} applied
          </span>
        </div>
      </div>

      <div className="flex flex-col rounded-md border border-hair bg-panel p-3.5">
        <div className="mb-2 flex items-center justify-between">
          <span className="font-mono text-[10px] tracking-[0.16em] text-muted">PROJECTED OUTCOME</span>
          {sim.validated && (
            <span className="flex items-center gap-1 rounded-sm border border-calm/40 bg-calm/10 px-2 py-0.5 font-mono text-[10px] tracking-[0.12em] text-calm">
              <BadgeCheck className="h-3.5 w-3.5" />
              VALIDATED
            </span>
          )}
        </div>
        <div className="mb-3 flex items-center gap-3">
          <span className="font-display text-2xl tnum text-alert">{sim.riskBefore}</span>
          <span className="text-muted">→</span>
          <span className="font-display text-3xl tnum text-calm">{sim.riskAfter}</span>
          <span className="font-mono text-[10px] text-muted">risk</span>
        </div>
        <div className="space-y-1.5">
          {sim.metrics.map((m, i) => (
            <div key={i} className="flex items-center justify-between rounded-sm bg-raised/50 px-3 py-1.5">
              <span className="text-[12px] text-txt">{m.k}</span>
              <span className="font-mono text-[12px] text-calm">
                {m.v ?? `${m.before} → ${m.after}`}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
