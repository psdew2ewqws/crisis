// SolutionsPage — AEGIS Crisis Console (T3: valid-solution engine).
//
// Renders a "valid solution" card per top voc360 root-cause cluster:
//   actions · owning agency · expected impact · feasibility · confidence
// Each card carries an "Authorize" button that creates a Decision.
//
// IMPORT-SAFE BY DESIGN. This file ships ahead of the T3 backend wiring, so it
// degrades gracefully at every boundary:
//   • Solutions come from `getSolutions()` if the API client exposes it; if that
//     export does not exist yet (or the call fails) we DERIVE grounded solutions
//     from `getRootCause()` — which is already part of lib/voc — using only real
//     voc360 columns (cluster_id, label_ar, label_en, members, severity_avg).
//   • "Authorize" calls `createDecision()` if present; otherwise it records the
//     decision in local state so the flow still works end-to-end in the UI.
// No top-level import can throw on a missing export: we read optional client
// functions off a namespace import at runtime.

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  FlaskConical,
  ShieldCheck,
  Building2,
  TrendingDown,
  Gauge,
  CheckCircle2,
  Loader2,
  AlertTriangle,
  Sparkles,
} from 'lucide-react'
import * as voc from '../lib/voc'
import type { RootCause, Decision, NewDecision, CreateDecisionResponse } from '../lib/voc'

/* ------------------------------------------------------------------ types -- */

type Feasibility = 'high' | 'medium' | 'low'

export interface ValidSolution {
  cluster_id: string
  rank: number
  /** real voc360 canonical labels */
  label_ar: string
  label_en: string | null
  members: number
  severity_avg: number
  /** countermeasure title (English, grounded) */
  title: string
  /** concrete action steps */
  actions: string[]
  /** owning agency / service team */
  agency: string
  /** expected impact — short narrative */
  expected_impact: string
  /** projected reduction in complaint volume for this cluster, 0..1 */
  impact_reduction: number
  feasibility: Feasibility
  /** 0..1 model/heuristic confidence */
  confidence: number
}

/* --------------------------------------------------- optional client probe -- */
// Read optional functions off the namespace import so a not-yet-added export
// never breaks the build or the module load.

type SolutionsFn = (limit?: number) => Promise<{ solutions: ValidSolution[] }>
// voc2.createDecision takes a NewDecision (action required; agency is NOT a
// server field) and resolves to {ok, decision?, error?}. A live HTTP-200 POST
// returns the BARE decision row with an `id` and no `ok` field, so authorize()
// tolerates both shapes.
type CreateDecisionFn = (d: NewDecision) => Promise<CreateDecisionResponse>

const api = voc as unknown as Record<string, unknown>
const getSolutions =
  typeof api.getSolutions === 'function' ? (api.getSolutions as SolutionsFn) : null
const createDecision =
  typeof api.createDecision === 'function' ? (api.createDecision as CreateDecisionFn) : null
const getDecisions =
  typeof api.getDecisions === 'function'
    ? (api.getDecisions as () => Promise<{ decisions: Decision[]; source?: string }>)
    : null
const getRootCause =
  typeof api.getRootCause === 'function'
    ? (api.getRootCause as () => Promise<{ root_causes: RootCause[]; recommendation: string }>)
    : null

/* --------------------------------------------- grounded fallback engine ---- */
// Maps real voc360 cluster signals → a deterministic countermeasure. No LLM, no
// invented columns: everything keys off label_ar/label_en + members + severity.

interface Rule {
  match: RegExp
  title: string
  agency: string
  actions: string[]
}

