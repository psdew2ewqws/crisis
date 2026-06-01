import { useNavigate } from 'react-router-dom'
import { RotateCcw } from 'lucide-react'
import { motion } from 'motion/react'
import ClosedLoopSummary from '../components/outcome/ClosedLoopSummary'
import TelemetryChart from '../components/outcome/TelemetryChart'
import LearnDiff from '../components/outcome/LearnDiff'
import { outcomeRecord } from '../lib/data'
import { useWizardStore } from '../stores/wizardStore'

const BASELINES: Record<string, { value: number; label: string }> = {
  '911 Call Volume': { value: 35, label: 'baseline' },
  'Hospital ED Load (%)': { value: 50, label: 'normal' },
  'Pipeline Pressure (bar)': { value: 2.0, label: 'nominal' },
}

export default function Outcome() {
  const navigate = useNavigate()
  const o = outcomeRecord
  const wizardReset = useWizardStore((s) => s.reset)

  const handleClose = () => {
    wizardReset()
    navigate('/')
  }

  return (
    <div className="mx-auto max-w-[1340px] px-8 py-7">
      <h1 className="text-[28px] font-semibold tracking-tight text-txt">Outcome &amp; Learn</h1>
      <p className="mt-1.5 text-[14px] text-muted mb-6">
        Post-action telemetry · Case closed · Zarqa Trunk-Main Cascade
      </p>

      <div className="space-y-5">
        <ClosedLoopSummary outcome={o} />

        {/* telemetry charts */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {o.telemetry.map((t, i) => {
            const bl = BASELINES[t.metric] ?? { value: 0, label: '' }
            return (
              <motion.div
                key={t.metric}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1, duration: 0.3 }}
              >
                <TelemetryChart
                  title={t.metric}
                  data={t.values}
                  trend={t.trend}
                  baseline={bl.value}
                  baselineLabel={bl.label}
                />
              </motion.div>
            )
          })}
        </div>

        <LearnDiff items={o.learned} />

        {/* actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleClose}
            className="rounded-lg bg-blue px-5 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8]"
          >
            Close Case
          </button>
          <button
            onClick={() => navigate('/case/zarqa-2025-08/graph')}
            className="flex items-center gap-2 rounded-lg border border-border bg-card px-5 py-2.5 text-[13.5px] font-medium text-txt hover:bg-cardhi"
          >
            <RotateCcw className="h-4 w-4" />
            Replay This Case
          </button>
        </div>
      </div>
    </div>
  )
}
