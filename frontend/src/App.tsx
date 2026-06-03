import { Suspense, lazy, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Zap, Loader2, X, Check, LayoutGrid } from 'lucide-react'
import Sidebar, { type CaseRow } from './components/Sidebar'
import Topbar from './components/Topbar'
import KpiCard from './components/KpiCard'
import SignalVolume from './components/SignalVolume'
import DataTable from './components/DataTable'
import LiveGraph from './components/LiveGraph'
import Onboarding from './components/Onboarding'
import SettingsDrawer from './components/SettingsDrawer'
import HelpDrawer from './components/HelpDrawer'
import ErrorBoundary from './components/ErrorBoundary'
import MissionBriefing from './components/MissionBriefing'
import Tour from './components/Tour'
import { useLangStore } from './stores/langStore'
import { useAuthStore } from './stores/authStore'
import { kpis as fallbackKpis, type Kpi, type Tone } from './lib/data'
import { getKpis, getCases, runFlow, type CaseServiceRow, type FlowEvent } from './lib/voc'

const SignalsPage = lazy(() => import('./pages/SignalsPage'))
const RootCausePage = lazy(() => import('./pages/RootCausePage'))
const SolutionsPage = lazy(() => import('./pages/SolutionsPage'))
const SimulationPage = lazy(() => import('./pages/SimulationPage'))
const DecisionsPage = lazy(() => import('./pages/DecisionsPage'))
const DeepAnalysisPage = lazy(() => import('./pages/DeepAnalysisPage'))
const ExpertChatPage = lazy(() => import('./pages/ExpertChatPage'))
const AuthPage = lazy(() => import('./pages/AuthPage'))

function Loading() {
  return (
    <div className="grid min-h-0 flex-1 place-items-center text-muted">
      <Loader2 className="h-6 w-6 animate-spin" />
    </div>
  )
}

