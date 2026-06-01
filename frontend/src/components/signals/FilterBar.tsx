import type { SignalSource, Severity } from '../../lib/data'

const SOURCES: SignalSource[] = ['SCADA', '911-CAD', 'HIS', 'TRAFFIC', 'SOCIAL']
const SEVERITIES: (Severity | 'All')[] = ['All', 'Critical', 'Elevated', 'Nominal']

interface Props {
  activeSources: Set<SignalSource>
  toggleSource: (s: SignalSource) => void
  severity: Severity | 'All'
  setSeverity: (s: Severity | 'All') => void
}

export default function FilterBar({ activeSources, toggleSource, severity, setSeverity }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-1.5">
        {SOURCES.map((s) => {
          const on = activeSources.has(s)
          return (
            <button
              key={s}
              onClick={() => toggleSource(s)}
              className={`rounded-lg border px-3 py-1.5 text-[12.5px] transition-colors ${
                on
                  ? 'border-blue bg-blue/10 font-medium text-blue'
                  : 'border-border bg-card text-muted hover:bg-cardhi hover:text-txt'
              }`}
            >
              {s}
            </button>
          )
        })}
      </div>
      <div className="h-5 w-px bg-border" />
      <div className="flex items-center gap-1.5">
        {SEVERITIES.map((s) => {
          const on = severity === s
          return (
            <button
              key={s}
              onClick={() => setSeverity(s)}
              className={`rounded-lg border px-3 py-1.5 text-[12.5px] transition-colors ${
                on
                  ? 'border-blue bg-blue/10 font-medium text-blue'
                  : 'border-border bg-card text-muted hover:bg-cardhi hover:text-txt'
              }`}
            >
              {s}
            </button>
          )
        })}
      </div>
    </div>
  )
}
