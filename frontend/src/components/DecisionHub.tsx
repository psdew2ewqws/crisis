import { useState } from 'react'
import { ShieldCheck, Lock } from 'lucide-react'
import type { Solution } from '../types'

export default function DecisionHub({
  solution,
  authorized,
  onAuthorize,
}: {
  solution: Solution
  authorized: boolean
  onAuthorize: () => void
}) {
  const [initials, setInitials] = useState('')
  const ok = initials.trim().length >= 2

  return (
    <div className="mx-auto grid h-full max-w-3xl grid-cols-1 gap-3 md:grid-cols-[1fr_290px]">
      <div className="rounded-md border border-hair bg-panel p-4">
        <div className="font-mono text-[10px] tracking-[0.18em] text-muted">PROPOSED INTERVENTION</div>
        <div className="mt-1.5 font-mono text-[12px] text-signal">{solution.id}</div>
        <div className="mt-0.5 text-[14px] text-txt">{solution.title}</div>
        <ul className="mt-3 space-y-1">
          {solution.actions.map((a) => (
            <li key={a} className="flex gap-1.5 text-[12px] text-muted">
              <span className="text-signal">›</span>
              {a}
            </li>
          ))}
        </ul>
        <div className="mt-4 flex gap-4 font-mono text-[12px]">
          <span className="text-calm">risk 72 → {solution.projectedRisk}</span>
          <span className="text-muted">ETA {solution.etaMin}m</span>
          <span className="text-muted">{solution.cost}</span>
        </div>
      </div>

      <div className={`rounded-md border p-4 ${authorized ? 'border-calm/50 bg-calm/[0.05]' : 'border-alert/40 bg-alert/[0.05]'}`}>
        {authorized ? (
          <div className="grid h-full place-items-center text-center">
            <div>
              <ShieldCheck className="mx-auto h-10 w-10 text-calm" />
              <div className="mt-2 font-display text-sm tracking-wide text-calm">AUTHORIZED</div>
              <div className="mt-1 font-mono text-[10px] text-muted">tasked to WAJ · logged to audit</div>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.16em] text-alert">
              <Lock className="h-3.5 w-3.5" />
              HUMAN AUTHORIZATION
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-muted">
              Requires role <span className="text-txt">decision_authority</span>. Type initials to commit.
            </p>
            <input
              value={initials}
              onChange={(e) => setInitials(e.target.value.toUpperCase())}
              placeholder="INITIALS"
              maxLength={4}
              className="mt-3 w-full rounded-sm border border-hair bg-void px-3 py-2 font-mono text-[13px] tracking-[0.3em] text-txt outline-none placeholder:text-muted/40 focus:border-signal"
            />
            <button
              disabled={!ok}
              onClick={onAuthorize}
              className={`mt-3 w-full rounded-sm px-3 py-2.5 font-mono text-[12px] tracking-[0.12em] transition-colors ${
                ok ? 'bg-alert text-white hover:bg-alert/90' : 'cursor-not-allowed bg-raised text-muted'
              }`}
            >
              AUTHORIZE INTERVENTION
            </button>
          </>
        )}
      </div>
    </div>
  )
}
