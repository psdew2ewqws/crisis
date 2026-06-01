import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'
import type { Intervention } from '../../lib/data'
import { useChartColors } from '../../stores/themeStore'

interface Props {
  interventions: Intervention[]
}

export default function TradeoffChart({ interventions }: Props) {
  const c = useChartColors()
  const data = interventions.map((iv) => ({
    name: iv.id,
    Risk: iv.projectedRisk,
    'Cost ($k)': iv.costUsd / 1000,
    'ETA (min)': iv.etaMinutes,
  }))

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-[10px] font-semibold tracking-[0.14em] text-faint mb-4">TRADEOFF ANALYSIS</div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} barGap={4} barCategoryGap="25%">
          <CartesianGrid strokeDasharray="3 3" stroke={c.border} vertical={false} />
          <XAxis dataKey="name" tick={{ fill: c.muted, fontSize: 12 }} axisLine={{ stroke: c.border }} tickLine={false} />
          <YAxis tick={{ fill: c.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{ background: c.card, border: `1px solid ${c.border}`, borderRadius: 8, fontSize: 12 }}
            itemStyle={{ color: c.txt }}
            labelStyle={{ color: c.muted }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: c.muted }} />
          <Bar dataKey="Risk" fill="#F04359" radius={[4, 4, 0, 0]} />
          <Bar dataKey="Cost ($k)" fill="#FBBF24" radius={[4, 4, 0, 0]} />
          <Bar dataKey="ETA (min)" fill="#3B82F6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
