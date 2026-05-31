import { motion } from 'framer-motion'
import { XCircle } from 'lucide-react'
import type { RootCause } from '../types'

export default function RootCausePanel({ rc }: { rc: RootCause }) {
  const maxW = Math.max(...rc.evidence.map((e) => e.w))
  return (
    <div className="grid h-full grid-cols-1 gap-3 lg:grid-cols-[230px_1fr_1fr]">
      <div className="rounded-md border border-alert/40 bg-alert/[0.06] p-4">
        <div className="font-mono text-[10px] tracking-[0.18em] text-alert">ROOT CAUSE</div>
        <div className="mt-2 font-mono text-lg text-txt">{rc.rootCause}</div>
        <div className="mt-0.5 text-[12px] text-muted">{rc.apexLabel}</div>
        <div className="mt-4 flex items-end gap-2">
          <span className="font-display text-3xl tnum text-calm">{Math.round(rc.confidence * 100)}%</span>
          <span className="pb-1 font-mono text-[10px] text-muted">confidence</span>
        </div>
        <div className="mt-1 font-mono text-[10px] text-muted">{rc.method} · lead {rc.leadTimeMin}m</div>
      </div>

      <div className="rounded-md border border-hair bg-panel p-4">
        <div className="mb-3 font-mono text-[10px] tracking-[0.18em] text-muted">EVIDENCE</div>
        <div className="space-y-3">
          {rc.evidence.map((e, i) => (
            <div key={i}>
              <div className="mb-1 flex items-center justify-between gap-2 text-[12px]">
                <span className="text-txt">{e.k}</span>
                <span className="font-mono text-muted">{e.w.toFixed(2)}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-raised">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${(e.w / maxW) * 100}%` }}
                  transition={{ duration: 0.7, delay: 0.1 * i }}
                  className="h-full rounded-full bg-signal"
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-md border border-hair bg-panel p-4">
        <div className="mb-3 font-mono text-[10px] tracking-[0.18em] text-watch">REJECTED SYMPTOMS</div>
        <div className="space-y-2">
          {rc.rejected.map((r) => (
            <div key={r.id} className="flex items-start gap-2 rounded-sm border border-hair bg-raised/50 p-2.5">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-alert/70" />
              <div>
                <div className="font-mono text-[12px] text-txt">{r.id}</div>
                <div className="text-[11px] text-muted">{r.why}</div>
              </div>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-muted">
          The loudest signals (911 <span className="text-alert">+320%</span>, hospital load) are{' '}
          <span className="text-watch">downstream symptoms</span> — not the cause.
        </p>
      </div>
    </div>
  )
}