// Keyed on the Arabic canonical labels actually present in ril_problem_clusters
// (National-Aid-Fund delays, BRT bus, urgent-service fees, Takaful platform, …)
// plus English/keyword fallbacks. Order matters: first match wins.
const RULES: Rule[] = [
  {
    match: /معونة|صندوق المعونة|national.?aid|aid fund/i,
    title: 'Clear the National Aid Fund disbursement backlog',
    agency: 'National Aid Fund',
    actions: [
      'Stand up a surge processing cell to clear the aged disbursement queue',
      'Publish a per-applicant status tracker to cut repeat enquiries',
      'Reconcile pending case files against eligibility records weekly',
    ],
  },
  {
    match: /تكافل|takaful/i,
    title: 'Stabilise the Takaful platform',
    agency: 'Ministry of Social Development',
    actions: [
      'Add capacity / retries on the Takaful submission endpoint',
      'Surface clear error messaging for failed applications',
      'Add an offline fallback channel during outages',
    ],
  },
  {
    match: /باص السريع|brt|الباص السريع|amman bus|نقل عام|transit/i,
    title: 'Restore BRT / public-transit reliability',
    agency: 'Greater Amman Municipality — Transport',
    actions: [
      'Re-time the BRT schedule against observed peak demand',
      'Deploy reserve buses on the most-complained corridors',
      'Publish live arrival data to reduce wait-time complaints',
    ],
  },
  {
    match: /رسوم|urgent.?service|expedited|fee/i,
    title: 'Review urgent-service fee policy',
    agency: 'Service Delivery Authority',
    actions: [
      'Audit expedited-service fees against published tariffs',
      'Disclose fee breakdown at point of payment',
      'Open a fast refund path for over-charges',
    ],
  },
  {
    match: /جوازات|passport/i,
    title: 'Reduce passport-service wait times',
    agency: 'Passports & Civil Status Dept.',
    actions: [
      'Open additional appointment slots at the busiest centres',
      'Shift routine renewals to the e-channel',
      'Add SMS status updates to cut counter follow-ups',
    ],
  },
  {
    match: /رد|عدم الرد|no.?response|response/i,
    title: 'Close the citizen-response gap',
    agency: 'Owning service contact centre',
    actions: [
      'Set and publish a first-response SLA for inbound complaints',
      'Auto-acknowledge every submission with a ticket reference',
      'Escalate any case unanswered past the SLA window',
    ],
  },
  {
    match: /فساد|corruption|إداري/i,
    title: 'Investigate administrative-conduct reports',
    agency: 'Integrity & Anti-Corruption Commission',
    actions: [
      'Triage flagged conduct reports for severity and recurrence',
      'Refer substantiated cases to the relevant oversight body',
      'Publish anonymised outcome statistics to restore trust',
    ],
  },
  {
    match: /طرق|بنية|road|infrastructure/i,
    title: 'Prioritise roads & infrastructure fixes',
    agency: 'Ministry of Public Works',
    actions: [
      'Rank reported defects by complaint density and severity',
      'Dispatch maintenance crews to top-ranked locations first',
      'Confirm closure with citizens who reported each defect',
    ],
  },
]

const GENERIC: Rule = {
  match: /.*/,
  title: 'Targeted intervention for the dominant complaint cluster',
  agency: 'Owning service agency',
  actions: [
    'Route this cluster to the owning agency with an assigned owner',
    'Brief the service team on the recurring problem pattern',
    'Track whether complaint volume on this cluster falls after action',
  ],
}

function ruleFor(label: string): Rule {
  return RULES.find((r) => r.match.test(label)) ?? GENERIC
}

// Feasibility & confidence are derived deterministically from the real cluster
// signals so the same data always yields the same recommendation.
function feasibilityFor(members: number, severity: number): Feasibility {
  // Big, sharply-negative clusters are higher effort → lower feasibility.
  if (members >= 120 || severity >= 0.6) return 'low'
  if (members >= 30 || severity >= 0.35) return 'medium'
  return 'high'
}

function confidenceFor(members: number, severity: number): number {
  // More evidence + clearer severity signal → higher confidence. Bounded 0.5..0.95.
  const evidence = Math.min(1, members / 200)
  const c = 0.5 + 0.3 * evidence + 0.15 * Math.min(1, severity * 1.4)
  return Math.round(Math.min(0.95, c) * 100) / 100
}

function impactFor(members: number, severity: number): number {
  // Expected complaint-volume reduction for this cluster. Bounded 0.2..0.7.
  const base = 0.4 + 0.2 * Math.min(1, severity * 1.5) - 0.05 * Math.min(1, members / 300)
  return Math.round(Math.max(0.2, Math.min(0.7, base)) * 100) / 100
}

