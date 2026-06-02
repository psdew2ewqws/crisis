import { useEffect, useState } from 'react'
import { SlidersHorizontal, Zap, Loader2 } from 'lucide-react'
import {
  getSignals,
  getRootCause,
  getSolutions,
  severityTone,
  toneColor,
  type Signal,
  type Solution,
} from '../lib/voc'
import type { RootCause } from '../lib/voc'
import { useT } from '../lib/i18n'

type Tab = 'Signals' | 'Incidents' | 'Solutions'
const TABS: Tab[] = ['Signals', 'Incidents', 'Solutions']

const isAr = (s: string | null | undefined) => !!s && /[؀-ۿ]/.test(s)
const clip = (s: string | null | undefined, n = 90) =>
  !s ? '—' : s.length > n ? s.slice(0, n) + '…' : s

export default function DataTable({
  onRun,
  service,
  query = '',
}: {
  onRun: () => void
  service?: string | null
  query?: string
}) {
  const { t: tr } = useT()
  const [tab, setTab] = useState<Tab>('Signals')
  const [signals, setSignals] = useState<Signal[] | null>(null)
  const [incidents, setIncidents] = useState<RootCause[] | null>(null)
  const [solutions, setSolutions] = useState<Solution[] | null>(null)

  useEffect(() => {
    let alive = true
    setSignals(null)
    getSignals({ service_id: service ?? undefined, limit: 8 }).then((r) => {
      if (alive) setSignals(r.signals ?? [])
    })
    return () => {
      alive = false
    }
  }, [service])

  // Topbar search filters the fetched signal rows client-side (text / service /
  // source / sentiment) — the real service-filtered fetch above stays intact.
  const q = query.trim().toLowerCase()
  const shownSignals =
    !q || signals === null
      ? signals
      : signals.filter((s) =>
          [s.text_clean, s.text, s.service_id, s.source_type, s.sentiment_label]
            .filter(Boolean)
            .some((f) => String(f).toLowerCase().includes(q)),
        )

  useEffect(() => {
    let alive = true
    if (tab === 'Incidents' && incidents === null)
      getRootCause().then((r) => alive && setIncidents(r.root_causes ?? []))
    if (tab === 'Solutions' && solutions === null)
      getSolutions(8).then((r) => alive && setSolutions(r.solutions ?? []))
    return () => {
      alive = false
    }
  }, [tab, incidents, solutions])

  const counts: Record<Tab, number | null> = {
    Signals: shownSignals?.length ?? null,
    Incidents: incidents?.length ?? null,
    Solutions: solutions?.length ?? null,
  }

  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-5">
          {TABS.map((tabName) => (
            <button
              key={tabName}
              onClick={() => setTab(tabName)}
              className={`flex items-center gap-1.5 text-[14px] transition-colors ${
                tab === tabName ? 'font-medium text-txt' : 'text-muted hover:text-txt'
              }`}
            >
              {tr(tabName)}
              {counts[tabName] !== null && (
                <span className={`text-[12px] ${tab === tabName ? 'text-muted' : 'text-faint'}`}>
                  {counts[tabName]}
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            disabled
            title={tr('Column customization — coming soon')}
            className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-[13px] text-faint opacity-60"
          >
            <SlidersHorizontal className="h-4 w-4" />
            {tr('Customize')}
          </button>
          <button
            onClick={onRun}
            className="flex items-center gap-1.5 rounded-lg bg-blue px-3 py-1.5 text-[13px] font-semibold text-white transition-colors hover:bg-[#2f76e8]"
          >
            <Zap className="h-4 w-4 fill-white" />
            {tr('Run Analysis')}
          </button>
        </div>
      </div>

      {tab === 'Signals' && <SignalsTable rows={shownSignals} />}
      {tab === 'Incidents' && <IncidentsTable rows={incidents} />}
      {tab === 'Solutions' && <SolutionsTable rows={solutions} />}
    </div>
  )
}

function Loading() {
  const { t: tr } = useT()
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-[13px] text-muted">
      <Loader2 className="h-4 w-4 animate-spin text-blue" /> {tr('Loading…')}
    </div>
  )
}
function Empty({ msg }: { msg: string }) {
  return <div className="py-10 text-center text-[13px] text-muted">{msg}</div>
}

const SeverityCell = ({ sev }: { sev: number | string | null }) => {
  const { t: tr } = useT()
  // numeric (0..1 avg) or categorical (low/medium/high/critical)
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
      {tr(label)}
    </span>
  )
}

// Relative-time formatter; needs the translator for the word forms.
function useFmtTime() {
  const { t: tr } = useT()
  return (iso: string | null) => {
    if (!iso) return '—'
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso.slice(0, 10)
    const days = Math.round((Date.now() - d.getTime()) / 86_400_000)
    return days <= 0 ? tr('today') : days === 1 ? tr('1d') : tr('{n}d', { n: days })
  }
}

function SignalsTable({ rows }: { rows: Signal[] | null }) {
  const { t: tr } = useT()
  const fmtTime = useFmtTime()
  if (rows === null) return <Loading />
  if (rows.length === 0) return <Empty msg={tr('No signals for this selection.')} />
  return (
    <table className="w-full text-start">
      <thead>
        <tr className="text-[11px] font-medium tracking-[0.08em] text-faint">
          <th className="px-5 py-3 font-medium">{tr('SERVICE')}</th>
          <th className="py-3 font-medium">{tr('OBSERVATION')}</th>
          <th className="py-3 font-medium">{tr('SEVERITY')}</th>
          <th className="py-3 font-medium">{tr('SENTIMENT')}</th>
          <th className="px-5 py-3 text-end font-medium">{tr('OBSERVED')}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((s) => {
          const obs = s.text_clean || s.text
          return (
            <tr key={s.record_id} className="border-t border-border/70 transition-colors hover:bg-soft/50">
              <td className="px-5 py-3.5 font-mono text-[13px] text-txt">{s.service_id ?? '—'}</td>
              <td className="max-w-[1px] py-3.5 text-[13.5px] text-txt" dir={isAr(obs) ? 'rtl' : 'ltr'}>
                <span className="line-clamp-1">{clip(obs)}</span>
                <span className="ms-2 font-mono text-[11px] text-faint">{s.source_type}</span>
              </td>
              <td className="py-3.5"><SeverityCell sev={s.severity} /></td>
              <td className="py-3.5 text-[13px] text-muted">{s.sentiment_label ?? '—'}</td>
              <td className="px-5 py-3.5 text-end font-mono text-[13px] tnum text-muted">
                {fmtTime(s.observed_at)}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function IncidentsTable({ rows }: { rows: RootCause[] | null }) {
  const { t: tr } = useT()
  if (rows === null) return <Loading />
  if (rows.length === 0) return <Empty msg={tr('No active root-cause clusters.')} />
  return (
    <table className="w-full text-start">
      <thead>
        <tr className="text-[11px] font-medium tracking-[0.08em] text-faint">
          <th className="px-5 py-3 font-medium">#</th>
          <th className="py-3 font-medium">{tr('ROOT-CAUSE CLUSTER')}</th>
          <th className="py-3 font-medium">{tr('SEVERITY')}</th>
          <th className="px-5 py-3 text-end font-medium">{tr('REPORTS')}</th>
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
              <td className="px-5 py-3.5 text-end font-mono text-[13px] tnum text-muted">{c.members}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function SolutionsTable({ rows }: { rows: Solution[] | null }) {
  const { t: tr } = useT()
  if (rows === null) return <Loading />
  if (rows.length === 0) return <Empty msg={tr('No solutions available.')} />
  return (
    <table className="w-full text-start">
      <thead>
        <tr className="text-[11px] font-medium tracking-[0.08em] text-faint">
          <th className="px-5 py-3 font-medium">{tr('CLUSTER')}</th>
          <th className="py-3 font-medium">{tr('COUNTERMEASURE')}</th>
          <th className="py-3 font-medium">{tr('FEASIBILITY')}</th>
          <th className="px-5 py-3 text-end font-medium">{tr('REPORTS')}</th>
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
              <td className="px-5 py-3.5 text-end font-mono text-[13px] tnum text-muted">
                {s.affected_signals}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
