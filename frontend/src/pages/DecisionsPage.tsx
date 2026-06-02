// DecisionsPage — T2 console page (decision log + human-authorization gate).
//
// Renders the operator decision log returned by GET /api/decisions (getDecisions)
// — what was chosen about a root cause / solution — as a clean table with status
// chips, owner, linked RIL cluster and rationale. The page also surfaces the
// human-in-the-loop AUTHORIZATION GATE: a decision that is still `proposed`
// cannot take effect until a named person authorizes it. Authorizing posts back
// through createDecision (the existing module signature) with status `approved`
// and the authorizer.
//
// NOTE: the current POST /api/decisions store APPENDS a new row and does not
// honor a status/owner transition on an existing decision (it persists
// status:"proposed", authorized_by:"operator"). Until the backend adds an
// authorize/PATCH endpoint, the gate cannot transition the original row — this
// page only logs the authorization attempt; it is NOT yet grounded in a real
// backend status change.
//
// Real voc360 columns only: decisions reference ril_problem_clusters.cluster_id
// (the root-cause layer); no Zarqa demo fixtures are used. Import-safe: every
// network call goes through getDecisions / createDecision which themselves return
// graceful fallbacks (lib/voc2.ts `jf`), so the page stays mounted and degrades
// cleanly when the backend (or the not-yet-built POST handler) is unreachable.

import { useEffect, useMemo, useState } from 'react'
import { useT } from '../lib/i18n'
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
  updateDecision,
  AEGIS,
  toneColor,
  type Tone,
  type Decision,
  type CreateDecisionResponse,
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

// The live GET /api/decisions store row uses `ts`/`label`/`authorized_by`, not
// the voc2 Decision `created_at`/`title`/`owner`. Normalize on read so rows
// render and StatusIcon/needsAuthorization see real values. The store status
// enum uses `authorized` where voc2 uses `approved`; map it so the tone/label
// maps resolve and the row reads as cleared.
type RawDecision = Decision & {
  ts?: string | null
  label?: string | null
  authorized_by?: string | null
}

function normalizeRow(raw: Decision): Decision {
  const r = raw as RawDecision
  const status = ((r.status as string) === 'authorized' ? 'approved' : r.status) as Decision['status']
  return {
    ...raw,
    status,
    title: raw.title || r.label || '',
    created_at: raw.created_at ?? r.ts ?? '',
    owner: raw.owner ?? r.authorized_by ?? null,
  }
}

