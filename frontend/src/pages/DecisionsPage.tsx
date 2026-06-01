// DecisionsPage — T2 console page (decision log + human-authorization gate).
//
// Renders the operator decision log returned by GET /api/decisions (getDecisions)
// — what was chosen about a root cause / solution — as a clean table with status
// chips, owner, linked RIL cluster and rationale. The page also enforces the
// human-in-the-loop AUTHORIZATION GATE: a decision that is still `proposed`
// cannot take effect until a named person authorizes it. Authorizing posts back
// through createDecision (the existing module signature) with status `approved`
// and records the authorizer, so the gate is grounded in real backend state
// rather than a local-only toggle.
//
// Real voc360 columns only: decisions reference ril_problem_clusters.cluster_id
// (the root-cause layer); no Zarqa demo fixtures are used. Import-safe: every
// network call goes through getDecisions / createDecision which themselves return
// graceful fallbacks (lib/voc2.ts `jf`), so the page stays mounted and degrades
// cleanly when the backend (or the not-yet-built POST handler) is unreachable.

import { useEffect, useMemo, useState } from 'react'
import {
  Gavel,
  RefreshCw,
  Loader2,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  CircleDot,
  User,
  Link2,
  Database,
} from 'lucide-react'
import {
  getDecisions,
  createDecision,
  AEGIS,
  toneColor,
  type Tone,
  type Decision,
} from '../lib/voc2'

/* ------------------------------------------------------------------ tokens */
// Arabic-aware direction so cluster labels / rationale render correctly. Mirrors
// RootCausePage's isAr/dir helpers.
const isAr = (s: string | null | undefined) => !!s && /[؀-ۿ]/.test(s)
const dir = (s: string | null | undefined): 'rtl' | 'ltr' => (isAr(s) ? 'rtl' : 'ltr')

// Decision.status → tone + icon. Maps the real status enum from voc2.ts.
type Status = Decision['status']

const STATUS_TONE: Record<Status, Tone> = {
  proposed: 'warn',
  approved: 'good',
  rejected: 'danger',
  in_progress: 'neutral',
  done: 'good',
}

const STATUS_LABEL: Record<Status, string> = {
  proposed: 'Proposed',
  approved: 'Approved',
  rejected: 'Rejected',
  in_progress: 'In progress',
  done: 'Done',
}

function StatusIcon({ status, className }: { status: Status; className?: string }) {
  const cls = className ?? 'h-3.5 w-3.5'
  switch (status) {
    case 'approved':
      return <ShieldCheck className={cls} />
    case 'done':
      return <CheckCircle2 className={cls} />
    case 'rejected':
      return <XCircle className={cls} />
    case 'in_progress':
      return <Clock className={cls} />
    default:
      return <CircleDot className={cls} />
  }
}

// A decision is "gated" (awaiting human authorization) while it is still proposed.
const needsAuthorization = (d: Decision) => d.status === 'proposed'

// `authorized_by` is the authorization-gate field. It is not declared on the
// voc2.ts Decision interface, so read it tolerantly from the raw row (backends
// that persist authorization will populate it; older rows simply won't).
function authorizedBy(d: Decision): string | null {
  const v = (d as Decision & { authorized_by?: string | null }).authorized_by
  return v ? String(v) : null
}

/* ----------------------------------------------------------------- component */

