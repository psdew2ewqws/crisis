import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, FileDown, RotateCcw } from 'lucide-react'
import SimStepper from '../components/simulation/SimStepper'
import SimDiff from '../components/simulation/SimDiff'
import BeforeAfterChart from '../components/simulation/BeforeAfterChart'
import { simulationResult } from '../lib/data'
import { useWizardStore } from '../stores/wizardStore'

export default function Simulation() {
  const navigate = useNavigate()
  const sim = simulationResult
  const wizardOpen = useWizardStore((s) => s.open)
  const setGuard = useWizardStore((s) => s.setGuard)

  // Wizard guard: sim succeeded and risk reduced
  useEffect(() => {
    if (wizardOpen && sim.status === 'succeeded' && sim.after.nationalRisk < sim.before.nationalRisk) {
      setGuard(5, true)
    }
  }, [wizardOpen])

  return (
    <div className="mx-auto max-w-[1340px] px-8 py-7">
      <h1 className="text-[28px] font-semibold tracking-tight text-txt">Simulation Console</h1>
      <p className="mt-1.5 text-[14px] text-muted mb-6">
        WNTR/EPANET hydraulic re-simulation · Zarqa Trunk-Main Cascade
      </p>

      <div className="space-y-5">
        <SimStepper elapsed={sim.elapsedSeconds} estimated={sim.estimatedSeconds} />
        <SimDiff before={sim.before} after={sim.after} />
        <BeforeAfterChart />

        {/* artifact */}
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-5 py-3">
          <FileDown className="h-4 w-4 text-muted" />
          <span className="font-mono text-[13px] text-txt">{sim.artifactUrl}</span>
          <button className="ml-auto rounded-lg border border-border px-3 py-1.5 text-[12px] text-muted hover:text-txt hover:bg-cardhi">
            Download
          </button>
          <span className="text-[11px] text-faint">Stored in S3/MinIO · Full hydraulic output</span>
        </div>

        {/* actions */}
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 rounded-lg border border-border bg-card px-5 py-2.5 text-[13.5px] font-medium text-txt hover:bg-cardhi">
            <RotateCcw className="h-4 w-4" />
            Re-run with edits
          </button>
          <button
            onClick={() => {
              if (wizardOpen) {
                useWizardStore.getState().completeStep(5)
              }
              navigate('/case/zarqa-2025-08/decide')
            }}
            className="flex items-center gap-2 rounded-lg bg-blue px-5 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8]"
          >
            Promote to Decision
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
