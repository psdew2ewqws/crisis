import { useEffect, useMemo, useState } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { getSignalVolume, type VolumePoint } from '../lib/voc'
import { useT } from '../lib/i18n'

// Historical citizen-signal volume is daily over years, so the range buttons
// slice a trailing window of real buckets rather than the old fake "Last 6h".
const RANGES: { label: string; take: number }[] = [
  { label: '30 days', take: 30 },
  { label: '90 days', take: 90 },
  { label: 'All', take: Infinity },
]

export default function SignalVolume({ service }: { service?: string | null }) {
  const { t } = useT()
  const [range, setRange] = useState('90 days')
  const [series, setSeries] = useState<VolumePoint[] | null>(null)

  useEffect(() => {
    let alive = true
    setSeries(null)
    getSignalVolume({ service_id: service ?? undefined, bucket: 'date' }).then((r) => {
      if (alive) setSeries(r.series ?? [])
    })
    return () => {
      alive = false
    }
  }, [service])

  const data = useMemo(() => {
    const all = series ?? []
    const take = RANGES.find((r) => r.label === range)?.take ?? 90
    return take === Infinity ? all : all.slice(-take)
  }, [series, range])

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <div className="text-[16px] font-semibold text-txt">{t('Signal Volume')}</div>
          <div className="mt-0.5 text-[13px] text-muted">
            {t('Citizen signals · voc360 · the_data')}
            {service ? <span className="text-faint"> · {service}</span> : <span className="text-faint"> · {t('all services')}</span>}
          </div>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-border bg-bg p-1">
          {RANGES.map((r) => (
            <button
              key={r.label}
              onClick={() => setRange(r.label)}
              className={`rounded-md px-3 py-1 text-[12.5px] transition-colors ${
                range === r.label ? 'bg-cardhi font-medium text-txt' : 'text-muted hover:text-txt'
              }`}
            >
              {t(r.label)}
            </button>
          ))}
        </div>
      </div>

      {series === null ? (
        <div className="grid h-[300px] place-items-center text-[13px] text-muted">{t('Loading volume…')}</div>
      ) : data.length === 0 ? (
        <div className="grid h-[300px] place-items-center text-[13px] text-muted">
          {t('No signal volume for this selection.')}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data} margin={{ top: 10, right: 8, bottom: 0, left: -20 }}>
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
              minTickGap={40}
              dy={8}
            />
            <YAxis hide />
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
              formatter={(v) => [String(v), t('signals')]}
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
      )}
    </div>
  )
}
