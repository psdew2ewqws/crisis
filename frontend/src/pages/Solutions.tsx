import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { motion } from 'motion/react'
import InterventionCard from '../components/solutions/InterventionCard'
import TradeoffChart from '../components/solutions/TradeoffChart'
import { interventions, constraintSummary } from '../lib/data'
import { useWizardStore } from '../stores/wizardStore'

export default function Solutions() {
  const navigate = useNavigate()
  const [selectedId, setSelectedId] = useState('SOL-A')
  const wizardOpen = useWizardStore((s) => s.open)
  const setGuard = useWizardStore((s) => s.setGuard)

  // Wizard guard: solution selected
  useEffect(() => {
    if (wizardOpen) setGuard(4, !!selectedId)
  }, [wizardOpen, selectedId])

  const handleSelect = (id: string) => {
    setSelectedId(id)
  }

  return (
    <div className="mx-auto max-w-[1340px] px-8 py-7">
      <h1 className="text-[28px] font-semibold tracking-tight text-txt">Candidate Solutions</h1>
      <p className="mt-1.5 text-[14px] text-muted mb-6">
        OR-Tools optimization · {interventions.length} candidates · Zarqa Trunk-Main Cascade
      </p>

      {/* intervention cards */}
      <div className="space-y-4">
        {interventions.map((iv, i) => (
          <motion.div
            key={iv.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1, duration: 0.3 }}
          >
            <InterventionCard
              intervention={iv}
              selected={selectedId === iv.id}
              onSelect={() => handleSelect(iv.id)}
            />
          </motion.div>
        ))}
      </div>

      {/* tradeoff chart */}
      <div className="mt-5">
        <TradeoffChart interventions={interventions} />
      </div>

      {/* constraint summary */}
      <div className="mt-5 rounded-xl border border-border bg-card p-4">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">AVAILABLE TANKERS</div>
            <div className="mt-0.5 font-mono text-[14px] text-txt">
              {constraintSummary.availableTankers.used}/{constraintSummary.availableTankers.total}
            </div>
          </div>
          <div className="border-l border-r border-border">
            <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">BYPASS CAPACITY</div>
            <div className="mt-0.5 font-mono text-[14px] text-txt">{constraintSummary.bypassCapacity}</div>
          </div>
          <div>
            <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">AUTHORIZATION</div>
            <div className="mt-0.5 text-[14px] text-warn">Required</div>
          </div>
        </div>
      </div>

      {/* action */}
      <div className="mt-6 flex justify-end">
        <button
          onClick={() => {
            if (wizardOpen) {
              useWizardStore.getState().completeStep(4)
            }
            navigate('/case/zarqa-2025-08/sim')
          }}
          disabled={!selectedId}
          className="flex items-center gap-2 rounded-lg bg-blue px-5 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-40"
        >
          Select &amp; Validate
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
