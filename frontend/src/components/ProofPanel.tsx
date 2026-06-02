import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { LineChart, Line, XAxis, ResponsiveContainer } from 'recharts'
import {
  Loader2, ArrowLeft, X, FileSpreadsheet, ShieldCheck, ShieldAlert,
  Quote, TrendingUp, TrendingDown, CheckCircle2, XCircle,
  MessagesSquare, Brain, Layers,
} from 'lucide-react'
import { getProof, reportUrl, streamDebate, type ProofBundle, type DebateEvent } from '../lib/voc'

// agent persona colours for the debate stream
const ROLE_COLOR: Record<string, string> = {
  delegate: '#22D3EE', analyst: '#3B82F6', advocate: '#34D399', skeptic: '#FBBF24', synthesizer: '#A78BFA',
}

const SEV: Record<string, string> = { alert: '#F04359', warn: '#FBBF24', calm: '#34D399' }
const isAr = (s: string | null | undefined) => !!s && /[؀-ۿ]/.test(s)
const sevColor = (v: number) => (v >= 0.5 ? SEV.alert : v >= 0.3 ? SEV.warn : SEV.calm)
const sevLabel = (v: number) => (v >= 0.5 ? 'Critical' : v >= 0.3 ? 'Elevated' : 'Nominal')

