import { Suspense, lazy, useState, type ReactNode } from 'react'
import { Zap, Loader2 } from 'lucide-react'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import KpiCard from './components/KpiCard'
import SignalVolume from './components/SignalVolume'
import DataTable from './components/DataTable'
import LiveGraph from './components/LiveGraph'
import { kpis } from './lib/data'

const SignalsPage = lazy(() => import('./pages/SignalsPage'))
const RootCausePage = lazy(() => import('./pages/RootCausePage'))
const SolutionsPage = lazy(() => import('./pages/SolutionsPage'))
const SimulationPage = lazy(() => import('./pages/SimulationPage'))
const DecisionsPage = lazy(() => import('./pages/DecisionsPage'))
const DeepAnalysisPage = lazy(() => import('./pages/DeepAnalysisPage'))

function Loading() {
  return (
    <div className="grid min-h-0 flex-1 place-items-center text-muted">
      <Loader2 className="h-6 w-6 animate-spin" />
    </div>
  )
}

function DashboardView() {
  const [running, setRunning] = useState(false)
  const run = () => {
    if (running) return
    setRunning(true)
    setTimeout(() => setRunning(false), 1600)
  }
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[1340px] px-8 py-7">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-[28px] font-semibold tracking-tight text-txt">Dashboard</h1>
            <p className="mt-1.5 text-[14px] text-muted">
              Zarqa Trunk-Main Cascade · Zarqa North · <span className="font-medium text-danger">Critical</span>
            </p>
          </div>
          <button
            onClick={run}
            className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8]"
          >
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4 fill-white" />}
            {running ? 'Analyzing…' : 'Run Analysis'}
          </button>
        </div>
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {kpis.map((k) => (
            <KpiCard key={k.title} kpi={k} />
          ))}
        </div>
        <div className="mt-4"><SignalVolume /></div>
        <div className="mt-4"><DataTable onRun={run} /></div>
      </div>
    </div>
  )
}

export default function App() {
  const [view, setView] = useState('Dashboard')

  let content: ReactNode
  switch (view) {
    case 'Incident Graph': content = <LiveGraph />; break
    case 'Signals': content = <SignalsPage />; break
    case 'Root Cause': content = <RootCausePage />; break
    case 'Solutions': content = <SolutionsPage />; break
    case 'Simulation': content = <SimulationPage />; break
    case 'Decisions': content = <DecisionsPage />; break
    case 'Deep Analysis': content = <DeepAnalysisPage />; break
    default: content = <DashboardView />
  }

  return (
    <div className="flex h-screen overflow-hidden bg-bg text-txt">
      <Sidebar onRun={() => setView('Incident Graph')} active={view} onNavigate={setView} />
      <main className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <div className="flex min-h-0 flex-1 flex-col">
          <Suspense fallback={<Loading />}>{content}</Suspense>
        </div>
      </main>
    </div>
  )
}
