import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, ResponsiveContainer } from 'recharts'
import {
  Loader2, ArrowLeft, X, FileSpreadsheet, ShieldCheck, ShieldAlert,
  CornerDownRight, Quote, TrendingUp, CheckCircle2, XCircle,
} from 'lucide-react'
import { getProof, reportUrl, type ProofBundle } from '../lib/voc'

const SEV: Record<string, string> = { alert: '#F04359', warn: '#FBBF24', calm: '#34D399' }
const isAr = (s: string | null | undefined) => !!s && /[؀-ۿ]/.test(s)
const sevColor = (v: number) => (v >= 0.5 ? SEV.alert : v >= 0.3 ? SEV.warn : SEV.calm)

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-border p-4">
      <div className="mb-3 font-mono text-[10px] tracking-[0.14em] text-faint">{label}</div>
      {children}
    </div>
  )
}

export default function ProofPanel({
  query,
  onBack,
}: {
  query: { type: 'cluster' | 'service' | 'all'; key: string }
  onBack: () => void
}) {
  const [proof, setProof] = useState<ProofBundle | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(true)

  useEffect(() => {
    let alive = true
    setBusy(true)
    setErr(null)
    setProof(null)
    getProof({ type: query.type, key: query.key, depth: 5 })
      .then((p) => alive && setProof(p))
      .catch((e) => alive && setErr(String(e)))
      .finally(() => alive && setBusy(false))
    return () => {
      alive = false
    }
  }, [query.type, query.key])

  const fc = proof?.forecast
  const spark =
    fc &&
    [
      ...fc.history.map((h) => ({ t: h.t, v: +(h.v ?? 0).toFixed(3) })),
      ...fc.forecast.map((f) => ({ t: f.t, v: +(f.mean ?? 0).toFixed(3) })),
    ]

  return (
    <aside className="flex w-[360px] shrink-0 flex-col overflow-y-auto border-l border-border bg-sidebar">
      {/* header / back */}
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-border bg-sidebar px-4 py-3">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-[11px] text-muted transition-colors hover:bg-soft hover:text-txt"
        >
          <ArrowLeft className="h-3 w-3" />
          back
        </button>
        <span className="font-mono text-[10px] tracking-[0.14em] text-faint">PROOF</span>
        <button
          onClick={onBack}
          aria-label="close"
          className="ml-auto rounded-md p-1 text-muted transition-colors hover:bg-soft hover:text-txt"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {busy && (
        <div className="flex items-center gap-2 p-6 text-[13px] text-muted">
          <Loader2 className="h-4 w-4 animate-spin" />
          building proof…
        </div>
      )}
      {err && !busy && (
        <div className="m-4 rounded-lg border border-danger/40 bg-card p-3 text-[12.5px] leading-snug text-danger">
          {err}
        </div>
      )}

      {proof && !busy && (
        <>
          {/* subject header */}
          <div className="border-b border-border p-4">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] tracking-[0.14em] text-faint">
                {proof.subject.type.toUpperCase()}
              </span>
              <span
                className="font-mono text-[11px]"
                style={{ color: sevColor(proof.subject.severity_avg) }}
              >
                {proof.subject.members} reports · sev {proof.subject.severity_avg}
              </span>
            </div>
            {proof.subject.label_ar && (
              <div className="mt-1.5 text-[14px] font-semibold leading-snug text-txt" dir="rtl">
                {proof.subject.label_ar}
              </div>
            )}
            {proof.subject.label_en && (
              <div className="mt-1 text-[12px] leading-snug text-muted" dir="ltr">
                {proof.subject.label_en}
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[10px] text-faint">
              <span>{proof.subject.signals} signals</span>
              {proof.subject.first_seen && <span>since {proof.subject.first_seen.slice(0, 10)}</span>}
              {proof.subject.last_seen && <span>→ {proof.subject.last_seen.slice(0, 10)}</span>}
            </div>
            {proof.subject.services.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {proof.subject.services.slice(0, 6).map(([svc, w]) => (
                  <span
                    key={svc}
                    className="rounded-md border border-border bg-card px-1.5 py-0.5 text-[10px] text-muted"
                    dir={isAr(svc) ? 'rtl' : 'ltr'}
                  >
                    {svc} <span className="text-faint">·{w}</span>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* download report */}
          <div className="border-b border-border p-4">
            <a
              href={reportUrl(proof.subject.cluster_id)}
              download
              className="flex items-center justify-center gap-2 rounded-lg bg-good px-4 py-2.5 text-[13.5px] font-semibold text-[#04130C] transition-opacity hover:opacity-90"
            >
              <FileSpreadsheet className="h-4 w-4" />
              Download Excel report
            </a>
            <p className="mt-2 text-[11px] leading-snug text-muted">
              Full evidence workbook — why-chain, validation checks, and every source record behind this finding.
            </p>
          </div>

          {/* why-chain causal trace */}
          <Section label="WHY THIS HAPPENS · 5-WHYS TRACE">
            <ol className="space-y-0">
              {proof.why_chain.map((w, i) => {
                const last = i === proof.why_chain.length - 1
                const txt = isAr(w.because) ? w.because : w.because_en || w.because
                return (
                  <li key={w.depth} className="relative pb-3 pl-6">
                    {!last && <span className="absolute left-[7px] top-5 h-full w-px bg-border" />}
                    <CornerDownRight
                      className="absolute left-0 top-0.5 h-4 w-4"
                      style={{ color: last ? SEV.alert : '#62646D' }}
                    />
                    <div className="text-[10px] font-mono uppercase tracking-wider text-faint">
                      {last ? 'root cause' : w.question || `because #${w.depth}`}
                    </div>
                    <div
                      className="mt-0.5 text-[12.5px] leading-snug text-txt"
                      dir={isAr(txt) ? 'rtl' : 'ltr'}
                    >
                      {txt}
                    </div>
                    {w.evidence?.[0] && (
                      <div
                        className="mt-1 border-l-2 border-border pl-2 text-[11px] leading-snug text-muted"
                        dir={isAr(w.evidence[0]) ? 'rtl' : 'ltr'}
                      >
                        “{w.evidence[0]}”
                      </div>
                    )}
                  </li>
                )
              })}
            </ol>
            {proof.narration && (
              <div
                className="mt-2 rounded-lg border border-blue/30 bg-blue/10 p-2.5 text-[12px] leading-snug text-txt"
                dir={isAr(proof.narration) ? 'rtl' : 'ltr'}
              >
                {proof.narration}
              </div>
            )}
          </Section>

          {/* validation verdict + checks */}
          {proof.validation && (
            <Section label="PROOF STRENGTH · VALIDATION">
              {(() => {
                const v = proof.validation
                const ok = v.verdict?.toLowerCase().includes('valid') || v.score >= 0.5
                const VIcon = ok ? ShieldCheck : ShieldAlert
                const col = ok ? SEV.calm : SEV.alert
                return (
                  <>
                    <div className="flex items-center gap-2">
                      <VIcon className="h-4 w-4 shrink-0" style={{ color: col }} />
                      <span className="text-[13px] font-semibold capitalize text-txt">{v.verdict}</span>
                      <span className="ml-auto font-mono text-[11px]" style={{ color: col }}>
                        {(v.confidence * 100).toFixed(0)}% conf · {v.score.toFixed(2)}
                      </span>
                    </div>
                    {v.summary && (
                      <div
                        className="mt-1.5 text-[12px] leading-snug text-muted"
                        dir={isAr(v.summary) ? 'rtl' : 'ltr'}
                      >
                        {v.summary}
                      </div>
                    )}
                    <div className="mt-2.5 space-y-1.5">
                      {v.checks.map((c) => (
                        <div key={c.name} className="rounded-lg border border-border bg-card p-2">
                          <div className="flex items-center gap-1.5">
                            {c.pass ? (
                              <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-good" />
                            ) : (
                              <XCircle className="h-3.5 w-3.5 shrink-0 text-danger" />
                            )}
                            <span className="text-[12px] capitalize text-txt">{c.name}</span>
                            <span className="ml-auto font-mono text-[10px] text-faint">{c.score.toFixed(2)}</span>
                          </div>
                          {c.detail && (
                            <div
                              className="mt-0.5 pl-5 text-[11px] leading-snug text-muted"
                              dir={isAr(c.detail) ? 'rtl' : 'ltr'}
                            >
                              {c.detail}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </>
                )
              })()}
            </Section>
          )}

          {/* evidence quotes */}
          {proof.evidence_segments.length > 0 && (
            <Section label="EVIDENCE · REPRESENTATIVE QUOTES">
              <div className="space-y-2">
                {proof.evidence_segments.map((e, i) => (
                  <div key={i} className="rounded-lg border border-border bg-card p-2.5">
                    <div className="flex items-start gap-1.5">
                      <Quote className="mt-0.5 h-3 w-3 shrink-0 text-faint" />
                      <div
                        className="text-[12px] leading-snug text-txt"
                        dir={isAr(e.segment_text) ? 'rtl' : 'ltr'}
                      >
                        {e.segment_text}
                      </div>
                    </div>
                    {e.confidence != null && (
                      <div className="mt-1 text-right font-mono text-[10px] text-faint">
                        {(e.confidence * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* related cases table */}
          {proof.related_cases.length > 0 && (
            <Section label={`RELATED CASES · ${proof.related_cases.length} SOURCE RECORDS`}>
              <div className="space-y-1.5">
                {proof.related_cases.map((c) => (
                  <div key={c.record_id} className="rounded-lg border border-border bg-card p-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className="truncate font-mono text-[10px] text-muted"
                        dir={isAr(c.service_id) ? 'rtl' : 'ltr'}
                      >
                        {c.service_id}
                      </span>
                      <span
                        className="shrink-0 font-mono text-[10px]"
                        style={{ color: sevColor(c.severity) }}
                      >
                        {c.sentiment_label} · sev {c.severity}
                      </span>
                    </div>
                    <div
                      className="mt-1 text-[12px] leading-snug text-txt"
                      dir={isAr(c.text) ? 'rtl' : 'ltr'}
                    >
                      {c.text}
                    </div>
                    <div className="mt-1 flex items-center justify-between font-mono text-[10px] text-faint">
                      <span>{c.source_type}</span>
                      <span>{(c.observed_at || '').slice(0, 10)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* forecast sparkline */}
          {fc && spark && spark.length > 1 && (
            <Section label="FORECAST · TREND">
              <div className="flex items-center gap-1.5">
                <TrendingUp
                  className={`h-3.5 w-3.5 ${fc.escalation?.escalating ? 'text-danger' : 'text-good'}`}
                />
                <span className="text-[12px] text-txt">
                  {fc.escalation?.escalating ? 'Escalating' : 'Stable'}
                  {typeof fc.escalation?.ratio === 'number' && (
                    <span className="ml-1 font-mono text-faint">×{fc.escalation.ratio.toFixed(2)}</span>
                  )}
                </span>
                <span className="ml-auto font-mono text-[10px] text-faint">{fc.source}</span>
              </div>
              <ResponsiveContainer width="100%" height={70}>
                <LineChart data={spark} margin={{ top: 6, right: 4, bottom: 0, left: 4 }}>
                  <XAxis dataKey="t" hide />
                  <Line type="monotone" dataKey="v" stroke="#3B82F6" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </Section>
          )}
        </>
      )}
    </aside>
  )
}
