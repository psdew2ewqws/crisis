import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'
import { useChartColors } from '../../stores/themeStore'

const data = [
  { name: 'Risk Index', Before: 84, After: 22 },
  { name: '911 Calls', Before: 320, After: 41 },
  { name: 'Hospital Load', Before: 94, After: 62 },
  { name: 'Pressure', Before: 12, After: 210 },
]

export default function BeforeAfterChart() {
  const c = useChartColors()
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-[10px] font-semibold tracking-[0.14em] text-faint mb-4">METRIC COMPARISON</div>
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
          <Bar dataKey="Before" fill="#F04359" radius={[4, 4, 0, 0]} />
          <Bar dataKey="After" fill="#34D399" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
