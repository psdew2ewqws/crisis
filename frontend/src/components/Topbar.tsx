import { useEffect, useState } from 'react'
import { PanelLeft, Search, Bell, Sun, Moon } from 'lucide-react'
import { useThemeStore } from '../stores/themeStore'
import { useT } from '../lib/i18n'

export default function Topbar({
  crumb,
  query = '',
  onSearch,
  onBell,
}: {
  crumb?: string
  query?: string
  onSearch?: (q: string) => void
  onBell?: () => void
}) {
  const { theme, toggle } = useThemeStore()
  const { t } = useT()
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
        <span className="text-muted">{t('Crisis Console')}</span>
        <span className="text-faint">/</span>
        <span className="font-medium text-txt" dir={/[؀-ۿ]/.test(crumb ?? '') ? 'rtl' : 'ltr'}>
          {crumb || t('All services')}
        </span>
      </nav>

      <div className="ms-auto flex items-center gap-3">
        <div className="relative hidden md:block">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
          <input
            value={query}
            onChange={(e) => onSearch?.(e.target.value)}
            placeholder={t('Search signals, entities...')}
            className="h-9 w-[300px] rounded-lg border border-border bg-card ps-9 pe-3 text-[13px] text-txt outline-none transition-colors placeholder:text-faint focus:border-blue/60"
          />
        </div>
        <button
          onClick={onBell}
          title={t('Notifications & help')}
          className="grid h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-soft hover:text-txt"
        >
          <Bell className="h-[18px] w-[18px]" />
        </button>
        <button
          onClick={toggle}
          title={theme === 'dark' ? t('Switch to light mode') : t('Switch to dark mode')}
          className="grid h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-soft hover:text-txt"
        >
          {theme === 'dark' ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
        </button>
        <span className="font-mono text-[13px] tnum text-muted">{clock}</span>
      </div>
    </header>
  )
}
