// MissionBriefing (Phase 3) — replaces the one-shot WelcomeCard. A collapsible panel
// at the top of the Dashboard that is ALWAYS available (the user can collapse it but it
// never permanently disappears). Collapsed state persists in localStorage. The four
// step boxes navigate to their stage; quick actions run analysis, jump to Signals, or
// replay the tour.
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Shield,
  ChevronDown,
  ChevronUp,
  Activity,
  Target,
  FlaskConical,
  PenLine,
  Zap,
  Compass,
  type LucideIcon,
} from 'lucide-react'

const STEPS: { n: number; key: string; icon: LucideIcon; view: string }[] = [
  { n: 1, key: 'briefing.step1', icon: Activity, view: 'Signals' },
  { n: 2, key: 'briefing.step2', icon: Target, view: 'Root Cause' },
  { n: 3, key: 'briefing.step3', icon: FlaskConical, view: 'Solutions' },
  { n: 4, key: 'briefing.step4', icon: PenLine, view: 'Decisions' },
]

export default function MissionBriefing({
  onNavigate,
  onRun,
  onTour,
}: {
  onNavigate: (view: string) => void
  onRun: () => void
  onTour: () => void
}) {
  const { t } = useTranslation()
  const [collapsed, setCollapsed] = useState(
    () => typeof localStorage !== 'undefined' && localStorage.getItem('aegis-briefing-collapsed') === '1',
  )
  const toggle = () =>
    setCollapsed((prev) => {
      const next = !prev
      localStorage.setItem('aegis-briefing-collapsed', next ? '1' : '0')
      return next
    })

  return (
    <div className="overflow-hidden rounded-xl border border-blue/30 bg-gradient-to-br from-blue/10 via-card to-card">
      <button
        onClick={toggle}
        aria-expanded={!collapsed}
        className="flex w-full items-center justify-between px-5 py-3.5 text-start transition-colors hover:bg-blue/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
      >
        <span className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-blue/15 text-blue">
            <Shield className="h-4 w-4" />
          </span>
          <span>
            <span className="block text-[15px] font-semibold text-txt">{t('briefing.title')}</span>
            {!collapsed && <span className="block text-[12px] text-muted">{t('briefing.subtitle')}</span>}
          </span>
        </span>
        {collapsed ? (
          <ChevronDown className="h-4 w-4 text-muted" />
        ) : (
          <ChevronUp className="h-4 w-4 text-muted" />
        )}
      </button>

      {!collapsed && (
        <div className="px-5 pb-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => {
              const Icon = s.icon
              return (
                <button
                  key={s.n}
                  onClick={() => onNavigate(s.view)}
                  className="rounded-lg border border-border bg-bg/60 p-3.5 text-start transition-colors hover:border-blue/40 hover:bg-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-blue/15 font-mono text-[12px] font-semibold text-blue">
                      {s.n}
                    </span>
                    <Icon className="h-4 w-4 text-muted" />
                  </div>
                  <div className="mt-2 text-[13px] font-medium text-txt">{t(s.key)}</div>
                </button>
              )
            })}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2.5">
            <button
              onClick={onRun}
              className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[#2f76e8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
            >
              <Zap className="h-3.5 w-3.5 fill-white" />
              {t('topbar.runAnalysis')}
            </button>
            <button
              onClick={() => onNavigate('Signals')}
              className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-[13px] font-medium text-txt transition-colors hover:bg-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
            >
              <Activity className="h-3.5 w-3.5 text-blue" />
              {t('briefing.viewSignals')}
            </button>
            <button
              onClick={onTour}
              className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-[13px] font-medium text-txt transition-colors hover:bg-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
            >
              <Compass className="h-3.5 w-3.5 text-blue" />
              {t('briefing.replayTour')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
