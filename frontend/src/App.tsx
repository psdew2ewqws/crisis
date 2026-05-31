import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import TopBar from './components/TopBar'
import SignalFeed from './components/SignalFeed'
import IncidentGraph from './components/IncidentGraph'
import RiskGauge from './components/RiskGauge'
import WizardRail, { STEPS } from './components/WizardRail'
import RootCausePanel from './components/RootCausePanel'
import SolutionReview from './components/SolutionReview'
import SimulationConsole from './components/SimulationConsole'
import DecisionHub from './components/DecisionHub'
import { signals, incident, rootCause, solutions, sim } from './data/zarqa'

const HINT = [
  'Six signals from four agencies are streaming in. The loudest is a 911 surge (+320%) — but watch the quiet SCADA pressure drop on PIPE-ZN-44.',
  'Signals are stitched into one incident by shared dependency paths: five entities, four causal edges. The graph is the connective tissue.',
  'Backward causal traversal isolates the trunk-main rupture as the apex. The loud symptoms are rejected.',
  'The engine proposes interventions that act on the cause — not the symptoms. Pick one to validate.',
  'Each candidate is re-simulated on the hydraulic twin. A valid fix must drop the risk index versus no action.',
  'A human with decision_authority must authorize before anything is tasked. This is a hard gate.',
  'Intervention authorized and logged to the audit trail. The outcome feeds back to recalibrate the models — the loop closes.',
]

export default function App() {
  const [step, setStep] = useState(0)
  const [pick, setPick] = useState(0)
  const [authorized, setAuthorized] = useState(false)
  const last = STEPS.length - 1
  const risk = authorized ? sim.riskAfter : incident.riskIndex
  const chosen = solutions[pick]

  const dock = () => {
    if (step === 2) return <RootCausePanel rc={rootCause} />
    if (step === 3) return <SolutionReview solutions={solutions} current={pick} onPick={setPick} />
    if (step === 4) return <SimulationConsole sim={sim} />
    if (step === 5)
      return (
        <DecisionHub
          solution={chosen}
          authorized={authorized}
          onAuthorize={() => {
            setAuthorized(true)
            setTimeout(() => setStep(6), 750)
          }}
        />
      )
    return (
      <div className="grid h-full place-items-center px-8 text-center">
        <p className="max-w-2xl text-[13px] leading-relaxed text-muted">{HINT[step]}</p>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col">
      <TopBar risk={risk} title={incident.title} />
      <div className="grid min-h-0 flex-1 grid-cols-[300px_1fr_320px] gap-3 p-3">
        <SignalFeed signals={signals} highlight={step === 0} />

        <div className="flex min-h-0 flex-col gap-3">
          <div className="min-h-0 flex-1">
            <IncidentGraph incident={incident} />
          </div>
          <div className="h-[268px] rounded-md border border-hair bg-panel/60 p-3 shadow-panel">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="grid h-5 w-5 place-items-center rounded-sm bg-signal/15 font-mono text-[11px] text-signal">
                  {step + 1}
                </span>
                <span className="font-display text-[13px] tracking-wide text-txt">{STEPS[step]}</span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setStep(Math.max(0, step - 1))}
                  disabled={step === 0}
                  className="grid h-7 w-7 place-items-center rounded-sm border border-hair text-muted hover:bg-raised disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setStep(Math.min(last, step + 1))}
                  disabled={step === last || (step === 5 && !authorized)}
                  className="flex h-7 items-center gap-1 rounded-sm border border-hair px-2.5 text-muted hover:bg-raised disabled:opacity-40"
                >
                  <span className="font-mono text-[11px]">{step === 5 ? 'authorize first' : 'next'}</span>
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -24 }}
                transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                className="h-[206px]"
              >
                {dock()}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>

        <div className="flex min-h-0 flex-col gap-3">
          <div className="grid place-items-center rounded-md border border-hair bg-panel py-5 shadow-panel">
            <RiskGauge value={risk} />
            <div className="mt-2 font-mono text-[10px] tracking-[0.14em] text-muted">
              {incident.caseId.toUpperCase()}
            </div>
          </div>
          <div className="min-h-0 flex-1">
            <WizardRail step={step} authorized={authorized} onJump={setStep} />
          </div>
        </div>
      </div>
    </div>
  )
}
