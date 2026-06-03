// Mission landing / hero (Phase 3). Shown full-screen (no shell) on first login and
// reachable any time via "Mission HQ". It frames what AEGIS does — a four-stage
// pipeline — and offers two ways in: Enter Console or Take the Tour. Fully bilingual.
import { useTranslation } from 'react-i18next'
import { Activity, Brain, Zap, MessageSquare, ArrowRight, Compass, type LucideIcon } from 'lucide-react'
import { PathsBackdrop } from './BackgroundPaths'
import { AegisLogoFull } from './AegisLogo'

interface Stage {
  icon: LucideIcon
  nameKey: string
  descKey: string
}

const STAGES: Stage[] = [
  { icon: Activity, nameKey: 'hero.stageMonitor', descKey: 'hero.monitor' },
  { icon: Brain, nameKey: 'hero.stageAnalyze', descKey: 'hero.analyze' },
  { icon: Zap, nameKey: 'hero.stageRespond', descKey: 'hero.respond' },
  { icon: MessageSquare, nameKey: 'hero.stageAssist', descKey: 'hero.assist' },
]

export default function Onboarding({ onEnter, onTour }: { onEnter: () => void; onTour: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="relative min-h-screen w-full overflow-y-auto bg-bg text-txt">
      <PathsBackdrop />
      <div className="relative z-10 mx-auto flex min-h-screen max-w-5xl flex-col items-center justify-center px-6 py-16 text-center">
        <AegisLogoFull size={44} />

        <h1 className="mt-8 bg-gradient-to-r from-txt to-muted bg-clip-text text-4xl font-bold tracking-tight text-transparent sm:text-6xl">
          {t('hero.welcome')}
        </h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-muted md:text-[16px]">
          {t('hero.subtitle')}
        </p>

        {/* pipeline */}
        <div className="mt-10 grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STAGES.map((s, i) => {
            const Icon = s.icon
            return (
              <div
                key={s.nameKey}
                className="relative rounded-xl border border-border bg-card/70 p-4 text-start backdrop-blur"
              >
                <div className="flex items-center gap-2.5">
                  <span className="grid h-8 w-8 place-items-center rounded-lg bg-blue/15 text-blue">
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="font-mono text-[11px] text-faint">0{i + 1}</span>
                </div>
                <div className="mt-3 text-[14px] font-semibold text-txt">{t(s.nameKey)}</div>
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{t(s.descKey)}</p>
              </div>
            )
          })}
        </div>

        {/* quick start */}
        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <button
            onClick={onEnter}
            className="flex items-center gap-2 rounded-xl bg-blue px-6 py-3 text-[14px] font-semibold text-white shadow-lg shadow-blue/20 transition-colors hover:bg-[#2f76e8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
          >
            {t('hero.enterConsole')}
            <ArrowRight className="h-4 w-4 rtl:rotate-180" />
          </button>
          <button
            onClick={onTour}
            className="flex items-center gap-2 rounded-xl border border-border bg-card/60 px-6 py-3 text-[14px] font-medium text-txt backdrop-blur transition-colors hover:bg-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
          >
            <Compass className="h-4 w-4 text-blue" />
            {t('hero.takeTour')}
          </button>
        </div>
      </div>
    </div>
  )
}
