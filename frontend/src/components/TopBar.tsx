import { useEffect, useState } from 'react'
import { ShieldAlert, Radio, User } from 'lucide-react'

export default function TopBar({ risk, title }: { risk: number; title: string }) {
  const [clock, setClock] = useState('')
  useEffect(() => {
    const t = setInterval(() => {
      const d = new Date()
      setClock(
        d.toISOString().slice(11, 19) + ' UTC',
      )
    }, 1000)
    return () => clearInterval(t)
  }, [])
  const color = risk >= 75 ? '#F43F5E' : risk >= 50 ? '#FBBF24' : '#2DD4BF'

  return (
    <header className="flex h-14 items-center justify-between border-b border-hair bg-panel/80 px-5 backdrop-blur">
      <div className="flex items-center gap-3">
        <ShieldAlert className="h-5 w-5 text-signal" />
        <div className="font-display text-lg tracking-[0.18em] text-txt">AEGIS</div>
        <div className="hidden h-5 w-px bg-hair sm:block" />
        <div className="hidden font-mono text-[11px] tracking-wide text-muted sm:block">
          NATIONAL CRISIS COMMAND
        </div>
      </div>

      <div className="flex items-center gap-5">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] tracking-[0.14em] text-muted">NRI</span>
          <span className="font-display text-base tnum" style={{ color }}>
            {risk}
          </span>
          <span className="font-mono text-[10px]" style={{ color }}>
            ▲
          </span>
        </div>
        <div className="hidden items-center gap-2 md:flex">
          <Radio className="h-3.5 w-3.5 animate-pulse text-calm" />
          <span className="font-mono text-[11px] text-muted">{title}</span>
        </div>
        <div className="font-mono text-[12px] tnum text-txt">{clock}</div>
        <div className="flex items-center gap-2 rounded-sm border border-hair bg-raised px-2.5 py-1">
          <User className="h-3.5 w-3.5 text-muted" />
          <span className="font-mono text-[11px] text-txt">duty.officer</span>
        </div>
      </div>
    </header>
  )
}
