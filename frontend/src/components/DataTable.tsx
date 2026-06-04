import { useEffect, useState } from 'react'
import { SlidersHorizontal, Zap, Loader2 } from 'lucide-react'
import {
  getRootCause,
  getSolutions,
  severityTone,
  toneColor,
  type Solution,
} from '../lib/voc'
import type { RootCause } from '../lib/voc'

type Tab = 'Incidents' | 'Solutions'
const TABS: Tab[] = ['Incidents', 'Solutions']

const isAr = (s: string | null | undefined) => !!s && /[؀-ۿ]/.test(s)
const clip = (s: string | null | undefined, n = 90) =>
  !s ? '—' : s.length > n ? s.slice(0, n) + '…' : s

export default function DataTable({
  onRun,
}: {
  onRun: () => void
  service?: string | null
  query?: string
}) {
  const [tab, setTab] = useState<Tab>('Incidents')
  const [incidents, setIncidents] = useState<RootCause[] | null>(null)
  const [solutions, setSolutions] = useState<Solution[] | null>(null)

  useEffect(() => {
    let alive = true
    if (tab === 'Incidents' && incidents === null)
      getRootCause().then((r) => alive && setIncidents(r.root_causes ?? []))
    if (tab === 'Solutions' && solutions === null)
      getSolutions(8).then((r) => alive && setSolutions(r.solutions ?? []))
    return () => { alive = false }
  }, [tab, incidents, solutions])

  const counts: Record<Tab, number | null> = {
    Incidents: incidents?.length ?? null,
    Solutions: solutions?.length ?? null,
  }

  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-5">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex items-center gap-1.5 text-[14px] transition-colors ${
                tab === t ? 'font-medium text-txt' : 'text-muted hover:text-txt'
              }`}
            >
              {t}
              {counts[t] !== null && (
                <span className={`text-[12px] ${tab === t ? 'text-muted' : 'text-faint'}`}>
                  {counts[t]}
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            disabled
            title="Column customization — coming soon"
            className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-[13px] text-faint opacity-60"
          >
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

      {tab === 'Incidents' && <IncidentsTable rows={incidents} />}
      {tab === 'Solutions' && <SolutionsTable rows={solutions} />}
    </div>
  )
}

function Loading() {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-[13px] text-muted">
      <Loader2 className="h-4 w-4 animate-spin text-blue" /> Loading…
    </div>
  )
}
function Empty({ msg }: { msg: string }) {
  return <div className="py-10 text-center text-[13px] text-muted">{msg}</div>
}

const SeverityCell = ({ sev }: { sev: number | string | null }) => {
  let label: string
  let color: string
  if (typeof sev === 'number') {
    label = sev >= 0.5 ? 'Critical' : sev >= 0.3 ? 'Elevated' : 'Nominal'
    color = sev >= 0.5 ? '#F04359' : sev >= 0.3 ? '#FBBF24' : '#34D399'
  } else {
    const tone = severityTone(sev as any)
    label = sev ?? 'n/a'
    color = toneColor(tone)
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-[13px]" style={{ color }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  )
}

function IncidentsTable({ rows }: { rows: RootCause[] | null }) {
  if (rows === null) return <Loading />
  if (rows.length === 0) return <Empty msg="No active root-cause clusters." />
  return (
    <table className="w-full text-left">
      <thead>
        <tr className="text-[11px] font-medium tracking-[0.08em] text-faint">
          <th className="px-5 py-3 font-medium">#</th>
          <th className="py-3 font-medium">ROOT-CAUSE CLUSTER</th>
          <th className="py-3 font-medium">SEVERITY</th>
          <th className="px-5 py-3 text-right font-medium">REPORTS</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((c) => {
          const label = c.label_en || c.label_ar || c.cluster_id
          return (
            <tr key={c.cluster_id} className="border-t border-border/70 transition-colors hover:bg-soft/50">
              <td className="px-5 py-3.5 font-mono text-[12px] text-faint">{c.rank}</td>
              <td className="max-w-[1px] py-3.5 text-[13.5px] text-txt" dir={isAr(label) ? 'rtl' : 'ltr'}>
                <span className="line-clamp-1">{label}</span>
              </td>
              <td className="py-3.5"><SeverityCell sev={c.severity_avg} /></td>
              <td className="px-5 py-3.5 text-right font-mono text-[13px] tnum text-muted">{c.members}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function SolutionsTable({ rows }: { rows: Solution[] | null }) {
  if (rows === null) return <Loading />
  if (rows.length === 0) return <Empty msg="No solutions available." />
  return (
    <table className="w-full text-left">
      <thead>
        <tr className="text-[11px] font-medium tracking-[0.08em] text-faint">
          <th className="px-5 py-3 font-medium">CLUSTER</th>
          <th className="py-3 font-medium">COUNTERMEASURE</th>
          <th className="py-3 font-medium">FEASIBILITY</th>
          <th className="px-5 py-3 text-right font-medium">REPORTS</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((s) => {
          const label = s.label_en || s.label_ar || s.cluster_id
          return (
            <tr key={s.cluster_id} className="border-t border-border/70 transition-colors hover:bg-soft/50">
              <td className="px-5 py-3.5 max-w-[1px] text-[13px] text-txt" dir={isAr(label) ? 'rtl' : 'ltr'}>
                <span className="line-clamp-1">{label}</span>
              </td>
              <td className="max-w-[1px] py-3.5 text-[13.5px] text-txt">
                <span className="line-clamp-1">{clip(s.countermeasure, 70)}</span>
              </td>
              <td className="py-3.5 text-[13px] text-muted">{s.feasibility_label}</td>
              <td className="px-5 py-3.5 text-right font-mono text-[13px] tnum text-muted">
                {s.affected_signals}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