function deriveSolutions(causes: RootCause[]): ValidSolution[] {
  return causes.map((c) => {
    const label = `${c.label_ar ?? ''} ${c.label_en ?? ''}`.trim()
    const rule = ruleFor(label)
    const severity = c.severity_avg ?? 0
    const members = c.members ?? 0
    const impact = impactFor(members, severity)
    return {
      cluster_id: c.cluster_id,
      rank: c.rank,
      label_ar: c.label_ar,
      label_en: c.label_en,
      members,
      severity_avg: severity,
      title: rule.title,
      actions:
        rule.actions && rule.actions.length
          ? rule.actions
          : ['Route this root cause to the owning agency, brief the service team, and track whether complaints on this cluster fall after action.'],
      agency: rule.agency,
      impact_reduction: impact,
      expected_impact: `~${Math.round(impact * 100)}% projected drop in complaints for this cluster (${members} reports today).`,
      feasibility: feasibilityFor(members, severity),
      confidence: confidenceFor(members, severity),
    }
  })
}

/* ------------------------------------------------------------ presentation -- */

const FEAS_TONE: Record<Feasibility, string> = {
  high: 'text-good border-good/30 bg-good/10',
  medium: 'text-warn border-warn/30 bg-warn/10',
  low: 'text-danger border-danger/30 bg-danger/10',
}

const isAr = (s: string) => /[؀-ۿ]/.test(s)

