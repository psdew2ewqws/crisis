import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import RecommendationSummary from '../components/decision/RecommendationSummary'
import RiskDelta from '../components/decision/RiskDelta'
import RbacBadge from '../components/decision/RbacBadge'
import AuthorizeGate from '../components/decision/AuthorizeGate'
import { decisionRecord } from '../lib/data'
import { useWizardStore } from '../stores/wizardStore'

export default function DecisionHub() {
  const navigate = useNavigate()
  const d = decisionRecord
  const [justification, setJustification] = useState('')
  const [rejected, setRejected] = useState(false)
  const wizardOpen = useWizardStore((s) => s.open)
  const setGuard = useWizardStore((s) => s.setGuard)

  const canAuthorize = justification.trim().length >= 10

  const handleAuthorized = () => {
    if (wizardOpen) {
      setGuard(6, true)
      useWizardStore.getState().completeStep(6)
    }
    navigate('/case/zarqa-2025-08/outcome')
  }

  const handleReject = () => {
    setRejected(true)
    if (wizardOpen) useWizardStore.getState().reset()
    setTimeout(() => navigate('/'), 2000)
  }

  if (rejected) {
    return (
      <div className="mx-auto max-w-[1340px] px-8 py-7">
        <div className="mt-20 rounded-xl border border-danger/30 bg-danger/5 p-8 text-center">
          <div className="text-[16px] font-semibold text-danger">Case rejected. Returning to dashboard.</div>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[1340px] px-8 py-7">
      <h1 className="text-[28px] font-semibold tracking-tight text-txt">Decision Hub</h1>
      <p className="mt-1.5 text-[14px] text-muted mb-6">
        Human authorization gate · RBAC-controlled · Immutable audit trail
      </p>

      <div className="space-y-5">
        <RecommendationSummary decision={d} />
        <RiskDelta riskBefore={d.riskBefore} riskAfter={d.riskAfter} riskReduction={d.riskReduction} />
        <RbacBadge name={d.actor.name} role={d.actor.role} authLevel={d.actor.authLevel} />

        {/* audit preamble */}
        <div className="rounded-xl border border-border border-l-4 border-l-warn bg-card p-5">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-warn" />
            <span className="text-[13px] font-semibold text-txt">This action will:</span>
          </div>
          <ul className="space-y-1.5 pl-6">
            {d.auditActions.map((action, i) => (
              <li key={i} className="flex items-start gap-2 text-[13px] text-muted">
                <span className="mt-0.5 text-faint">•</span>
                {action}
              </li>
            ))}
          </ul>
        </div>

        {/* justification */}
        <div>
          <label className="text-[13px] font-medium text-txt">
            Justification <span className="text-faint">(required for audit trail)</span>
          </label>
          <textarea
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            placeholder="Enter justification for this authorization..."
            className="mt-2 w-full rounded-xl border border-border bg-bg p-4 text-[13px] text-txt placeholder:text-faint resize-none h-24 focus:border-blue focus:outline-none"
          />
        </div>

        {/* action buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/case/zarqa-2025-08/solutions')}
            className="rounded-lg border border-border bg-card px-5 py-2.5 text-[13.5px] font-medium text-txt hover:bg-cardhi"
          >
            Request Changes
          </button>
          <button
            onClick={handleReject}
            className="rounded-lg border border-danger/30 bg-danger/10 px-5 py-2.5 text-[13.5px] font-medium text-danger hover:bg-danger/20"
          >
            Reject
          </button>
          <div className="ml-auto">
            {canAuthorize ? (
              <AuthorizeGate onAuthorized={handleAuthorized} />
            ) : (
              <button
                disabled
                className="rounded-lg bg-card px-6 py-3 text-[16px] font-semibold text-faint cursor-not-allowed border border-border"
              >
                🔒 AUTHORIZE
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