function Section({ label, count, children }: { label: string; count?: number; children: React.ReactNode }) {
  return (
    <div className="border-b border-border p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="font-mono text-[10px] tracking-[0.14em] text-faint">{label}</span>
        {count != null && (
          <span className="rounded-full bg-soft px-1.5 py-px font-mono text-[9px] text-faint">{count}</span>
        )}
      </div>
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

  // ── Agent debate (streamed) ──────────────────────────────────────────────
  const [turns, setTurns] = useState<DebateEvent[]>([])
  const [dossier, setDossier] = useState<DebateEvent | null>(null)
  const [debating, setDebating] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    // reset the debate whenever the subject changes
    setTurns([]); setDossier(null); setDebating(false)
    abortRef.current?.abort()
  }, [query.type, query.key])

  async function runDebate() {
    if (debating) return
    setTurns([]); setDossier(null); setDebating(true)
    const ac = new AbortController()
    abortRef.current = ac
    try {
      await streamDebate({ type: query.type, key: query.key }, (e) => {
        if (e.type === 'dossier') setDossier(e)
        else if (e.type === 'turn' || e.type === 'synthesis') setTurns((xs) => [...xs, e])
      }, ac.signal)
    } catch {
      /* aborted or network error — leave whatever streamed */
    } finally {
      setDebating(false)
    }
  }

  return (
    <aside className="flex w-[384px] shrink-0 flex-col overflow-y-auto border-l border-border bg-sidebar">
      {/* sticky header / back */}
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-border bg-sidebar/95 px-4 py-3 backdrop-blur">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-[11px] text-muted transition-colors hover:bg-soft hover:text-txt"
        >
          <ArrowLeft className="h-3 w-3" />
          back
        </button>
        <span className="font-mono text-[10px] tracking-[0.18em] text-faint">PROOF</span>
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
          <Loader2 className="h-4 w-4 animate-spin text-blue" />
          building proof…
        </div>
      )}
      {err && !busy && (
        <div className="m-4 rounded-lg border border-danger/40 bg-card p-3 text-[12.5px] leading-snug text-danger">
          {err}
        </div>
      )}

      {proof && !busy && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          {/* PLAIN-LANGUAGE summary — for a non-technical reader, shown first */}
          {proof.plain && (
            <div className="border-b border-border bg-blue/5 p-4">
              <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[10px] tracking-[0.14em] text-blue">
                <Layers className="h-3 w-3" /> باختصار · IN PLAIN TERMS
              </div>
              <p dir="rtl" className="text-[13.5px] leading-[1.9] text-txt">
                {proof.plain}
              </p>
            </div>
          )}

          {/* subject hero — severity-tinted */}
          <div className="relative overflow-hidden border-b border-border p-4">
            <div
              className="pointer-events-none absolute inset-x-0 top-0 h-px"
              style={{ background: `linear-gradient(90deg, ${sevColor(proof.subject.severity_avg)}, transparent)` }}
            />
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] tracking-[0.14em] text-faint">
                {proof.subject.type.toUpperCase()}
              </span>
              <span
                className="rounded-full px-2 py-0.5 font-mono text-[10px] font-medium"
                style={{
                  color: sevColor(proof.subject.severity_avg),
                  background: `${sevColor(proof.subject.severity_avg)}1a`,
                }}
              >
                {sevLabel(proof.subject.severity_avg)} · sev {proof.subject.severity_avg}
              </span>
            </div>
            {proof.subject.label_ar && (
              <div className="mt-2 text-[15.5px] font-semibold leading-snug text-txt" dir="rtl">
                {proof.subject.label_ar}
              </div>
            )}
            {proof.subject.label_en && (
              <div className="mt-1 text-[12px] leading-snug text-muted" dir="ltr">
                {proof.subject.label_en}
              </div>
            )}
            <div className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[10px] text-faint">
              <span className="text-muted">{proof.subject.members} reports</span>
              <span>{proof.subject.signals} signals</span>
              {proof.subject.first_seen && <span>since {proof.subject.first_seen.slice(0, 10)}</span>}
              {proof.subject.last_seen && <span>→ {proof.subject.last_seen.slice(0, 10)}</span>}
            </div>
            {proof.subject.services.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
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

          {/* download report — primary CTA */}
          <div className="border-b border-border p-4">
            <a
              href={reportUrl(proof.subject.cluster_id)}
              download
              className="flex items-center justify-center gap-2 rounded-lg bg-good px-4 py-2.5 text-[13.5px] font-semibold text-[#04130C] shadow-lg shadow-good/20 transition-all hover:-translate-y-0.5 hover:opacity-95"
            >
              <FileSpreadsheet className="h-4 w-4" />
              Download Excel report
            </a>
            <p className="mt-2 text-[11px] leading-snug text-muted">
              Full evidence workbook — why-chain, validation checks, and every source record behind this finding.
            </p>
          </div>

          {/* agent debate — LightMem-augmented swarm arguing over the data */}
          <Section label="نقاش الوكلاء · AGENT DEBATE">
            {!turns.length && !debating && (
              <button
                onClick={runDebate}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-blue/40 bg-blue/10 px-4 py-2.5 text-[13px] font-semibold text-blue transition-colors hover:bg-blue/20"
              >
                <MessagesSquare className="h-4 w-4" />
                شغّل نقاش الوكلاء على هذه القضية
              </button>
            )}

            {dossier && (
              <div className="mb-3">
                <div className="mb-1.5 flex items-center gap-1.5 text-[10px] text-faint">
                  <Layers className="h-3 w-3" /> ذاكرة LightMem · {dossier.memory?.length ?? 0} محاور
                  <span className="ml-auto font-mono">{dossier.model ? dossier.model : 'grounded'}</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(dossier.memory ?? []).map((m, i) => (
                    <span key={i} dir="rtl" className="rounded-md border border-border bg-card px-1.5 py-0.5 text-[10px] text-muted">
                      «{m.topic}» · {m.count}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-2">
              {turns.map((t, i) => {
                const col = ROLE_COLOR[t.role ?? ''] ?? '#8B8D96'
                const isSynth = t.type === 'synthesis'
                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`rounded-lg border p-2.5 ${isSynth ? 'border-blue/40 bg-blue/5' : 'border-border bg-card'}`}
                  >
                    <div className="mb-1 flex items-center gap-1.5">
                      <span className="grid h-4 w-4 place-items-center rounded-full" style={{ background: col }}>
                        {isSynth ? <Brain className="h-2.5 w-2.5 text-white" /> : <span className="h-1.5 w-1.5 rounded-full bg-white" />}
                      </span>
                      <span className="text-[11px] font-semibold text-txt">{t.agent}</span>
                      {t.engine && <span className="ml-auto font-mono text-[9px] text-faint">{t.engine}</span>}
                    </div>
                    <div dir="rtl" className="text-[12px] leading-relaxed text-txt">{t.text}</div>
                    {isSynth && typeof t.confidence === 'number' && (
                      <div className="mt-1.5 font-mono text-[10px] text-faint">
                        الثقة {Math.round(t.confidence * 100)}% · {t.verdict}
                      </div>
                    )}
                  </motion.div>
                )
              })}
              {debating && (
                <div className="flex items-center gap-2 py-1 text-[11px] text-muted">
                  <Loader2 className="h-3 w-3 animate-spin" /> الوكلاء يتناقشون…
                </div>
              )}
            </div>

            {turns.length > 0 && !debating && (
              <button onClick={runDebate} className="mt-2 text-[11px] text-blue hover:underline">
                إعادة النقاش
              </button>
            )}
          </Section>

          {/* why-chain causal trace — numbered stepper */}
          <Section label="WHY THIS HAPPENS · 5-WHYS">
            <ol className="space-y-0">
              {proof.why_chain.map((w, i) => {
                const last = i === proof.why_chain.length - 1
                const txt = isAr(w.because) ? w.because : w.because_en || w.because
                return (
                  <li key={w.depth} className="relative pb-4 pl-8 last:pb-0">
                    {!last && (
                      <span className="absolute left-[11px] top-6 h-[calc(100%-1.25rem)] w-px bg-border" />
                    )}
                    <span
                      className="absolute left-0 top-0 grid h-[23px] w-[23px] place-items-center rounded-full text-[10px] font-bold"
                      style={
                        last
                          ? { background: SEV.alert, color: '#fff' }
                          : { background: 'var(--color-soft)', color: 'var(--color-muted)', boxShadow: 'inset 0 0 0 1px var(--color-border)' }
                      }
                    >
                      {last ? '!' : i + 1}
                    </span>
                    <div
                      className="text-[9.5px] font-mono uppercase tracking-[0.14em]"
                      style={{ color: last ? SEV.alert : 'var(--color-faint)' }}
                    >
                      {last ? 'root cause' : `why ${i + 1}`}
                    </div>
                    {w.question && !last && (
                      <div
                        className="mt-0.5 text-[11.5px] leading-snug text-muted"
                        dir={isAr(w.question) ? 'rtl' : 'ltr'}
                      >
                        {w.question}
                      </div>
                    )}
                    <div
                      className={`mt-0.5 text-[12.5px] leading-snug ${last ? 'font-semibold' : ''} text-txt`}
                      dir={isAr(txt) ? 'rtl' : 'ltr'}
                    >
                      {txt}
                    </div>
                    {w.evidence?.[0] && (
                      <div
                        className="mt-1.5 rounded-md bg-soft/60 px-2 py-1 text-[11px] leading-snug text-muted"
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
                className="mt-3 rounded-lg border border-blue/30 bg-blue/10 p-2.5 text-[12px] leading-snug text-txt"
                dir={isAr(proof.narration) ? 'rtl' : 'ltr'}
              >
                {proof.narration}
              </div>
            )}
          </Section>

          {/* validation verdict + checks */}
          {proof.validation && (
            <Section label="PROOF STRENGTH" count={proof.validation.checks.length}>
              {(() => {
                const v = proof.validation
                const ok = v.verdict?.toLowerCase().includes('valid') || v.score >= 0.5
                const VIcon = ok ? ShieldCheck : ShieldAlert
                const col = ok ? SEV.calm : SEV.alert
                return (
                  <>
                    <div className="flex items-center gap-2 rounded-lg border border-border bg-card p-2.5">
                      <VIcon className="h-4 w-4 shrink-0" style={{ color: col }} />
                      <span className="text-[13px] font-semibold capitalize text-txt">{v.verdict}</span>
                      <span className="ml-auto font-mono text-[11px]" style={{ color: col }}>
                        {(v.confidence * 100).toFixed(0)}% · {v.score.toFixed(2)}
                      </span>
                    </div>
                    {v.summary && (
                      <div
                        className="mt-2 text-[12px] leading-snug text-muted"
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
                          {/* score bar */}
                          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-soft">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${Math.round(Math.min(1, Math.max(0, c.score)) * 100)}%`,
                                background: c.pass ? SEV.calm : SEV.alert,
                              }}
                            />
                          </div>
                          {c.detail && (
                            <div
                              className="mt-1.5 text-[11px] leading-snug text-muted"
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
            <Section label="EVIDENCE · QUOTES" count={proof.evidence_segments.length}>
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

          {/* related cases */}
          {proof.related_cases.length > 0 && (
            <Section label="RELATED CASES · SOURCE RECORDS" count={proof.related_cases.length}>
              <div className="space-y-1.5">
                {proof.related_cases.map((c) => (
                  <div key={c.record_id} className="rounded-lg border border-border bg-card p-2.5 transition-colors hover:border-border/70 hover:bg-cardhi">
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
                {fc.escalation?.escalating ? (
                  <TrendingUp className="h-3.5 w-3.5 text-danger" />
                ) : (
                  <TrendingDown className="h-3.5 w-3.5 text-good" />
                )}
                <span className="text-[12px] font-medium text-txt">
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
        </motion.div>
      )}
    </aside>
  )
}