function Meter({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-soft">
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%`, background: color }}
      />
    </div>
  )
}

function severityColor(sev: number): string {
  return sev >= 0.5 ? '#F04359' : sev >= 0.3 ? '#FBBF24' : '#34D399'
}

function SolutionCard({
  sol,
  authorized,
  pending,
  onAuthorize,
}: {
  sol: ValidSolution
  authorized: boolean
  pending: boolean
  onAuthorize: () => void
}) {
  const sevCol = severityColor(sol.severity_avg)
  return (
    <div className="flex flex-col rounded-xl border border-border bg-card p-5 transition-colors hover:border-border/80 hover:bg-cardhi">
      {/* header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-faint">#{sol.rank}</span>
            <span className="font-mono text-[11px] text-muted">{sol.cluster_id.slice(0, 8)}</span>
          </div>
          <h3
            dir={isAr(sol.title) ? 'rtl' : 'ltr'}
            className="mt-1 text-[16px] font-semibold leading-tight tracking-tight text-txt"
          >
            {sol.title}
          </h3>
          <p
            className="mt-1 text-[12.5px] leading-snug text-muted"
            dir={isAr(sol.label_ar) ? 'rtl' : 'ltr'}
          >
            {sol.label_ar}
            {sol.label_en && !isAr(sol.label_en) && sol.label_en !== sol.label_ar && (
              <span className="text-faint"> · {sol.label_en}</span>
            )}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-md border px-2 py-0.5 font-mono text-[11px] font-medium ${FEAS_TONE[sol.feasibility]}`}
        >
          {sol.feasibility} feasibility
        </span>
      </div>

      {/* agency + evidence row */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12.5px] text-muted">
        <span className="inline-flex items-center gap-1.5">
          <Building2 className="h-3.5 w-3.5 text-faint" />
          {sol.agency}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: sevCol }} />
          <span className="font-mono tnum">{sol.members}</span> reports · sev{' '}
          <span className="font-mono tnum">{sol.severity_avg.toFixed(2)}</span>
        </span>
      </div>

      {/* actions */}
      <div className="mt-4">
        <div className="mb-2 font-mono text-[10px] tracking-[0.14em] text-faint">COUNTERMEASURE</div>
        <ul className="space-y-1.5">
          {sol.actions.map((a, i) => (
            <li key={i} className="flex items-start gap-2 text-[13px] leading-snug text-txt">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-blue" />
              <span>{a}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* impact + confidence meters */}
      <div className="mt-4 grid grid-cols-2 gap-4">
        <div>
          <div className="mb-1.5 flex items-center justify-between text-[11px]">
            <span className="inline-flex items-center gap-1 text-muted">
              <TrendingDown className="h-3.5 w-3.5 text-good" />
              Expected impact
            </span>
            <span className="font-mono tnum text-good">−{Math.round(sol.impact_reduction * 100)}%</span>
          </div>
          <Meter value={sol.impact_reduction} color="#34D399" />
        </div>
        <div>
          <div className="mb-1.5 flex items-center justify-between text-[11px]">
            <span className="inline-flex items-center gap-1 text-muted">
              <Gauge className="h-3.5 w-3.5 text-blue" />
              Confidence
            </span>
            <span className="font-mono tnum text-txt">{sol.confidence.toFixed(2)}</span>
          </div>
          <Meter value={sol.confidence} color="#3B82F6" />
        </div>
      </div>

      <p className="mt-3 text-[12px] leading-snug text-faint">{sol.expected_impact}</p>

      {/* authorize */}
      <div className="mt-4 flex items-center justify-end border-t border-border/70 pt-4">
        {authorized ? (
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-good/30 bg-good/10 px-3 py-2 text-[13px] font-semibold text-good">
            <ShieldCheck className="h-4 w-4" />
            Decision authorized
          </span>
        ) : (
          <button
            onClick={onAuthorize}
            disabled={pending}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-60"
          >
            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            {pending ? 'Authorizing…' : 'Authorize'}
          </button>
        )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------- page -- */

export default function SolutionsPage() {
  const { t } = useTranslation()
  const [sols, setSols] = useState<ValidSolution[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [derived, setDerived] = useState(false)
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [pending, setPending] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    async function load() {
      // 0) hydrate already-authorized decisions from the backend store so
      // authorizedIds (which keys on cluster_id) reflects prior sessions.
      if (getDecisions) {
        try {
          const dec = await getDecisions()
          if (alive) setDecisions(dec.decisions ?? [])
        } catch {
          /* leave decisions empty */
        }
      }
      // 1) preferred: real solutions endpoint.
      if (getSolutions) {
        try {
          const r = await getSolutions(8)
          if (alive && Array.isArray(r?.solutions) && r.solutions.length) {
            // normalize the backend Solution (cause/countermeasure) → the card's ValidSolution
            setSols(
              (r.solutions as any[]).map((s, i): ValidSolution => ({
                cluster_id: s.cluster_id,
                rank: s.rank ?? i + 1,
                label_ar: s.label_ar,
                label_en: s.label_en ?? null,
                members: s.affected_signals ?? s.members ?? 0,
                severity_avg: s.severity_avg ?? 0,
                title: (s.label_en && !isAr(s.label_en) ? s.label_en : null) || s.label_ar || 'Root cause',
                actions: s.countermeasure ? [s.countermeasure] : (s.actions ?? []),
                agency: s.owning_service || s.agency || '—',
                impact_reduction:
                  typeof s.expected_impact === 'number' ? s.expected_impact : (s.impact_reduction ?? 0.4),
                expected_impact:
                  typeof s.expected_impact === 'number'
                    ? `~${Math.round(s.expected_impact * 100)}% projected drop (${s.affected_signals ?? s.members ?? 0} reports).`
                    : (s.expected_impact ?? ''),
                feasibility:
                  (s.feasibility_label as Feasibility) ||
                  (typeof s.feasibility === 'number'
                    ? s.feasibility >= 0.66 ? 'high' : s.feasibility >= 0.4 ? 'medium' : 'low'
                    : 'medium'),
                confidence: typeof s.confidence === 'number' ? s.confidence : 0.7,
              })),
            )
            setDerived(false)
            return
          }
        } catch {
          /* fall through to grounded derivation */
        }
      }
      // 2) grounded fallback: derive from real voc360 root causes.
      if (getRootCause) {
        try {
          const rc = await getRootCause()
          if (alive) {
            setSols(deriveSolutions(rc.root_causes ?? []))
            setDerived(true)
          }
          return
        } catch (e) {
          if (alive) setErr(String(e))
          return
        }
      }
      if (alive) setErr('No solutions source available.')
    }
    load()
    return () => {
      alive = false
    }
  }, [])

  const authorizedIds = useMemo(
    () => new Set(decisions.map((d) => d.cluster_id)),
    [decisions],
  )

  async function authorize(sol: ValidSolution) {
    if (pending || authorizedIds.has(sol.cluster_id)) return
    setPending(sol.cluster_id)
    try {
      if (createDecision) {
        // Send the server-required fields: `action` is required (422 without it);
        // `agency` is NOT a server field, so carry it via owner/rationale.
        const res = await createDecision({
          cluster_id: sol.cluster_id,
          title: sol.title,
          action: sol.actions[0] ?? sol.title,
          owner: sol.agency,
          rationale: `Authorized — ${sol.agency}`,
        })
        // A live HTTP-200 POST returns the BARE decision row (has `id`, no `ok`);
        // voc2's type says {ok, decision}. Tolerate both, and only treat it as
        // authorized when the backend actually accepted it.
        const raw = res as CreateDecisionResponse & Partial<Decision>
        const decision: Decision | undefined =
          raw.decision ?? (typeof raw.id === 'string' ? (raw as unknown as Decision) : undefined)
        // Success = a returned decision (bare row or wrapped) or an explicit ok:true.
        // jf's unreachable fallback is {ok:false,error} with no decision → fail.
        if (!decision && raw.ok !== true) {
          setErr(raw.error ?? 'Decision was not saved.')
          return
        }
        // Push the UNWRAPPED decision; ensure it carries cluster_id so
        // authorizedIds.has(sol.cluster_id) flips the card and the gate.
        setDecisions((xs) => [
          ...xs,
          {
            id: decision?.id ?? `dec-${sol.cluster_id}`,
            cluster_id: decision?.cluster_id ?? sol.cluster_id,
            title: decision?.title ?? sol.title,
            action: decision?.action ?? (sol.actions[0] ?? sol.title),
            status: decision?.status ?? 'proposed',
            owner: decision?.owner ?? sol.agency,
            rationale: decision?.rationale ?? null,
            created_at: decision?.created_at ?? new Date().toISOString(),
          },
        ])
      } else {
        // local-only decision so the flow completes without the backend.
        setDecisions((xs) => [
          ...xs,
          {
            id: `local-${sol.cluster_id}`,
            cluster_id: sol.cluster_id,
            title: sol.title,
            action: sol.actions[0] ?? sol.title,
            status: 'proposed',
            owner: sol.agency,
            rationale: null,
            created_at: new Date().toISOString(),
          },
        ])
      }
    } catch (e) {
      setErr(String(e))
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[1340px] px-8 py-7">
        {/* header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="flex items-center gap-2.5 text-[28px] font-semibold tracking-tight text-txt">
              <FlaskConical className="h-6 w-6 text-blue" />
              {t('solutions.title')}
            </h1>
            <p className="mt-1.5 flex items-center gap-2 text-[14px] text-muted">
              Valid-solution engine · cause → countermeasure → expected impact
              {derived && (
                <span className="inline-flex items-center gap-1 rounded-md border border-border bg-soft px-2 py-0.5 font-mono text-[11px] text-faint">
                  <Sparkles className="h-3 w-3" />
                  grounded
                </span>
              )}
            </p>
          </div>
          {decisions.length > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-good/30 bg-good/10 px-3 py-2 text-[13px] font-medium text-good">
              <ShieldCheck className="h-4 w-4" />
              {decisions.length} decision{decisions.length > 1 ? 's' : ''} authorized
            </span>
          )}
        </div>

        {/* error */}
        {err && (
          <div className="mt-6 flex items-center gap-2 rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-[13px] text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {err}
          </div>
        )}

        {/* loading */}
        {!sols && !err && (
          <div className="mt-16 flex flex-col items-center justify-center gap-3 text-muted">
            <Loader2 className="h-6 w-6 animate-spin text-blue" />
            <span className="text-[13px]">Computing valid solutions from voc360 root causes…</span>
          </div>
        )}

        {/* empty */}
        {sols && sols.length === 0 && !err && (
          <div className="mt-16 text-center text-[13px] text-muted">
            No active root-cause clusters to resolve.
          </div>
        )}

        {/* grid */}
        {sols && sols.length > 0 && (
          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            {sols.map((s) => (
              <SolutionCard
                key={s.cluster_id}
                sol={s}
                authorized={authorizedIds.has(s.cluster_id)}
                pending={pending === s.cluster_id}
                onAuthorize={() => authorize(s)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
