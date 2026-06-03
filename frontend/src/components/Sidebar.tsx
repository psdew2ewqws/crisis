import {
  Zap,
  LayoutGrid,
  Activity,
  Share2,
  Target,
  FlaskConical,
  Gauge,
  PenLine,
  Brain,
  MessageSquare,
  Settings,
  HelpCircle,
  LogOut,
  Home,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import AegisLogo, { AegisLogoFull } from './AegisLogo'
import type { Tone } from '../lib/data'
import type { AuthUser } from '../stores/authStore'

// Navigation grouped by the operator's workflow: watch the live picture (MONITOR),
// find the cause (ANALYZE), act on it (RESPOND), ask for help (ASSIST).
// `key` is the stable view id App switches on (never translated); `labelKey` is the
// i18n key for the displayed text.
const NAV_GROUPS: {
  titleKey: string
  items: { key: string; labelKey: string; icon: typeof LayoutGrid; tourId?: string }[]
}[] = [
  {
    titleKey: 'nav.monitor',
    items: [
      { key: 'Dashboard', labelKey: 'nav.dashboard', icon: LayoutGrid },
      { key: 'Signals', labelKey: 'nav.signals', icon: Activity, tourId: 'signals' },
      { key: 'Incident Graph', labelKey: 'nav.incidentGraph', icon: Share2 },
    ],
  },
  {
    titleKey: 'nav.analyze',
    items: [
      { key: 'Root Cause', labelKey: 'nav.rootCause', icon: Target, tourId: 'rootcause' },
      { key: 'Deep Analysis', labelKey: 'nav.deepAnalysis', icon: Brain, tourId: 'deepanalysis' },
    ],
  },
  {
    titleKey: 'nav.respond',
    items: [
      { key: 'Solutions', labelKey: 'nav.solutions', icon: FlaskConical },
      { key: 'Simulation', labelKey: 'nav.simulation', icon: Gauge },
      { key: 'Decisions', labelKey: 'nav.decisions', icon: PenLine, tourId: 'decisions' },
    ],
  },
  {
    titleKey: 'nav.assist',
    items: [{ key: 'Expert Chat', labelKey: 'nav.expertChat', icon: MessageSquare }],
  },
]

// A sidebar CASE row = a real voc360 service (id) with its signal/critical counts.
export interface CaseRow {
  id: string
  name: string
  score: string // formatted badge (e.g. signal count)
  tone: Tone
}

const dot: Record<Tone, string> = {
  danger: 'bg-danger',
  good: 'bg-good',
  warn: 'bg-warn',
  neutral: 'bg-muted',
}
const score: Record<Tone, string> = {
  danger: 'text-danger',
  good: 'text-good',
  warn: 'text-warn',
  neutral: 'text-muted',
}

export default function Sidebar({
  onRun,
  active,
  onNavigate,
  cases,
  activeCase,
  onSelectCase,
  onSettings,
  onHelp,
  collapsed = false,
  user,
  onLogout,
  onMissionHQ,
}: {
  onRun: () => void
  active: string
  onNavigate: (s: string) => void
  cases: CaseRow[]
  activeCase: string | null
  onSelectCase: (id: string) => void
  onSettings: () => void
  onHelp: () => void
  collapsed?: boolean
  user?: AuthUser | null
  onLogout?: () => void
  onMissionHQ?: () => void
}) {
  const { t } = useTranslation()
  const displayName = user?.name || 'Commander'
  const displayRole = user?.role || 'Commander'
  const initials = displayName.slice(0, 2).toUpperCase()
  return (
    <aside
      className={`flex shrink-0 flex-col border-r border-border bg-sidebar transition-[width] duration-200 ${
        collapsed ? 'w-[68px]' : 'w-[248px]'
      }`}
    >
      {/* brand */}
      <div className={`flex items-center pb-4 pt-5 ${collapsed ? 'justify-center px-0' : 'px-5'}`}>
        {collapsed ? <AegisLogo size={32} /> : <AegisLogoFull />}
      </div>

      {/* run analysis */}
      <div className={collapsed ? 'px-3 pb-2' : 'px-4 pb-2'}>
        <button
          onClick={onRun}
          title={t('topbar.runAnalysis')}
          aria-label={t('topbar.runAnalysis')}
          data-tour="run"
          className={`flex w-full items-center justify-center gap-2 rounded-lg bg-blue text-[13.5px] font-semibold text-white shadow-lg shadow-blue/20 transition-all hover:bg-[#2f76e8] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60 ${
            collapsed ? 'h-10' : 'py-2.5'
          }`}
        >
          <Zap className="h-4 w-4 fill-white" />
          {!collapsed && t('topbar.runAnalysis')}
        </button>
      </div>

      <nav className="mt-3 flex-1 overflow-y-auto px-3">
        <div data-tour="nav">
        {NAV_GROUPS.map((group) => (
          <div key={group.titleKey} className="mb-1">
            {collapsed ? (
              <div className="mx-2 my-2 h-px bg-border/60" />
            ) : (
              <div className="px-2 pb-1.5 pt-2 text-[10px] font-semibold tracking-[0.14em] text-faint ltr:tracking-[0.14em] rtl:tracking-normal">
                {t(group.titleKey)}
              </div>
            )}
            {group.items.map((item) => {
              const on = active === item.key
              const Icon = item.icon
              const label = t(item.labelKey)
              return (
                <button
                  key={item.key}
                  onClick={() => onNavigate(item.key)}
                  data-tour={item.tourId}
                  title={collapsed ? label : undefined}
                  aria-label={label}
                  aria-current={on ? 'page' : undefined}
                  className={`group relative mb-0.5 flex w-full items-center gap-3 overflow-hidden rounded-lg px-3 py-2 text-[13.5px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60 ${
                    collapsed ? 'justify-center' : ''
                  } ${on ? 'bg-cardhi text-txt' : 'text-muted hover:bg-soft hover:text-txt'}`}
                >
                  {on && <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-blue rtl:left-auto rtl:right-0 rtl:rounded-l-full rtl:rounded-r-none" />}
                  <Icon className={`h-[18px] w-[18px] shrink-0 ${on ? 'text-blue' : 'text-muted group-hover:text-txt'}`} />
                  {!collapsed && <span className={on ? 'font-medium' : ''}>{label}</span>}
                </button>
              )
            })}
          </div>
        ))}
        </div>

        <div data-tour="cases">
        {!collapsed && (
          <div className="px-2 pb-1.5 pt-3 text-[10px] font-semibold text-faint ltr:tracking-[0.14em]">
            {t('nav.caseService')}
          </div>
        )}
        {collapsed && cases.length > 0 && <div className="mx-2 my-2 h-px bg-border/60" />}
        {!collapsed && cases.length === 0 && (
          <div className="px-3 py-2 text-[12px] text-faint">{t('general.loading')}</div>
        )}
        {cases.map((c) => {
          const on = activeCase === c.id
          return (
            <button
              key={c.id}
              onClick={() => onSelectCase(c.id)}
              dir={collapsed ? undefined : /[؀-ۿ]/.test(c.name) ? 'rtl' : 'ltr'}
              title={collapsed ? `${c.name} · ${c.score}` : undefined}
              aria-label={`${c.name} (${c.score} signals)`}
              aria-pressed={on}
              className={`group relative mb-0.5 flex w-full items-center gap-3 overflow-hidden rounded-lg px-3 py-2 text-[13.5px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60 ${
                collapsed ? 'justify-center' : ''
              } ${on ? 'bg-cardhi text-txt' : 'text-muted hover:bg-soft hover:text-txt'}`}
            >
              {on && <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-blue" />}
              <span className={`h-2 w-2 shrink-0 rounded-full ${dot[c.tone]} ${c.tone === 'danger' ? 'shadow-[0_0_6px_1px] shadow-danger/50' : ''}`} />
              {!collapsed && (
                <>
                  <span className={`truncate ${on ? 'font-medium' : 'group-hover:text-txt'}`}>{c.name}</span>
                  <span className={`ml-auto shrink-0 font-mono text-[11px] ${score[c.tone]}`}>{c.score}</span>
                </>
              )}
            </button>
          )
        })}
        </div>
      </nav>

      {/* footer */}
      <div className="border-t border-border px-3 py-3">
        <button
          onClick={onSettings}
          title={collapsed ? t('nav.settings') : undefined}
          aria-label={t('nav.settings')}
          className={`mb-0.5 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] text-muted transition-colors hover:bg-soft hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60 ${
            collapsed ? 'justify-center' : ''
          }`}
        >
          <Settings className="h-[18px] w-[18px] shrink-0" />
          {!collapsed && t('nav.settings')}
        </button>
        <button
          onClick={onHelp}
          title={collapsed ? t('nav.getHelp') : undefined}
          aria-label={t('nav.getHelp')}
          data-tour="help"
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] text-muted transition-colors hover:bg-soft hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60 ${
            collapsed ? 'justify-center' : ''
          }`}
        >
          <HelpCircle className="h-[18px] w-[18px] shrink-0" />
          {!collapsed && t('nav.getHelp')}
        </button>
        <button
          onClick={onMissionHQ}
          title={collapsed ? t('nav.missionHQ') : undefined}
          aria-label={t('nav.missionHQ')}
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] text-muted transition-colors hover:bg-soft hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60 ${
            collapsed ? 'justify-center' : ''
          }`}
        >
          <Home className="h-[18px] w-[18px] shrink-0" />
          {!collapsed && t('nav.missionHQ')}
        </button>
        <button
          onClick={onLogout}
          title={collapsed ? t('auth.logout') : undefined}
          aria-label={t('auth.logout')}
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] text-muted transition-colors hover:bg-soft hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60 ${
            collapsed ? 'justify-center' : ''
          }`}
        >
          <LogOut className="h-[18px] w-[18px] shrink-0" />
          {!collapsed && t('auth.logout')}
        </button>
        <div className={`mt-2 flex items-center gap-3 px-3 py-2 ${collapsed ? 'justify-center' : ''}`}>
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-cardhi text-[11px] font-semibold text-muted">
            {initials}
          </div>
          {!collapsed && (
            <div className="min-w-0 leading-tight">
              <div className="truncate text-[13px] font-medium text-txt" dir="auto">{displayName}</div>
              <div className="truncate text-[11px] text-faint" dir="auto">{displayRole}</div>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