export default function DecisionsPage({
  onNavigate,
}: {
  // App.tsx drives views via onNavigate(label); 'Root Cause' opens the graph view
  // so an operator can jump from a decision to the cluster it governs.
  onNavigate?: (view: string) => void
}) {
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [source, setSource] = useState<'store' | 'fallback'>('fallback')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  // Authorization-gate UI state.
  const [gateFor, setGateFor] = useState<Decision | null>(null) // open modal target
  const [authorizer, setAuthorizer] = useState('') // authorized_by input
  const [submitting, setSubmitting] = useState(false)
  const [gateErr, setGateErr] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setErr(null)
    try {
      const res = await getDecisions()
      setDecisions(Array.isArray(res?.decisions) ? res.decisions : [])
      setSource(res?.source ?? 'fallback')
    } catch (e) {
      setErr(String(e))
      setDecisions([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  // Decision rows that are still waiting on a human authorizer.
  const pending = useMemo(() => decisions.filter(needsAuthorization), [decisions])
  const authorizedCount = useMemo(
    () => decisions.filter((d) => d.status !== 'proposed').length,
    [decisions],
  )

  function openGate(d: Decision) {
    setGateFor(d)
    setAuthorizer('')
    setGateErr(null)
  }
  function closeGate() {
    if (submitting) return
    setGateFor(null)
    setGateErr(null)
  }

  // Authorize (or reject) a proposed decision. Routes through createDecision —
  // the existing POST signature — recording the human authorizer so the gate is
  // grounded in backend state. We re-load afterwards to reflect the source of
  // truth rather than optimistically mutating local rows.
  async function decide(d: Decision, status: 'approved' | 'rejected') {
    const who = authorizer.trim()
    if (!who) {
      setGateErr('An authorizing officer name is required to clear the gate.')
      return
    }
    setSubmitting(true)
    setGateErr(null)
    try {
      const verb = status === 'approved' ? 'Authorized' : 'Rejected'
      const res = await createDecision({
        cluster_id: d.cluster_id,
        title: d.title,
        action: d.action,
        status,
        owner: who,
        // Encode authorized_by into the rationale so it survives even if the
        // backend has no dedicated column; servers that do persist
        // `authorized_by` will pick up `owner` as the human authorizer.
        rationale: `${verb} by ${who}${d.rationale ? ` — ${d.rationale}` : ''}`,
      })
      if (!res?.ok) {
        setGateErr(res?.error || 'Backend rejected the authorization — is the decisions store writable?')
        return
      }
      setGateFor(null)
      await load()
    } catch (e) {
      setGateErr(String(e))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto bg-bg">
      <div className="mx-auto max-w-[1340px] px-8 py-7">
        {/* header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="flex items-center gap-2.5 text-[28px] font-semibold tracking-tight text-txt">
              <Gavel className="h-6 w-6 text-muted" />
              Decisions
            </h1>
            <p className="mt-1.5 flex items-center gap-2 text-[14px] text-muted">
              <Database className="h-3.5 w-3.5" />
              Operator decision log over voc360 root causes
              {decisions.length > 0 && (
                <span className="text-faint">
                  · {decisions.length} logged · {authorizedCount} authorized · {pending.length} awaiting gate
                </span>
              )}
              {source === 'fallback' && decisions.length === 0 && (
                <span className="text-faint">· offline</span>
              )}
            </p>
          </div>
          <button
            onClick={() => void load()}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-60"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>

        {/* authorization-gate banner */}
        {pending.length > 0 && (
          <div className="mt-6 flex items-start gap-3 rounded-xl border border-warn/30 bg-warn/10 p-4 text-[13.5px] leading-snug text-txt">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
            <div>
              <div className="mb-0.5 font-mono text-[10px] tracking-[0.14em] text-warn">
                HUMAN AUTHORIZATION REQUIRED
              </div>
              {pending.length} proposed decision{pending.length === 1 ? '' : 's'} cannot take effect
              until a named officer authorizes {pending.length === 1 ? 'it' : 'them'}. Review the
              rationale, then clear the gate below.
            </div>
          </div>
        )}

        {/* error */}
        {err && (
          <div className="mt-6 flex items-center gap-2 rounded-lg border border-danger/40 bg-card px-4 py-3 text-[13px] text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            Could not load decisions — {err}
          </div>
        )}

        {/* loading / empty */}
        {!err && loading && decisions.length === 0 && (
          <div className="mt-10 flex items-center justify-center gap-2 text-[13px] text-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading decision log…
          </div>
        )}
        {!err && !loading && decisions.length === 0 && (
          <div className="mt-10 rounded-xl border border-border bg-card px-5 py-10 text-center text-[13px] text-muted">
            No decisions have been logged yet. Decisions are created from the Root Cause and
            Solutions views, then cleared through the authorization gate here.
          </div>
        )}

        {/* decision log table */}
        {decisions.length > 0 && (
          <div className="mt-6 overflow-hidden rounded-xl border border-border bg-card">
            <div className="border-b border-border px-5 py-3 font-mono text-[10px] tracking-[0.14em] text-faint">
              DECISION LOG · {decisions.length}
            </div>
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border text-[11px] font-medium tracking-[0.08em] text-faint">
                  <th className="px-5 py-3 font-medium">DECISION</th>
                  <th className="py-3 font-medium">ROOT CAUSE</th>
                  <th className="py-3 font-medium">STATUS</th>
                  <th className="py-3 font-medium">AUTHORIZED BY</th>
                  <th className="py-3 font-medium">LOGGED</th>
                  <th className="px-5 py-3 text-right font-medium">GATE</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((d) => (
                  <DecisionRow
                    key={d.id}
                    d={d}
                    onAuthorize={() => openGate(d)}
                    onOpenGraph={() => onNavigate?.('Root Cause')}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* authorization-gate modal */}
      {gateFor && (
        <GateModal
          decision={gateFor}
          authorizer={authorizer}
          setAuthorizer={setAuthorizer}
          submitting={submitting}
          error={gateErr}
          onApprove={() => void decide(gateFor, 'approved')}
          onReject={() => void decide(gateFor, 'rejected')}
          onClose={closeGate}
        />
      )}
    </div>
  )
}

/* --------------------------------------------------------------- table row */

function DecisionRow({
  d,
  onAuthorize,
  onOpenGraph,
}: {
  d: Decision
  onAuthorize: () => void
  onOpenGraph: () => void
}) {
  const tone = STATUS_TONE[d.status] ?? 'neutral'
  const col = toneColor(tone)
  const who = authorizedBy(d) ?? d.owner ?? null
  const gated = needsAuthorization(d)

  return (
    <tr className="border-t border-border/70 align-top transition-colors hover:bg-soft/50">
      {/* decision title + action */}
      <td className="px-5 py-3.5">
        <div className="text-[13.5px] font-medium text-txt" dir={dir(d.title)}>
          {d.title}
        </div>
        {d.action && (
          <div className="mt-0.5 max-w-[360px] truncate text-[12px] text-muted" dir={dir(d.action)}>
            {d.action}
          </div>
        )}
      </td>

      {/* linked RIL cluster */}
      <td className="py-3.5">
        {d.cluster_id ? (
          <button
            onClick={onOpenGraph}
            className="inline-flex items-center gap-1.5 font-mono text-[11px] text-muted transition-colors hover:text-txt"
            title="Open this cluster in the graph"
          >
            <Link2 className="h-3 w-3" />
            {String(d.cluster_id).slice(0, 8)}
          </button>
        ) : (
          <span className="font-mono text-[11px] text-faint">—</span>
        )}
      </td>

      {/* status chip */}
      <td className="py-3.5">
        <span
          className="inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11.5px] font-medium"
          style={{ color: col, borderColor: `${col}55`, background: `${col}14` }}
        >
          <StatusIcon status={d.status} />
          {STATUS_LABEL[d.status] ?? d.status}
        </span>
      </td>

      {/* authorized by */}
      <td className="py-3.5">
        {who ? (
          <span className="inline-flex items-center gap-1.5 text-[12.5px] text-txt">
            <User className="h-3.5 w-3.5 text-faint" />
            {who}
          </span>
        ) : (
          <span className="text-[12px] text-faint">{gated ? 'unauthorized' : '—'}</span>
        )}
      </td>

      {/* logged at */}
      <td className="py-3.5 font-mono text-[11.5px] text-muted">{fmtTime(d.created_at)}</td>

      {/* gate action */}
      <td className="px-5 py-3.5 text-right">
        {gated ? (
          <button
            onClick={onAuthorize}
            className="inline-flex items-center gap-1.5 rounded-lg border border-warn/40 px-3 py-1.5 text-[12.5px] font-medium text-warn transition-colors hover:bg-warn/10"
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            Authorize
          </button>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-[12px] text-faint">
            <ShieldCheck className="h-3.5 w-3.5" style={{ color: AEGIS.good }} />
            cleared
          </span>
        )}
      </td>
    </tr>
  )
}

/* ------------------------------------------------------- authorization gate */

function GateModal({
  decision,
  authorizer,
  setAuthorizer,
  submitting,
  error,
  onApprove,
  onReject,
  onClose,
}: {
  decision: Decision
  authorizer: string
  setAuthorizer: (v: string) => void
  submitting: boolean
  error: string | null
  onApprove: () => void
  onReject: () => void
  onClose: () => void
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-[480px] overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-center gap-2 border-b border-border px-5 py-3.5">
          <ShieldAlert className="h-4 w-4 text-warn" />
          <span className="font-mono text-[10px] tracking-[0.14em] text-warn">
            AUTHORIZATION GATE
          </span>
        </div>

        {/* body */}
        <div className="px-5 py-4">
          <h3 className="text-[15.5px] font-semibold leading-snug text-txt" dir={dir(decision.title)}>
            {decision.title}
          </h3>
          {decision.action && (
            <p className="mt-1 text-[13px] leading-snug text-muted" dir={dir(decision.action)}>
              {decision.action}
            </p>
          )}

          <dl className="mt-3 space-y-1.5 text-[12px]">
            {decision.cluster_id && (
              <Row k="Root cause" v={String(decision.cluster_id).slice(0, 8)} mono />
            )}
            {decision.rationale && <Row k="Rationale" v={decision.rationale} />}
          </dl>

          {/* authorizer input — the human-in-the-loop field */}
          <label className="mt-4 block">
            <span className="font-mono text-[10px] tracking-[0.14em] text-faint">
              AUTHORIZED BY
            </span>
            <input
              value={authorizer}
              onChange={(e) => setAuthorizer(e.target.value)}
              disabled={submitting}
              autoFocus
              placeholder="Authorizing officer name"
              className="mt-1.5 w-full rounded-lg border border-border bg-cardhi px-3 py-2 text-[13.5px] text-txt outline-none transition-colors placeholder:text-faint focus:border-blue disabled:opacity-60"
            />
          </label>

          {error && (
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-danger/40 px-3 py-2 text-[12px] text-danger">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              {error}
            </div>
          )}
        </div>

        {/* actions */}
        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3.5">
          <button
            onClick={onClose}
            disabled={submitting}
            className="rounded-lg border border-border px-3.5 py-2 text-[13px] text-muted transition-colors hover:bg-soft hover:text-txt disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            onClick={onReject}
            disabled={submitting || !authorizer.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-danger/40 px-3.5 py-2 text-[13px] font-medium text-danger transition-colors hover:bg-danger/10 disabled:opacity-50"
          >
            <XCircle className="h-4 w-4" />
            Reject
          </button>
          <button
            onClick={onApprove}
            disabled={submitting || !authorizer.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-50"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            {submitting ? 'Submitting…' : 'Authorize'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex gap-2">
      <dt className="shrink-0 font-mono text-faint">{k}:</dt>
      <dd className={`text-muted ${mono ? 'font-mono' : ''}`} dir={dir(v)}>
        {v}
      </dd>
    </div>
  )
}

/* --------------------------------------------------------------- utilities */

function fmtTime(ts: string | null | undefined): string {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return String(ts)
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
