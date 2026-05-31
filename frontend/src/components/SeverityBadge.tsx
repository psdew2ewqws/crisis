import type { Severity } from '../types'
import { SEV_LABEL } from '../types'

const map: Record<Severity, string> = {
  calm: 'text-calm border-calm/40 bg-calm/10',
  watch: 'text-watch border-watch/40 bg-watch/10',
  alert: 'text-alert border-alert/40 bg-alert/10',
}

export default function SeverityBadge({ sev, className = '' }: { sev: Severity; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[10px] tracking-[0.12em] ${map[sev]} ${className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: 'currentColor' }} />
      {SEV_LABEL[sev]}
    </span>
  )
}