// The DECISION column must never be blank: the live store persists `label:""` on
// every row, so fall back through title → action → short cluster id.
function titleOf(d: Decision): string {
  const r = d as RawDecision
  return (r.label || d.title || d.action || (d.cluster_id ? String(d.cluster_id).slice(0, 8) : '') || '—')
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
  const { t } = useT()
  const [gateFor, setGateFor] = useState<Decision | null>(null) // open modal target
  const [authorizer, setAuthorizer] = useState('') // authorized_by input
  const [submitting, setSubmitting] = useState(false)
  const [gateErr, setGateErr] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setErr(null)
    try {
      const res = await getDecisions()
      const rows = Array.isArray(res?.decisions) ? res.decisions.map(normalizeRow) : []
      setDecisions(rows)
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
      setGateErr(t('An authorizing officer name is required to clear the gate.'))
      return
    }
    setSubmitting(true)
    setGateErr(null)
    try {
      // Transition the EXISTING proposed decision in place (PATCH) so the row's
      // status + authorized_by are ratified — no duplicate decision is appended.
      const res = await updateDecision(d.id, { status, authorized_by: who })
      // A successful PATCH returns the BARE updated row ({id,...}) with no `ok`
      // field; the unreachable fallback returns {ok:false}. Accept either a real
      // row (has id) or an {ok:true,decision} wrapper.
      const raw = res as CreateDecisionResponse & Partial<Decision>
      const accepted = raw.ok === true || !!raw.decision || typeof raw.id === 'string'
      if (!accepted) {
        setGateErr(raw.error || t('Backend rejected the authorization — is the decisions store writable?'))
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
              {t('Decisions')}
            </h1>
            <p className="mt-1.5 flex items-center gap-2 text-[14px] text-muted">
              <Database className="h-3.5 w-3.5" />
              {t('Operator decision log over voc360 root causes')}
              {decisions.length > 0 && (
                <span className="text-faint">
                  · {t('{logged} logged · {authorized} authorized · {pending} awaiting gate', {
                    logged: decisions.length,
                    authorized: authorizedCount,
                    pending: pending.length,
                  })}
                </span>
              )}
              {source === 'fallback' && decisions.length === 0 && (
                <span className="text-faint">· {t('offline')}</span>
              )}
            </p>
          </div>
          <button
            onClick={() => void load()}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-60"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {loading ? t('Loading…') : t('Refresh')}
          </button>
        </div>

        {/* authorization-gate banner */}
        {pending.length > 0 && (
          <div className="mt-6 flex items-start gap-3 rounded-xl border border-warn/30 bg-warn/10 p-4 text-[13.5px] leading-snug text-txt">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
            <div>
              <div className="mb-0.5 font-mono text-[10px] tracking-[0.14em] text-warn">
                {t('HUMAN AUTHORIZATION REQUIRED')}
              </div>
              {pending.length === 1
                ? t('{n} proposed decision cannot take effect until a named officer authorizes it.', { n: pending.length })
                : t('{n} proposed decisions cannot take effect until a named officer authorizes them.', { n: pending.length })}
              {' '}{t('Review the rationale, then clear the gate below.')}
            </div>
          </div>
        )}

        {/* error */}
        {err && (
          <div className="mt-6 flex items-center gap-2 rounded-lg border border-danger/40 bg-card px-4 py-3 text-[13px] text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {t('Could not load decisions — {err}', { err })}
          </div>
        )}

        {/* loading / empty */}
        {!err && loading && decisions.length === 0 && (
          <div className="mt-10 flex items-center justify-center gap-2 text-[13px] text-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t('Loading decision log…')}
          </div>
        )}
        {!err && !loading && decisions.length === 0 && (
          <div className="mt-10 rounded-xl border border-border bg-card px-5 py-10 text-center text-[13px] text-muted">
            {t('No decisions have been logged yet. Decisions are created from the Root Cause and Solutions views, then cleared through the authorization gate here.')}
          </div>
        )}

        {/* decision log table */}
        {decisions.length > 0 && (
          <div className="mt-6 overflow-hidden rounded-xl border border-border bg-card">
            <div className="border-b border-border px-5 py-3 font-mono text-[10px] tracking-[0.14em] text-faint">
              {t('DECISION LOG · {n}', { n: decisions.length })}
            </div>
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border text-[11px] font-medium tracking-[0.08em] text-faint">
                  <th className="px-5 py-3 font-medium">{t('DECISION')}</th>
                  <th className="py-3 font-medium">{t('ROOT CAUSE')}</th>
                  <th className="py-3 font-medium">{t('STATUS')}</th>
                  <th className="py-3 font-medium">{t('AUTHORIZED BY')}</th>
                  <th className="py-3 font-medium">{t('LOGGED')}</th>
                  <th className="px-5 py-3 text-right font-medium">{t('GATE')}</th>
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
  const { t } = useT()
  const tone = STATUS_TONE[d.status] ?? 'neutral'
  const col = toneColor(tone)
  const who = authorizedBy(d) ?? d.owner ?? null
  const gated = needsAuthorization(d)

  return (
    <tr className="border-t border-border/70 align-top transition-colors hover:bg-soft/50">
      {/* decision title + action */}
      <td className="px-5 py-3.5">
        <div className="text-[13.5px] font-medium text-txt" dir={dir(titleOf(d))}>
          {titleOf(d)}
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
            title={t('Open this cluster in the graph')}
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
          {t(STATUS_LABEL[d.status] ?? d.status)}
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
          <span className="text-[12px] text-faint">{gated ? t('unauthorized') : '—'}</span>
        )}
      </td>

      {/* logged at */}
      <td className="py-3.5 font-mono text-[11.5px] text-muted">
        {fmtTime((d as Decision & { ts?: string | null }).ts ?? d.created_at)}
      </td>

      {/* gate action */}
      <td className="px-5 py-3.5 text-right">
        {gated ? (
          <button
            onClick={onAuthorize}
            className="inline-flex items-center gap-1.5 rounded-lg border border-warn/40 px-3 py-1.5 text-[12.5px] font-medium text-warn transition-colors hover:bg-warn/10"
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            {t('Authorize')}
          </button>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-[12px] text-faint">
            <ShieldCheck className="h-3.5 w-3.5" style={{ color: AEGIS.good }} />
            {t('cleared')}
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
  const { t } = useT()
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
            {t('AUTHORIZATION GATE')}
          </span>
        </div>

        {/* body */}
        <div className="px-5 py-4">
          <h3 className="text-[15.5px] font-semibold leading-snug text-txt" dir={dir(titleOf(decision))}>
            {titleOf(decision)}
          </h3>
          {decision.action && (
            <p className="mt-1 text-[13px] leading-snug text-muted" dir={dir(decision.action)}>
              {decision.action}
            </p>
          )}

          <dl className="mt-3 space-y-1.5 text-[12px]">
            {decision.cluster_id && (
              <Row k={t('Root cause')} v={String(decision.cluster_id).slice(0, 8)} mono />
            )}
            {decision.rationale && <Row k={t('Rationale')} v={decision.rationale} />}
          </dl>

          {/* authorizer input — the human-in-the-loop field */}
          <label className="mt-4 block">
            <span className="font-mono text-[10px] tracking-[0.14em] text-faint">
              {t('AUTHORIZED BY')}
            </span>
            <input
              value={authorizer}
              onChange={(e) => setAuthorizer(e.target.value)}
              disabled={submitting}
              autoFocus
              placeholder={t('Authorizing officer name')}
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
            {t('Cancel')}
          </button>
          <button
            onClick={onReject}
            disabled={submitting || !authorizer.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-danger/40 px-3.5 py-2 text-[13px] font-medium text-danger transition-colors hover:bg-danger/10 disabled:opacity-50"
          >
            <XCircle className="h-4 w-4" />
            {t('Reject')}
          </button>
          <button
            onClick={onApprove}
            disabled={submitting || !authorizer.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-50"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            {submitting ? t('Submitting…') : t('Authorize')}
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
