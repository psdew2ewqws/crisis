import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowRight, RotateCcw } from 'lucide-react'
import { motion } from 'motion/react'
import ApexCard from '../components/rca/ApexCard'
import EvidenceTrail from '../components/rca/EvidenceTrail'
import CandidateTable from '../components/rca/CandidateTable'
import ConfidenceMeter from '../components/rca/ConfidenceMeter'
import { rootCauseResult } from '../lib/data'
import { useWizardStore } from '../stores/wizardStore'

export default function RootCause() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [challenged, setChallenged] = useState(false)
  const wizardOpen = useWizardStore((s) => s.open)
  const setGuard = useWizardStore((s) => s.setGuard)

  const handleAccept = () => {
    if (wizardOpen) {
      setGuard(3, true)
      useWizardStore.getState().completeStep(3)
    }
    navigate(`/case/${id}/solutions`)
  }

  const handleChallenge = () => {
    setChallenged(true)
    setTimeout(() => setChallenged(false), 2000)
  }

  return (
    <div className="mx-auto max-w-[1340px] px-8 py-7">
      <h1 className="text-[28px] font-semibold tracking-tight text-txt">Root-Cause Analysis</h1>
      <p className="mt-1.5 text-[14px] text-muted mb-6">
        Causal apex identification and evidence trail for case {id}
      </p>

      <div className="space-y-5">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <ApexCard rca={rootCauseResult} />
        </motion.div>
        <EvidenceTrail evidence={rootCauseResult.evidence} />
        <CandidateTable candidates={rootCauseResult.candidates} />
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.5 }}
        >
          <ConfidenceMeter value={rootCauseResult.confidence} threshold={0.70} />
        </motion.div>

        {/* action buttons */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleAccept}
            className="flex items-center gap-2 rounded-lg bg-blue px-5 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8]"
          >
            Accept Root Cause
            <ArrowRight className="h-4 w-4" />
          </button>
          <button
            onClick={handleChallenge}
            disabled={challenged}
            className="flex items-center gap-2 rounded-lg border border-border bg-card px-5 py-2.5 text-[13.5px] font-medium text-txt transition-colors hover:bg-cardhi disabled:opacity-50"
          >
            <RotateCcw className="h-4 w-4" />
            Challenge
          </button>
        </div>

        {/* challenge toast */}
        {challenged && (
          <div className="rounded-lg border border-warn/30 bg-warn/10 px-4 py-2.5 text-[13px] text-warn animate-pulse">
            Re-analysis queued — recalculating causal graph…
          </div>
        )}
      </div>
    </div>
  )
}
