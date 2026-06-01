import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid } from 'recharts'
import { useChartColors } from '../../stores/themeStore'

interface Props {
  title: string
  data: { time: string; value: number }[]
  trend: 'down' | 'stable' | 'up'
  baseline: number
  baselineLabel: string
}

function trendIndicator(trend: 'down' | 'stable' | 'up') {
  if (trend === 'down') return <span className="text-good">↘</span>
  if (trend === 'stable') return <span className="text-good">✓ stabilized</span>
  return <span className="text-warn">↗</span>
}

export default function TelemetryChart({ title, data, trend, baseline, baselineLabel }: Props) {
  const c = useChartColors()
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[13px] font-semibold text-txt">{title}</span>
        <span className="text-[12px]">{trendIndicator(trend)}</span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.border} vertical={false} />
          <XAxis
            dataKey="time"
            tick={{ fill: c.muted, fontSize: 11 }}
            axisLine={{ stroke: c.border }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: c.muted, fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            domain={['auto', 'auto']}
          />
          <Tooltip
            contentStyle={{ background: c.card, border: `1px solid ${c.border}`, borderRadius: 8, fontSize: 12 }}
            itemStyle={{ color: c.txt }}
            labelStyle={{ color: c.muted }}
          />
          <ReferenceLine
            y={baseline}
            stroke={c.faint}
            strokeDasharray="6 4"
            label={{ value: baselineLabel, position: 'right', fill: c.faint, fontSize: 10 }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#34D399"
            strokeWidth={2}
            dot={{ fill: '#34D399', r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
