import { Zap, Loader2, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import KpiCard from '../components/KpiCard'
import DataTable from '../components/DataTable'
import { kpis } from '../lib/data'
import { useAppStore } from '../stores/appStore'
import { useWizardStore } from '../stores/wizardStore'

export default function Dashboard() {
  const running = useAppStore((s) => s.running)
  const setRunning = useAppStore((s) => s.setRunning)
  const startTour = useWizardStore((s) => s.startTour)
  const navigate = useNavigate()

  const run = () => {
    if (running) return
    setRunning(true)
    startTour()
    navigate('/signals')
    setTimeout(() => setRunning(false), 1600)
  }

  return (
    <div className="mx-auto max-w-[1340px] px-8 py-7">
      {/* header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[28px] font-semibold tracking-tight text-txt">Dashboard</h1>
          <p className="mt-1.5 flex items-center gap-2 text-[14px] text-muted">
            Zarqa Trunk-Main Cascade · Zarqa North ·{' '}
            <span className="inline-flex items-center gap-1.5 font-medium text-danger">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-danger opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-danger" />
              </span>
              Critical
            </span>
          </p>
        </div>
        <button
          onClick={run}
          className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8]"
        >
          {running ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Zap className="h-4 w-4 fill-white" />
          )}
          {running ? 'Analyzing…' : 'Run Analysis'}
        </button>
      </div>

      {/* KPI cards */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((k, i) => (
          <motion.div
            key={k.title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08, duration: 0.3 }}
          >
            <KpiCard kpi={k} />
          </motion.div>
        ))}
      </div>

      {/* table */}
      <div className="mt-4">
        <DataTable onRun={run} />
      </div>

      {/* case summary card */}
      <button
        onClick={() => navigate('/case/zarqa-2025-08/graph')}
        className="mt-4 w-full text-left rounded-xl border border-border bg-card p-5 transition-colors hover:border-border/80 hover:bg-cardhi group"
      >
        <div className="flex items-start justify-between gap-6">
          <div>
            <div className="text-[15px] font-semibold text-txt">Case Summary</div>
            <p className="mt-1.5 text-[13px] text-muted leading-relaxed">
              Trunk-main pipe rupture (PIPE-ZN-44) in Zarqa Zone 3. Cascade affecting hospital
              operations, traffic, and emergency services.
            </p>
          </div>
          <div className="shrink-0 flex items-center gap-6">
            <div className="text-right">
              <div className="font-mono text-[11px] text-faint">Root Cause</div>
              <div className="font-mono text-[13px] text-txt">PIPE-ZN-44</div>
            </div>
            <div className="h-8 w-px bg-border" />
            <div className="text-right">
              <div className="font-mono text-[11px] text-faint">Confidence</div>
              <div className="font-mono text-[13px] text-good">0.91</div>
            </div>
            <div className="h-8 w-px bg-border" />
            <div className="text-right">
              <div className="font-mono text-[11px] text-faint">Status</div>
              <div className="text-[13px] text-warn">Awaiting Authorization</div>
            </div>
            <ArrowRight className="h-5 w-5 text-faint transition-colors group-hover:text-txt" />
          </div>
        </div>
      </button>
    </div>
  )
}
