import { motion } from 'framer-motion'
import type { Signal } from '../types'
import { SEV_HEX } from '../types'

function rel(ts: string) {
  return ts.slice(11, 19)
}

export default function SignalFeed({ signals, highlight }: { signals: Signal[]; highlight: boolean }) {
  const sorted = [...signals].sort((a, b) => (a.ts < b.ts ? 1 : -1))
  return (
    <div className="flex h-full flex-col rounded-md border border-hair bg-panel shadow-panel">
      <div className="flex items-center justify-between border-b border-hair px-3 py-2.5">
        <span className="font-mono text-[10px] tracking-[0.18em] text-muted">SIGNAL FEED</span>
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 animate-ping rounded-full bg-calm" />
          <span className="font-mono text-[10px] text-calm">LIVE</span>
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {sorted.map((s, i) => (
          <motion.div
            key={s.id}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.04 * i, duration: 0.35 }}
            className={`mb-1.5 rounded-sm border bg-raised/60 p-2.5 ${
              highlight && i === 0 ? 'border-signal/50 shadow-glow' : 'border-hair'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] text-txt">{s.id}</span>
              <span className="font-mono text-[10px] tnum text-muted">{rel(s.ts)}</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: SEV_HEX[s.severity], boxShadow: `0 0 8px ${SEV_HEX[s.severity]}` }}
              />
              <span className="truncate text-[12px] text-txt">{s.type.replace(/_/g, ' ')}</span>
              <span className="ml-auto font-mono text-[12px] tnum" style={{ color: SEV_HEX[s.severity] }}>
                {s.value > 0 && s.type !== 'reservoir_level' ? '+' : ''}
                {s.value}
                <span className="text-muted">{s.unit}</span>
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2 font-mono text-[10px] text-muted">
              <span className="rounded-sm bg-void px-1.5 py-0.5">{s.source}</span>
              <span className="truncate">{s.entity}</span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
