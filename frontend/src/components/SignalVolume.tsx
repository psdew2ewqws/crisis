import { useState } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { signalVolume } from '../lib/data'

const RANGES = ['Last 6h', '24 hours', '7 days']

export default function SignalVolume() {
  const [range, setRange] = useState('Last 6h')
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <div className="text-[16px] font-semibold text-txt">Signal Volume</div>
          <div className="mt-0.5 text-[13px] text-muted">
            911 call rate &amp; pressure anomalies · Zarqa North
          </div>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-border bg-bg p-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`rounded-md px-3 py-1 text-[12.5px] transition-colors ${
                range === r ? 'bg-cardhi font-medium text-txt' : 'text-muted hover:text-txt'
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={signalVolume} margin={{ top: 10, right: 8, bottom: 0, left: -20 }}>
          <defs>
            <linearGradient id="sv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#1A1B20" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="t"
            tick={{ fill: '#62646D', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval={2}
            dy={8}
          />
          <YAxis hide domain={[0, 100]} />
          <Tooltip
            cursor={{ stroke: '#3B82F6', strokeWidth: 1, strokeDasharray: '3 3' }}
            contentStyle={{
              background: '#131417',
              border: '1px solid #212228',
              borderRadius: 10,
              fontSize: 12,
            }}
            labelStyle={{ color: '#8B8D96' }}
            itemStyle={{ color: '#ECEDEE' }}
            formatter={(v) => [String(v), 'signals']}
          />
          <Area
            type="monotone"
            dataKey="v"
            stroke="#3B82F6"
            strokeWidth={2.5}
            fill="url(#sv)"
            activeDot={{ r: 4, fill: '#3B82F6', stroke: '#0A0A0B', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
