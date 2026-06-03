import { useEffect, useState } from 'react'
import { PanelLeft, Search, Bell, Sun, Moon, Languages } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useThemeStore } from '../stores/themeStore'
import { useLangStore } from '../stores/langStore'

export default function Topbar({
  crumb,
  query = '',
  onSearch,
  onBell,
  onToggleSidebar,
}: {
  crumb?: string
  query?: string
  onSearch?: (q: string) => void
  onBell?: () => void
  onToggleSidebar?: () => void
}) {
  const { theme, toggle } = useThemeStore()
  const { t } = useTranslation()
  const { toggle: toggleLang } = useLangStore()
  const [clock, setClock] = useState('')
  useEffect(() => {
    const tick = () => setClock(new Date().toISOString().slice(11, 19) + ' UTC')
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <header className="flex h-[60px] shrink-0 items-center gap-4 border-b border-border px-6">
      <button
        onClick={onToggleSidebar}
        title="Toggle sidebar"
        aria-label="Toggle sidebar"
        className="grid h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-soft hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
      >
        <PanelLeft className="h-[18px] w-[18px]" />
      </button>
      <div className="h-5 w-px bg-border" />
      <nav className="flex items-center gap-2 text-[14px]">
        <span className="text-muted">Crisis Console</span>
        <span className="text-faint">/</span>
        <span className="font-medium text-txt" dir={/[؀-ۿ]/.test(crumb ?? '') ? 'rtl' : 'ltr'}>
          {crumb || 'All services'}
        </span>
      </nav>

      <div className="ml-auto flex items-center gap-3">
        <div className="relative hidden md:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
          <input
            value={query}
            onChange={(e) => onSearch?.(e.target.value)}
            placeholder={t('topbar.search')}
            aria-label={t('topbar.search')}
            className="h-9 w-[300px] rounded-lg border border-border bg-card pl-9 pr-3 text-[13px] text-txt outline-none transition-colors placeholder:text-faint focus:border-blue/60"
          />
        </div>
        <button
          onClick={onBell}
          title="Notifications &amp; help"
          aria-label="Open help"
          className="grid h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-soft hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
        >
          <Bell className="h-[18px] w-[18px]" />
        </button>
        <button
          onClick={toggleLang}
          title={t('lang.switch')}
          aria-label={t('lang.switch')}
          className="flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-muted transition-colors hover:bg-soft hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
        >
          <Languages className="h-[18px] w-[18px]" />
          <span className="text-[12.5px] font-medium">{t('lang.switch')}</span>
        </button>
        <button
          onClick={toggle}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label="Toggle color theme"
          className="grid h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-soft hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
        >
          {theme === 'dark' ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
        </button>
        <span className="font-mono text-[13px] tnum text-muted">{clock}</span>
      </div>
    </header>
  )
}
