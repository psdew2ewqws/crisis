import { useState } from 'react'
import { SlidersHorizontal, Zap } from 'lucide-react'
import { signals, type Severity } from '../lib/data'

const TABS = [
  { label: 'Signals', count: 6 },
  { label: 'Incidents', count: 5 },
  { label: 'Solutions', count: 3 },
]

const sevTone: Record<Severity, string> = {
  Critical: 'text-danger',
  Elevated: 'text-warn',
  Nominal: 'text-good',
}
const sevDot: Record<Severity, string> = {
  Critical: 'bg-danger',
  Elevated: 'bg-warn',
  Nominal: 'bg-good',
}

export default function DataTable({ onRun }: { onRun: () => void }) {
  const [tab, setTab] = useState('Signals')
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-5">
          {TABS.map((t) => (
            <button
              key={t.label}
              onClick={() => setTab(t.label)}
              className={`flex items-center gap-1.5 text-[14px] transition-colors ${
                tab === t.label ? 'font-medium text-txt' : 'text-muted hover:text-txt'
              }`}
            >
              {t.label}
              <span className={`text-[12px] ${tab === t.label ? 'text-muted' : 'text-faint'}`}>
                {t.count}
              </span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-[13px] text-muted transition-colors hover:bg-soft hover:text-txt">
            <SlidersHorizontal className="h-4 w-4" />
            Customize
          </button>
          <button
            onClick={onRun}
            className="flex items-center gap-1.5 rounded-lg bg-blue px-3 py-1.5 text-[13px] font-semibold text-white transition-colors hover:bg-[#2f76e8]"
          >
            <Zap className="h-4 w-4 fill-white" />
            Run Analysis
          </button>
        </div>
      </div>

      <table className="w-full text-left">
        <thead>
          <tr className="text-[11px] font-medium tracking-[0.08em] text-faint">
            <th className="px-5 py-3 font-medium">ENTITY</th>
            <th className="py-3 font-medium">OBSERVATION</th>
            <th className="py-3 font-medium">SEVERITY</th>
            <th className="py-3 text-right font-medium">Δ VALUE</th>
            <th className="py-3 text-right font-medium">Z</th>
            <th className="px-5 py-3 text-right font-medium">TIME</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((s) => (
            <tr key={s.entity} className="border-t border-border/70 transition-colors hover:bg-soft/50">
              <td className="px-5 py-3.5 font-mono text-[13px] text-txt">{s.entity}</td>
              <td className="py-3.5 text-[13.5px] text-txt">
                {s.observation}
                <span className="ml-2 font-mono text-[11px] text-faint">{s.source}</span>
              </td>
              <td className="py-3.5">
                <span className={`inline-flex items-center gap-1.5 text-[13px] ${sevTone[s.severity]}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${sevDot[s.severity]}`} />
                  {s.severity}
                </span>
              </td>
              <td className="py-3.5 text-right font-mono text-[13px] tnum text-txt">{s.delta}</td>
              <td className="py-3.5 text-right font-mono text-[13px] tnum text-muted">{s.z}</td>
              <td className="px-5 py-3.5 text-right font-mono text-[13px] tnum text-muted">{s.time}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