function fmtCount(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(n >= 10_000 ? 0 : 1)}k` : String(n)
}

// Real voc360 service → sidebar CASE row. Tone flags urgency by critical count.
function toCaseRow(s: CaseServiceRow): CaseRow {
  const tone: Tone = s.critical > 50 ? 'danger' : s.critical > 0 ? 'warn' : 'neutral'
  return { id: s.id, name: s.id, score: fmtCount(s.signals), tone }
}

/* ── live run progress (real streamed runFlow) ────────────────────────────── */
// The backend emits exactly these stages, each "running" then "done"; the final
// recommend.done detail carries the drafted recommendation text.
const STAGES = [
  { id: 'connect', label: 'Connect', hint: 'Connecting to voc360' },
  { id: 'ingest', label: 'Ingest', hint: 'Pulling citizen signals' },
  { id: 'graph', label: 'Graph', hint: 'Building dependency graph' },
  { id: 'rootcause', label: 'Root Cause', hint: 'Ranking problem clusters' },
  { id: 'recommend', label: 'Recommend', hint: 'Drafting recommendation' },
] as const

type StageState = 'idle' | 'running' | 'done'

interface RunState {
  active: boolean
  service: string | null
  stages: Record<string, StageState>
  details: Record<string, string>
  recommendation: string | null
  error: string | null
}

const idleRun: RunState = {
  active: false,
  service: null,
  stages: {},
  details: {},
  recommendation: null,
  error: null,
}

function RunProgress({ run, onClose }: { run: RunState; onClose: () => void }) {
  if (!run.active && !run.recommendation && !run.error) return null
  const finished = !!run.recommendation || !!run.error
  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/50 p-4">
      <div className="w-full max-w-lg overflow-hidden rounded-xl border border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <Zap className="h-4 w-4 fill-blue text-blue" />
            <div className="text-[14px] font-semibold text-txt">
              Deer Graph Analysis
              <span
                className="ml-2 font-mono text-[12px] font-normal text-muted"
                dir={/[؀-ۿ]/.test(run.service ?? '') ? 'rtl' : 'ltr'}
              >
                {run.service ?? 'All services'}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={!finished}
            title={finished ? 'Close' : 'Running…'}
            className="rounded-lg p-1.5 text-muted transition-colors hover:bg-soft hover:text-txt disabled:cursor-not-allowed disabled:opacity-40"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4">
          <ol className="space-y-2.5">
            {STAGES.map((st) => {
              const state: StageState = run.stages[st.id] ?? 'idle'
              const detail = run.details[st.id]
              return (
                <li key={st.id} className="flex items-start gap-3">
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center">
                    {state === 'done' ? (
                      <Check className="h-4 w-4 text-good" />
                    ) : state === 'running' ? (
                      <Loader2 className="h-4 w-4 animate-spin text-blue" />
                    ) : (
                      <span className="h-2 w-2 rounded-full bg-border" />
                    )}
                  </span>
                  <div className="min-w-0">
                    <div
                      className={`text-[13.5px] ${
                        state === 'idle' ? 'text-faint' : 'font-medium text-txt'
                      }`}
                    >
                      {st.label}
                    </div>
                    <div
                      className="truncate text-[12px] text-muted"
                      dir={/[؀-ۿ]/.test(detail ?? '') ? 'rtl' : 'ltr'}
                    >
                      {detail ?? st.hint}
                    </div>
                  </div>
                </li>
              )
            })}
          </ol>

          {run.recommendation && (
            <div className="mt-4 rounded-lg border border-blue/40 bg-blue/5 px-4 py-3">
              <div className="mb-1 text-[11px] font-semibold tracking-[0.12em] text-blue">
                RECOMMENDATION
              </div>
              <p
                className="text-[13.5px] leading-relaxed text-txt"
                dir={/[؀-ۿ]/.test(run.recommendation) ? 'rtl' : 'ltr'}
              >
                {run.recommendation}
              </p>
            </div>
          )}
          {run.error && (
            <div className="mt-4 rounded-lg border border-danger/40 bg-danger/5 px-4 py-3 text-[13px] text-danger">
              {run.error}
            </div>
          )}
        </div>

        {finished && (
          <div className="flex justify-end border-t border-border px-5 py-3">
            <button
              onClick={onClose}
              className="rounded-lg bg-blue px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[#2f76e8]"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function DashboardView({
  service,
  onRun,
  query,
  onTour,
  onNavigate,
}: {
  service: string | null
  onRun: () => void
  query: string
  onTour: () => void
  onNavigate: (view: string) => void
}) {
  const { t } = useTranslation()
  const [kpis, setKpis] = useState<Kpi[] | null>(null)

  useEffect(() => {
    let alive = true
    getKpis().then((r) => {
      if (alive) setKpis(r.kpis && r.kpis.length ? (r.kpis as unknown as Kpi[]) : fallbackKpis)
    })
    return () => {
      alive = false
    }
  }, [])

  const cards = kpis ?? fallbackKpis
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[1340px] px-8 py-7">
        <div>
          <h1 className="flex items-center gap-2.5 text-[28px] font-semibold tracking-tight text-txt">
            <LayoutGrid className="h-6 w-6 text-blue" />
            {t('nav.dashboard')}
          </h1>
          <p className="mt-1.5 text-[14px] text-muted">
            {t('dashboard.live')} ·{' '}
            <span className="font-medium text-txt" dir={/[؀-ۿ]/.test(service ?? '') ? 'rtl' : 'ltr'}>
              {service ?? t('dashboard.allServices')}
            </span>
          </p>
        </div>
        <div className="mt-6">
          <MissionBriefing onNavigate={onNavigate} onRun={onRun} onTour={onTour} />
        </div>
        <div data-tour="kpis" className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {cards.map((k, i) => (
            <KpiCard key={k.title} kpi={k} index={i} />
          ))}
        </div>
        <div className="mt-4"><SignalVolume service={service} /></div>
        <div className="mt-4"><DataTable onRun={onRun} service={service} query={query} /></div>
      </div>
    </div>
  )
}

export default function App() {
  // First login lands on the hero; returning (onboarded) users land on the Dashboard.
  const [view, setView] = useState(() =>
    typeof localStorage !== 'undefined' && localStorage.getItem('aegis-onboarded') !== null
      ? 'Dashboard'
      : 'hero',
  )
  const [services, setServices] = useState<CaseServiceRow[]>([])
  const [activeService, setActiveService] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [run, setRun] = useState<RunState>(idleRun)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => typeof localStorage !== 'undefined' && localStorage.getItem('aegis-sidebar-collapsed') === '1',
  )

  const toggleSidebar = () =>
    setSidebarCollapsed((prev) => {
      const next = !prev
      localStorage.setItem('aegis-sidebar-collapsed', next ? '1' : '0')
      return next
    })

  // First-run journey: the hero is a full-screen view shown on first login (and any
  // time via "Mission HQ"); the Mission Briefing + tour live inside the console.
  const [tourOpen, setTourOpen] = useState(false)

  const enterConsole = () => {
    localStorage.setItem('aegis-onboarded', '1')
    setView('Dashboard')
  }
  const goToHero = () => setView('hero')
  const startTour = () => {
    setView('Dashboard') // the tour anchors live on the console chrome
    setTourOpen(true)
  }
  const heroTakeTour = () => {
    enterConsole()
    setTourOpen(true)
  }

  // Global keyboard shortcuts (advertised in the Help drawer). Ignored while typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      if (e.key === '?') {
        e.preventDefault()
        setHelpOpen((v) => !v)
      } else if (e.key === '[') {
        e.preventDefault()
        toggleSidebar()
      } else if (e.key === 'Escape') {
        if (tourOpen) setTourOpen(false)
        else if (helpOpen) setHelpOpen(false)
        else if (settingsOpen) setSettingsOpen(false)
        else if (run.recommendation || run.error) setRun(idleRun)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [tourOpen, helpOpen, settingsOpen, run])

  // Auth gate (client-side only — see authStore).
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const authUser = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  // Apply the persisted language's dir/lang to <html> on mount (langStore also does
  // this at import, but this guards StrictMode remounts and any DOM resets).
  const lang = useLangStore((s) => s.lang)
  useEffect(() => {
    document.documentElement.setAttribute('lang', lang)
    document.documentElement.setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr')
  }, [lang])

  useEffect(() => {
    let alive = true
    getCases().then((r) => {
      if (!alive) return
      const sorted = [...(r.services ?? [])].sort(
        (a, b) => b.critical - a.critical || b.signals - a.signals,
      )
      setServices(sorted.slice(0, 8))
    })
    return () => {
      alive = false
    }
  }, [])

  const cases = useMemo<CaseRow[]>(() => services.map(toCaseRow), [services])

  const selectCase = (id: string) => {
    setActiveService((prev) => (prev === id ? null : id)) // click again to clear filter
    setView('Dashboard')
  }

  // Real streamed Deer Graph run against the active service. Drives the live
  // progress overlay; the final recommend.done detail is the recommendation.
  const runAnalysis = async () => {
    if (run.active) return
    const service = activeService
    setRun({ ...idleRun, active: true, service })
    try {
      for await (const ev of runFlow(service ?? undefined) as AsyncGenerator<FlowEvent>) {
        setRun((prev) => {
          const next: RunState = {
            ...prev,
            stages: { ...prev.stages, [ev.stage]: ev.status === 'done' ? 'done' : 'running' },
            details: { ...prev.details, [ev.stage]: ev.detail },
          }
          if (ev.stage === 'recommend' && ev.status === 'done') next.recommendation = ev.detail
          return next
        })
      }
      setRun((prev) => ({ ...prev, active: false }))
    } catch (e) {
      setRun((prev) => ({
        ...prev,
        active: false,
        error: e instanceof Error ? e.message : 'Analysis failed to stream.',
      }))
    }
  }

  // Sidebar "Run Analysis": show the live reactflow canvas AND stream the run.
  const runFromSidebar = () => {
    setView('Incident Graph')
    runAnalysis()
  }

  // Auth gate wraps everything — unauthenticated users only see the login/signup page.
  if (!isAuthenticated) {
    return (
      <Suspense fallback={<Loading />}>
        <AuthPage />
      </Suspense>
    )
  }

  // Hero is a full-screen view (no shell) — first login, or any time via Mission HQ.
  if (view === 'hero') {
    return <Onboarding onEnter={enterConsole} onTour={heroTakeTour} />
  }

  let content: ReactNode
  switch (view) {
    case 'Incident Graph': content = <LiveGraph />; break
    case 'Signals': content = <SignalsPage />; break
    case 'Root Cause': content = <RootCausePage />; break
    case 'Solutions': content = <SolutionsPage />; break
    case 'Simulation': content = <SimulationPage />; break
    case 'Decisions': content = <DecisionsPage />; break
    case 'Deep Analysis': content = <DeepAnalysisPage />; break
    case 'Expert Chat': content = <ExpertChatPage />; break
    default:
      content = (
        <DashboardView
          service={activeService}
          onRun={runAnalysis}
          query={search}
          onTour={startTour}
          onNavigate={setView}
        />
      )
  }

  return (
    <div className="flex h-screen overflow-hidden bg-bg text-txt">
      <Sidebar
        onRun={runFromSidebar}
        active={view}
        onNavigate={setView}
        cases={cases}
        activeCase={activeService}
        onSelectCase={selectCase}
        onSettings={() => setSettingsOpen(true)}
        onHelp={() => setHelpOpen(true)}
        collapsed={sidebarCollapsed}
        user={authUser}
        onLogout={logout}
        onMissionHQ={goToHero}
      />
      <main className="flex min-w-0 flex-1 flex-col">
        <Topbar
          crumb={activeService ?? undefined}
          query={search}
          onSearch={setSearch}
          onBell={() => setHelpOpen(true)}
          onToggleSidebar={toggleSidebar}
        />
        <div className="flex min-h-0 flex-1 flex-col">
          <ErrorBoundary key={view} onReset={() => setView('Dashboard')}>
            <Suspense fallback={<Loading />}>{content}</Suspense>
          </ErrorBoundary>
        </div>
      </main>

      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        leftOffset={sidebarCollapsed ? 68 : 248}
      />
      <HelpDrawer
        open={helpOpen}
        onClose={() => setHelpOpen(false)}
        leftOffset={sidebarCollapsed ? 68 : 248}
        onReplayTour={() => {
          setHelpOpen(false)
          startTour()
        }}
      />
      <Tour open={tourOpen} onClose={() => setTourOpen(false)} />
      <RunProgress run={run} onClose={() => setRun(idleRun)} />
    </div>
  )
}
