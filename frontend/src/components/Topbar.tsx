import { useEffect, useState } from 'react'
import { PanelLeft, Search, Bell, Sun } from 'lucide-react'

export default function Topbar() {
  const [clock, setClock] = useState('')
  useEffect(() => {
    const tick = () => setClock(new Date().toISOString().slice(11, 19) + ' UTC')
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <header className="flex h-[60px] shrink-0 items-center gap-4 border-b border-border px-6">
      <button className="text-muted transition-colors hover:text-txt">
        <PanelLeft className="h-[18px] w-[18px]" />
      </button>
      <div className="h-5 w-px bg-border" />
      <nav className="flex items-center gap-2 text-[14px]">
        <span className="text-muted">Crisis Console</span>
        <span className="text-faint">/</span>
        <span className="font-medium text-txt">Zarqa Cascade</span>
      </nav>

      <div className="ml-auto flex items-center gap-3">
        <div className="relative hidden md:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
          <input
            placeholder="Search signals, entities..."
            className="h-9 w-[300px] rounded-lg border border-border bg-card pl-9 pr-3 text-[13px] text-txt outline-none transition-colors placeholder:text-faint focus:border-blue/60"
          />
        </div>
        <button className="grid h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-soft hover:text-txt">
          <Bell className="h-[18px] w-[18px]" />
        </button>
        <button className="grid h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-soft hover:text-txt">
          <Sun className="h-[18px] w-[18px]" />
        </button>
        <span className="font-mono text-[13px] tnum text-muted">{clock}</span>
      </div>
    </header>
  )
}
