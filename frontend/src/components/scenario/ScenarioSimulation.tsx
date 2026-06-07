// ScenarioSimulation — the full reworked Simulation page body. Owns the run
// state and the NDJSON scenario stream, then assembles the seven scenario
// sub-components into one pipeline view: intake → stepper → precedents →
// agents → simulation charts → verdict → (optional) agent debate.
//
// Data source: streamScenario() → POST /api/scenario/detect, which emits one
// ScenarioEvent per NDJSON line (stage: parse | retrieve | select_agents |
// simulate | debate | detect_predict | done). Each stage is accumulated into
// local state and rendered the moment its data arrives. Arabic-first; AEGIS
// dark crisis-console tokens.

import { useCallback, useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { AlertTriangle, Info, SlidersHorizontal, ChevronDown } from 'lucide-react'
import {
  streamScenario,
  getScenarioOptions,
  getScenarioReport,
  saveSolution,
  startDeliberationJob,
  getDeliberationStatus,
  getActiveDeliberations,
  getSavedSolutions,
  getSolution,
  solutionMarkdownUrl,
  type SavedSolutionMeta,
  type DeliberationEvent,
  type ScenarioReportDoc,
  type ScenarioEvent,
  type ScenarioCitation,
  type ScenarioAgent,
  type ScenarioOption,
  type ScenarioPastRun,
  type ScenarioSolutionEval,
  type ScenarioEvidence,
} from '../../lib/voc'
import ScenarioInput from './ScenarioInput'
import ScenarioStepper, { type StageKey } from './ScenarioStepper'
import PrecedentCards from './PrecedentCards'
import AgentRoster from './AgentRoster'
import ScenarioCharts from './ScenarioCharts'
import VerdictPanel from './VerdictPanel'
import DebateStream, { type DebateTurn } from './DebateStream'
import PastRuns from './PastRuns'
import SolutionEval from './SolutionEval'
import ResultSummary from './ResultSummary'
import ScenarioSuggestions from './ScenarioSuggestions'
import EvidencePanel from './EvidencePanel'
import JordanDroughtStudy from './JordanDroughtStudy'
import ScenarioReport, { type ReportData } from './ScenarioReport'
import { downloadElementsAsPdf } from '../../lib/pdf'
import { FileText, Download, X, Users, Loader2, MessagesSquare, Save, FileDown, Check, History } from 'lucide-react'

// Linear stage order — drives the stepper's "current = next logical stage".
const STAGE_ORDER: StageKey[] = ['parse', 'retrieve', 'select_agents', 'simulate', 'detect_predict']

// The stage that should light up after `stage` completes (null past the end).
function nextStage(stage: StageKey): StageKey | null {
  const i = STAGE_ORDER.indexOf(stage)
  return i >= 0 && i < STAGE_ORDER.length - 1 ? STAGE_ORDER[i + 1] : null
}

interface VerdictState {
  detection: ScenarioEvent['detection']
  prediction: ScenarioEvent['prediction']
  confidence: ScenarioEvent['confidence']
}

const PHASE_AR: Record<string, string> = { analysis: 'تحليل', negotiation: 'تفاوض', vote: 'تصويت' }

// Render the saved solution (the agents' argument + the final report) as Markdown for download.
function buildSolutionMarkdown(
  scenario: string,
  turns: DeliberationEvent[],
  tallies: DeliberationEvent[],
  doc: ScenarioReportDoc | null,
): string {
  const L: string[] = []
  L.push(`# ${doc?.meta?.title_ar ?? 'تقرير حلّ — AEGIS'}`, '')
  L.push(`**السيناريو:** ${scenario}`, '')
  if (turns.length) {
    L.push('## مداولة الوكلاء (المحضر)', '')
    for (const t of turns) {
      const ph = PHASE_AR[t.phase ?? ''] ?? (t.phase ?? '')
      L.push(`### ${t.persona ?? ''} — ${ph}${t.round ? ` · جولة ${t.round}` : ''}`)
      L.push((t.text ?? '').trim(), '')
    }
    for (const v of tallies) {
      L.push(`> تصويت جولة ${v.round}: ${v.ready}/${v.total} جاهز — ${v.converged ? 'توافق ✓' : 'لم يكتمل التوافق'}`)
    }
    L.push('')
  }
  const kf = doc?.key_figures ?? []
  if (kf.length) {
    L.push('## الأرقام الرئيسية', '')
    for (const r of kf) L.push(`- **${r.label}:** ${r.value}${r.source ? `  _( ${r.source} )_` : ''}`)
    L.push('')
  }
  for (const s of doc?.sections ?? []) {
    L.push(`## ${s.title_ar || s.title_en || ''}`, '')
    for (const p of s.paragraphs ?? []) L.push(p.trim(), '')
  }
  L.push('---', 'AEGIS Crisis Console · لدعم القرار فقط — لا توقّع للواقع.')
  return L.join('\n')
}

function downloadTextFile(filename: string, text: string) {
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export default function ScenarioSimulation() {
  // ── intake ──────────────────────────────────────────────────────────────
  const [text, setText] = useState('')
  const [location, setLocation] = useState('')
  const [service, setService] = useState('')
  const [solution, setSolution] = useState('')
  const [runDebate, setRunDebate] = useState(false)
  const [running, setRunning] = useState(false)
  const [showTech, setShowTech] = useState(false)

  // dropdown options (governorates + services), fetched once
  const [locations, setLocations] = useState<ScenarioOption[]>([])
  const [services, setServices] = useState<ScenarioOption[]>([])
  useEffect(() => {
    getScenarioOptions()
      .then((o) => { setLocations(o.locations ?? []); setServices(o.services ?? []) })
      .catch(() => { /* dropdowns just stay empty */ })
  }, [])

  // Read sessionStorage pre-fill written by the map "Analyze in Simulation" button.
  // Articles are stored in a ref so they can be included in the next run body.
  const prefillArticlesRef = useRef<object[]>([])
  useEffect(() => {
    const raw = sessionStorage.getItem('aegis_scenario_prefill')
    if (!raw) return
    try {
      const prefill = JSON.parse(raw) as { text?: string; location?: string; articles?: object[] }
      if (prefill.text) setText(prefill.text)
      if (prefill.location) setLocation(prefill.location)
      if (prefill.articles?.length) prefillArticlesRef.current = prefill.articles
    } catch { /* ignore malformed */ }
    sessionStorage.removeItem('aegis_scenario_prefill')
  }, [])

  // ── accumulated stage data ──────────────────────────────────────────────
  const [parse, setParse] = useState<{
    script: 'ar' | 'latin'
    domain: string
    using_llm: boolean
    warnings: string[]
  } | null>(null)
  const [doneStages, setDoneStages] = useState<StageKey[]>([])
  const [current, setCurrent] = useState<StageKey | null>(null)
  const [cases, setCases] = useState<ScenarioCitation[]>([])
  const [retrieved, setRetrieved] = useState(false)
  const [bestRelevance, setBestRelevance] = useState(0)
  const [agents, setAgents] = useState<ScenarioAgent[]>([])
  const [selectEngine, setSelectEngine] = useState('')
  const [sim, setSim] = useState<ScenarioEvent | null>(null)
  const [debateTurns, setDebateTurns] = useState<DebateTurn[]>([])
  const [verdict, setVerdict] = useState<VerdictState | null>(null)
  const [flagsAr, setFlagsAr] = useState<string[]>([])
  const [doneEngine, setDoneEngine] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pastRuns, setPastRuns] = useState<ScenarioPastRun[]>([])
  const [pastTotal, setPastTotal] = useState(0)
  const [solutionEval, setSolutionEval] = useState<ScenarioSolutionEval | null>(null)
  const [evidence, setEvidence] = useState<ScenarioEvidence[]>([])
  const [evidenceShown, setEvidenceShown] = useState(false)
  const [evidenceAbstained, setEvidenceAbstained] = useState(false)
  const [showReport, setShowReport] = useState(false)
  const [newsContext, setNewsContext] = useState<{
    gov: string | null; articles: { title: string; source: string; published: string | null }[]
  } | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [reportDoc, setReportDoc] = useState<ScenarioReportDoc | null>(null)
  const [delibTurns, setDelibTurns] = useState<DeliberationEvent[]>([])
  const [delibTallies, setDelibTallies] = useState<DeliberationEvent[]>([])
  const [delibStatus, setDelibStatus] = useState<'idle' | 'running' | 'done'>('idle')
  const [delibMsg, setDelibMsg] = useState<string | null>(null)
  const [delibSynth, setDelibSynth] = useState<{ done: number; total: number; title: string } | null>(null)
  const [delibIteration, setDelibIteration] = useState(0)
  const [savedSol, setSavedSol] = useState(false)
  const [savingSol, setSavingSol] = useState(false)
  const [history, setHistory] = useState<SavedSolutionMeta[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [bgJob, setBgJob] = useState<{ job_id: string; scenario: string; iteration: number } | null>(null)
  const delibPoll = useRef<number | null>(null)
  const delibJobId = useRef<string | null>(null)
  const delibCursor = useRef(0)

  const loadHistory = useCallback(() => {
    getSavedSolutions().then((r) => setHistory(r.solutions ?? [])).catch(() => {})
  }, [])

  // Apply one streamed deliberation event to the UI (shared by live polling + re-attach).
  const applyDelibEvent = (e: DeliberationEvent) => {
    if (e.stage === 'agent') setDelibTurns((t) => [...t, e])
    else if (e.stage === 'tally') setDelibTallies((t) => [...t, e])
    else if (e.stage === 'fallback') setDelibMsg(e.message_ar ?? null)
    else if (e.stage === 'synthesis') setDelibSynth({ done: 0, total: e.sections_total ?? 6, title: '' })
    else if (e.stage === 'section') setDelibSynth({ done: e.index ?? 0, total: e.total ?? 6, title: e.title_ar ?? '' })
  }

  // Poll a background deliberation job. The job runs server-side, so it keeps going even
  // if the modal closes; we just reflect its progress while mounted.
  const pollJob = useCallback((jobId: string) => {
    getDeliberationStatus(jobId, delibCursor.current)
      .then((s) => {
        if (!s.ok) { setDelibStatus('done'); setBgJob(null); return }
        s.events.forEach(applyDelibEvent)
        delibCursor.current = s.total_events
        setDelibIteration(s.iteration)
        setBgJob({ job_id: jobId, scenario: s.scenario, iteration: s.iteration })
        if (s.report) {
          setDelibSynth(null)
          setReportDoc({
            ok: true, sections: s.report.sections, key_figures: s.report.key_figures, references: s.report.references,
            meta: { title_ar: 'تقرير حالة — مداولة الوكلاء', scenario: s.scenario || text,
              report_no: `مداولة حيّة — ${s.iteration} جولة`, generated_at: '', flagship: sim?.engine === 'cascade' },
          })
        }
        if (s.status === 'running') {
          delibPoll.current = window.setTimeout(() => pollJob(jobId), 1500)
        } else {
          setDelibStatus('done')
          setDelibSynth(null)
          setBgJob(null)
          if (s.saved) { setSavedSol(true); loadHistory() }
        }
      })
      .catch(() => { delibPoll.current = window.setTimeout(() => pollJob(jobId), 2500) })
  }, [text, sim, loadHistory])

  const startDeliberation = useCallback(async () => {
    if (delibPoll.current) { clearTimeout(delibPoll.current); delibPoll.current = null }
    setDelibTurns([]); setDelibTallies([]); setDelibMsg(null); setDelibSynth(null)
    setSavedSol(false); setDelibIteration(0); delibCursor.current = 0
    setDelibStatus('running')
    try {
      const r = await startDeliberationJob({ text, sim, detection: verdict?.detection, prediction: verdict?.prediction, confidence: verdict?.confidence, evidence, rounds: 3 })
      if (r.ok && r.job_id) { delibJobId.current = r.job_id; pollJob(r.job_id) }
      else setDelibStatus('done')
    } catch { setDelibStatus('done') }
  }, [text, sim, verdict, evidence, pollJob])

  // Re-attach to a still-running background deliberation on mount; load the history.
  useEffect(() => {
    loadHistory()
    getActiveDeliberations()
      .then((r) => {
        const live = (r.jobs || []).find((jb) => jb.status === 'running')
        if (live) setBgJob({ job_id: live.job_id, scenario: live.scenario, iteration: live.iteration })
      })
      .catch(() => {})
    return () => { if (delibPoll.current) clearTimeout(delibPoll.current) }
  }, [loadHistory])

  // Resume watching a background job (started here earlier, or found on mount).
  const resumeJob = useCallback((jobId: string) => {
    if (delibPoll.current) { clearTimeout(delibPoll.current); delibPoll.current = null }
    setDelibTurns([]); setDelibTallies([]); setDelibMsg(null); setDelibSynth(null)
    delibCursor.current = 0
    delibJobId.current = jobId
    setShowReport(true)
    setDelibStatus('running')
    pollJob(jobId)
  }, [pollJob])

  // Open a saved solution from the history (its argument transcript + report).
  const openSaved = useCallback((id: string) => {
    if (delibPoll.current) { clearTimeout(delibPoll.current); delibPoll.current = null }
    setShowHistory(false)
    getSolution(id).then((sol) => {
      setDelibTurns((sol.transcript || []).filter((e) => e.stage === 'agent'))
      setDelibTallies((sol.tallies || []))
      setDelibIteration(Number((sol.meta || {}).iterations) || 0)
      setDelibStatus('done')
      setDelibSynth(null)
      setSavedSol(true)
      setReportDoc({ ...(sol.report as ScenarioReportDoc), meta: { title_ar: sol.title_ar, scenario: sol.scenario, report_no: 'حلّ محفوظ', generated_at: sol.ts, flagship: false } })
      setShowReport(true)
    }).catch(() => {})
  }, [])

  const openReport = useCallback(async () => {
    setReportDoc(null)
    setDelibTurns([])
    setDelibTallies([])
    setDelibStatus('idle')
    setDelibMsg(null)
    setDelibSynth(null)
    setShowReport(true)
    try {
      const doc = await getScenarioReport({
        text,
        sim,
        detection: verdict?.detection,
        prediction: verdict?.prediction,
        confidence: verdict?.confidence,
        evidence,
      })
      if (doc.ok) setReportDoc(doc)
    } catch {
      /* the fallback summary renders */
    }
  }, [text, sim, verdict, evidence])

  // Persist the deliberated solution (the agents' argument + the final report).
  const saveSolutionNow = useCallback(async () => {
    if (!reportDoc || savingSol) return
    setSavingSol(true)
    try {
      const r = await saveSolution({
        scenario: text,
        transcript: delibTurns.map((t) => ({ persona: t.persona, role: t.role, round: t.round, phase: t.phase, text: t.text })),
        tallies: delibTallies.map((v) => ({ round: v.round, ready: v.ready, total: v.total, converged: v.converged })),
        report: reportDoc,
        meta: { deliberated: delibTurns.length > 0, engine: sim?.engine ?? null },
      })
      if (r.ok) setSavedSol(true)
    } catch {
      /* leave un-saved; the download still works */
    } finally {
      setSavingSol(false)
    }
  }, [reportDoc, text, delibTurns, delibTallies, sim, savingSol])

  // Download the argument + report as a Markdown file (works offline, no save needed).
  const downloadSolutionMarkdown = useCallback(() => {
    if (!reportDoc) return
    const md = buildSolutionMarkdown(text, delibTurns, delibTallies, reportDoc)
    const stamp = new Date().toISOString().slice(0, 10)
    downloadTextFile(`AEGIS-Solution-${stamp}.md`, md)
  }, [reportDoc, text, delibTurns, delibTallies])

  const downloadReport = useCallback(async () => {
    const main = document.getElementById('aegis-report')
    const refsPage = document.getElementById('aegis-references-page')
    if (!main) return
    setDownloading(true)
    try {
      const stamp = new Date().toISOString().slice(0, 10)
      const els = [main, refsPage].filter(Boolean) as HTMLElement[]
      await downloadElementsAsPdf(els, `AEGIS-Report-${stamp}.pdf`)
    } catch {
      /* user can retry */
    } finally {
      setDownloading(false)
    }
  }, [])

  const abortRef = useRef<AbortController | null>(null)
  const startedRef = useRef(false)

  // Clear every accumulated stage field back to its initial value.
  const resetState = useCallback(() => {
    setParse(null)
    setDoneStages([])
    setCurrent(null)
    setCases([])
    setRetrieved(false)
    setBestRelevance(0)
    setAgents([])
    setSelectEngine('')
    setSim(null)
    setDebateTurns([])
    setVerdict(null)
    setFlagsAr([])
    setDoneEngine(null)
    setError(null)
    setPastRuns([])
    setPastTotal(0)
    setSolutionEval(null)
    setEvidence([])
    setEvidenceShown(false)
    setEvidenceAbstained(false)
    setNewsContext(null)
  }, [])

  const onEvent = useCallback((e: ScenarioEvent) => {
    switch (e.stage) {
      case 'parse':
        setParse({
          script: e.script ?? 'ar',
          domain: e.domain ?? '',
          using_llm: !!e.using_llm,
          warnings: e.warnings ?? [],
        })
        setDoneStages((d) => [...d, 'parse'])
        setCurrent(nextStage('parse'))
        break
      case 'retrieve':
        setCases(e.cases ?? [])
        setBestRelevance(e.best_relevance ?? 0)
        setRetrieved(true)
        setDoneStages((d) => [...d, 'retrieve'])
        setCurrent(nextStage('retrieve'))
        break
      case 'news_context':
        setNewsContext({ gov: e.gov ?? null, articles: e.articles ?? [] })
        break
      case 'history':
        setPastRuns(e.runs ?? [])
        setPastTotal(e.total ?? 0)
        break
      case 'select_agents':
        setAgents(e.agents ?? [])
        setSelectEngine(e.engine ?? '')
        setDoneStages((d) => [...d, 'select_agents'])
        setCurrent(nextStage('select_agents'))
        break
      case 'simulate':
        setSim(e)
        setDoneStages((d) => [...d, 'simulate'])
        setCurrent(nextStage('simulate'))
        break
      case 'evidence':
        setEvidence(e.items ?? [])
        setEvidenceAbstained(!!e.abstained)
        setEvidenceShown(true)
        break
      case 'debate':
        setDebateTurns((t) => [
          ...t,
          {
            role: e.role ?? '',
            agent: e.agent ?? '',
            text: e.text ?? '',
            engine: e.engine,
          },
        ])
        break
      case 'detect_predict':
        if (e.detection && e.prediction && e.confidence) {
          setVerdict({
            detection: e.detection,
            prediction: e.prediction,
            confidence: e.confidence,
          })
        }
        setFlagsAr(e.degradation_flags_ar ?? [])
        setDoneStages((d) => [...d, 'detect_predict'])
        setCurrent(nextStage('detect_predict'))
        break
      case 'solution_eval':
        setSolutionEval({
          alignment: e.alignment ?? 'novel',
          alignment_ar: e.alignment_ar ?? '',
          alignment_score: e.alignment_score ?? 0,
          matched_success: e.matched_success ?? null,
          matched_anti_pattern: e.matched_anti_pattern ?? null,
          optimized_solution: e.optimized_solution ?? '',
          expected_results: e.expected_results ?? {},
          confidence_band: e.confidence_band ?? 'low',
          confidence_band_ar: e.confidence_band_ar ?? '',
        })
        break
      case 'done':
        setRunning(false)
        setDoneEngine(e.engine ?? null)
        setCurrent(null)
        break
      default:
        break
    }
  }, [])

  const runWith = useCallback(async (t: string) => {
    const txt = (t || '').trim()
    if (txt.length < 6) return
    // Abort any in-flight run before starting a fresh one.
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    resetState()
    startedRef.current = true
    setRunning(true)
    setCurrent('parse')

    const articles = prefillArticlesRef.current.length > 0
      ? prefillArticlesRef.current.splice(0) // consume once per run
      : undefined
    const body = {
      text: txt,
      run_debate: runDebate,
      top_k: 6,
      location: location || undefined,
      service: service || undefined,
      solution: solution.trim() || undefined,
      ...(articles ? { rss_articles: articles } : {}),
    }

    try {
      await streamScenario(body, onEvent, controller.signal)
    } catch (err) {
      // A deliberate abort (new run / reset) is not an error.
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        setError(err instanceof Error ? err.message : 'تعذّر تشغيل المحاكاة')
      }
    } finally {
      setRunning(false)
    }
  }, [location, service, solution, runDebate, onEvent, resetState])

  const onRun = useCallback(() => runWith(text), [runWith, text])
  // pick a suggested scenario/question → fill the box and run it
  const onPick = useCallback((t: string) => { setText(t); runWith(t) }, [runWith])

  const onReset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    startedRef.current = false
    setRunning(false)
    resetState()
  }, [resetState])

  const warnings = parse?.warnings ?? []
  const started = startedRef.current

  const reportData: ReportData = {
    text,
    domain: parse?.domain,
    location,
    service,
    engine: doneEngine ?? sim?.engine ?? null,
    generatedAt: new Date().toISOString().slice(0, 16).replace('T', ' ') + ' UTC',
    detection: verdict?.detection ?? undefined,
    prediction: verdict?.prediction ?? undefined,
    confidence: verdict?.confidence ?? undefined,
    flagsAr,
    sim,
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[1340px] px-8 py-7">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-[28px] font-semibold text-txt" dir="auto">
              المحاكاة
              <span className="ml-2 text-[14px] font-normal uppercase tracking-wide text-faint">
                · SIMULATION
              </span>
            </h1>
            <p className="mt-1.5 text-[14px] text-muted" dir="auto">
              حاكِ أزمة جديدة: استرجاع السوابق ← اختيار الوكلاء ← محاكاة ← كشف وتنبؤ
            </p>
          </div>
          {verdict && (
            <button
              type="button"
              onClick={openReport}
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-3.5 py-2.5 text-[13.5px] font-medium text-muted transition-colors hover:bg-cardhi hover:text-txt"
            >
              <FileText className="h-4 w-4" />
              <span dir="auto">تقرير كامل (PDF)</span>
            </button>
          )}
        </div>

        {/* Intake */}
        <div className="mt-6">
          <ScenarioInput
            text={text}
            onText={setText}
            location={location}
            onLocation={setLocation}
            service={service}
            onService={setService}
            solution={solution}
            onSolution={setSolution}
            locations={locations}
            services={services}
            runDebate={runDebate}
            onToggleDebate={setRunDebate}
            running={running}
            onRun={onRun}
            onReset={onReset}
          />
        </div>

        {/* Parse warnings */}
        {warnings.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="mt-4 flex items-start gap-2.5 rounded-xl border border-warn/30 bg-warn/10 px-4 py-3 text-[13px] text-warn"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="flex flex-wrap gap-x-3 gap-y-1" dir="auto">
              {warnings.map((w, i) => (
                <span key={i}>{w}</span>
              ))}
            </div>
          </motion.div>
        )}

        {/* Error banner */}
        {error && (
          <div className="mt-4 flex items-center gap-2.5 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-[13px] text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span dir="auto">
              تعذّر الوصول إلى محرّك المحاكاة: <span className="font-mono">{error}</span>
            </span>
          </div>
        )}

        {/* Idle — ready-made scenarios + questions to run with one click */}
        {!started && (
          <div className="mt-6">
            <ScenarioSuggestions onPick={onPick} disabled={running} />
          </div>
        )}

        {/* Pipeline progress */}
        {started && (
          <div className="mt-6">
            <ScenarioStepper done={doneStages} current={current} />
          </div>
        )}

        {/* Similar past runs — learning memory */}
        {pastRuns.length > 0 && (
          <div className="mt-4">
            <PastRuns runs={pastRuns} total={pastTotal} />
          </div>
        )}

        {/* END RESULT — the plain conclusion, first and prominent */}
        {verdict && verdict.detection && verdict.prediction && verdict.confidence && (
          <>
            <div className="mt-6">
              <ResultSummary
                detection={verdict.detection}
                prediction={verdict.prediction}
                confidence={verdict.confidence}
              />
            </div>
            <div className="mt-4">
              <VerdictPanel
                detection={verdict.detection}
                prediction={verdict.prediction}
                confidence={verdict.confidence}
                flagsAr={flagsAr}
              />
            </div>
          </>
        )}

        {/* Jordan drought flagship — cited cascade study + charts (the analysis) */}
        {sim && sim.engine === 'cascade' && (
          <div className="mt-6">
            <JordanDroughtStudy sim={sim} />
          </div>
        )}

        {/* Live news context — articles fetched from aegis_news for the location */}
        {newsContext && newsContext.articles.length > 0 && (
          <div className="mt-6 rounded-xl border border-border bg-card p-4">
            <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue" />
              Live News Context
              <span className="rounded bg-soft px-1.5 py-0.5 font-mono normal-case tracking-normal">
                {newsContext.articles.length} articles
              </span>
            </div>
            <ul className="space-y-2 max-h-[220px] overflow-y-auto">
              {newsContext.articles.map((a, i) => (
                <li key={i} className="flex items-start gap-2 rounded-lg border border-border/50 bg-soft/40 px-3 py-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue/70" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-medium leading-snug text-txt" dir="rtl">{a.title}</p>
                    <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-faint" dir="rtl">
                      <span>{a.source}</span>
                      {a.published && <><span>·</span><span className="font-mono">{a.published.slice(0,10)}</span></>}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Evidence & references (verified, from the legal research agent) */}
        {evidenceShown && (
          <div className="mt-6">
            <EvidencePanel items={evidence} abstained={evidenceAbstained} />
          </div>
        )}

        {/* Solution validator / optimizer */}
        {solutionEval && (
          <div className="mt-6">
            <SolutionEval ev={solutionEval} />
          </div>
        )}

        {/* Technical details — collapsed by default (charts, precedents, agents, debate) */}
        {(retrieved || agents.length > 0 || sim || debateTurns.length > 0) && (
          <div className="mt-6">
            <button
              type="button"
              onClick={() => setShowTech((v) => !v)}
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-3.5 py-2 text-[13px] font-medium text-muted transition-colors hover:bg-cardhi hover:text-txt"
            >
              <SlidersHorizontal className="h-4 w-4" />
              <span dir="auto">{showTech ? 'إخفاء التفاصيل التقنية' : 'عرض التفاصيل التقنية'}</span>
              <ChevronDown className={`h-4 w-4 transition-transform ${showTech ? 'rotate-180' : ''}`} />
            </button>

            {showTech && (
              <div className="mt-4 space-y-6">
                {sim && <ScenarioCharts sim={sim} />}
                {retrieved && <PrecedentCards cases={cases} bestRelevance={bestRelevance} />}
                {agents.length > 0 && <AgentRoster agents={agents} engine={selectEngine} />}
                {debateTurns.length > 0 && <DebateStream turns={debateTurns} />}
              </div>
            )}
          </div>
        )}

        {/* Try another example */}
        {started && !running && verdict && (
          <div className="mt-6">
            <ScenarioSuggestions compact onPick={onPick} disabled={running} />
          </div>
        )}

        {/* Completion engine footnote */}
        {doneEngine && !running && (
          <div className="mt-4 flex items-center gap-2 text-[12px] text-faint">
            <Info className="h-3.5 w-3.5" />
            <span dir="auto">
              اكتملت المحاكاة · المحرّك:{' '}
              <span className="font-mono">{doneEngine}</span>
            </span>
          </div>
        )}
      </div>

      {/* Full report — preview + one-click PDF download */}
      {showReport && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-6"
          onClick={() => setShowReport(false)}
        >
          <div className="my-4 w-[860px] max-w-[94vw]" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between gap-2">
              <button
                type="button"
                onClick={startDeliberation}
                disabled={delibStatus === 'running'}
                className="flex items-center gap-2 rounded-lg border border-blue/40 bg-blue/15 px-3.5 py-2 text-[13.5px] font-medium text-white transition-colors hover:bg-blue/25 disabled:opacity-60"
                title="يستدعي وكلاء يتحاورون ويحلّلون ويتفاوضون على التقرير — يتطلّب نموذجًا متاحًا"
              >
                {delibStatus === 'running' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Users className="h-4 w-4" />}
                <span dir="auto">{delibStatus === 'running' ? 'الوكلاء يتداولون…' : 'مداولة الوكلاء (تحليل حيّ)'}</span>
              </button>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={saveSolutionNow}
                  disabled={!reportDoc || savingSol}
                  className="flex items-center gap-2 rounded-lg border border-good/40 bg-good/15 px-3.5 py-2 text-[13.5px] font-medium text-white transition-colors hover:bg-good/25 disabled:opacity-50"
                  title="حفظ الحلّ (محضر المداولة + التقرير) لاسترجاعه لاحقًا"
                >
                  {savingSol ? <Loader2 className="h-4 w-4 animate-spin" /> : savedSol ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
                  <span dir="auto">{savedSol ? 'حُفِظ ✓' : savingSol ? 'يحفظ…' : 'حفظ الحلّ'}</span>
                </button>
                <button
                  type="button"
                  onClick={downloadSolutionMarkdown}
                  disabled={!reportDoc}
                  className="flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3.5 py-2 text-[13.5px] text-white transition-colors hover:bg-white/20 disabled:opacity-50"
                  title="تنزيل المحضر + التقرير كملف Markdown"
                >
                  <FileDown className="h-4 w-4" />
                  <span dir="auto">تنزيل (Markdown)</span>
                </button>
                <button
                  type="button"
                  onClick={downloadReport}
                  disabled={downloading}
                  className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-60"
                >
                  <Download className="h-4 w-4" />
                  <span dir="auto">{downloading ? 'جارٍ التنزيل…' : 'تنزيل PDF'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => { setShowHistory((v) => !v); loadHistory() }}
                  className="flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-[13.5px] text-white transition-colors hover:bg-white/20"
                  title="سجلّ المحاكاة — الحلول المحفوظة"
                >
                  <History className="h-4 w-4" />
                  <span dir="auto">السجل{history.length ? ` (${history.length})` : ''}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowReport(false)}
                  className="flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-[13.5px] text-white transition-colors hover:bg-white/20"
                >
                  <X className="h-4 w-4" />
                  <span dir="auto">إغلاق</span>
                </button>
              </div>
            </div>

            {/* A deliberation still running server-side (found on mount or after closing) */}
            {bgJob && delibStatus !== 'running' && (
              <div className="mb-3 flex items-center justify-between gap-2 rounded-lg border border-blue/40 bg-blue/10 px-3 py-2 text-[12.5px] text-blue" dir="auto">
                <span className="inline-flex items-center gap-1.5"><Loader2 className="h-3.5 w-3.5 animate-spin" /> مداولة جارية في الخلفية — الجولة {bgJob.iteration}</span>
                <button onClick={() => resumeJob(bgJob.job_id)} className="rounded-md border border-blue/40 px-2 py-1 font-medium transition-colors hover:bg-blue/20">استئناف المتابعة</button>
              </div>
            )}

            {/* Simulation history — saved solutions, re-openable + downloadable */}
            {showHistory && (
              <div className="mb-3 max-h-[40vh] overflow-y-auto rounded-lg border border-border bg-card p-3">
                <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-txt" dir="auto">
                  <History className="h-4 w-4 text-blue" /> سجلّ المحاكاة ({history.length})
                </div>
                {history.length === 0 ? (
                  <p className="text-[12.5px] text-faint" dir="auto">لا توجد حلول محفوظة بعد.</p>
                ) : (
                  <div className="space-y-1.5">
                    {history.map((h) => (
                      <div key={h.id} className="flex items-center justify-between gap-2 rounded-md border border-border bg-bg px-2.5 py-1.5 text-[12px]">
                        <button
                          onClick={() => openSaved(h.id)}
                          className="min-w-0 flex-1 text-right transition-colors hover:text-blue"
                          dir="auto"
                          title="فتح الحلّ المحفوظ"
                        >
                          <span className="block truncate text-txt">{h.scenario || h.title_ar}</span>
                          <span className="text-[10.5px] text-faint">{h.ts?.slice(0, 16).replace('T', ' ')} · {h.n_turns} مداخلة{h.deliberated ? ' · مداولة' : ''}</span>
                        </button>
                        <a
                          href={solutionMarkdownUrl(h.id)}
                          download
                          className="shrink-0 rounded-md border border-white/15 bg-white/5 px-2 py-1 text-faint transition-colors hover:text-txt"
                          title="تنزيل Markdown"
                        >
                          <FileDown className="h-3.5 w-3.5" />
                        </a>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Live deliberation transcript (UI only — not part of the PDF) */}
            {(delibTurns.length > 0 || delibMsg || delibStatus !== 'idle') && (
              <div className="mb-3 max-h-[40vh] overflow-y-auto rounded-lg border border-border bg-card p-4">
                <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-txt">
                  <MessagesSquare className="h-4 w-4 text-blue" />
                  <span dir="auto">مداولة الوكلاء · تحليل وتفاوض حيّ</span>
                  {delibIteration > 0 && (
                    <span className="rounded bg-soft px-1.5 py-0.5 text-[11px] text-faint tnum" dir="auto">الجولة {delibIteration}</span>
                  )}
                  {delibStatus === 'running' && <Loader2 className="h-3.5 w-3.5 animate-spin text-blue" />}
                  {delibStatus === 'running' && <span className="text-[11px] text-faint" dir="auto">· تعمل في الخلفية</span>}
                </div>
                {delibMsg && (
                  <div className="mb-2 rounded-md border border-warn/30 bg-warn/10 p-2.5 text-[12.5px] text-warn" dir="auto">
                    {delibMsg}
                  </div>
                )}
                <div className="space-y-2">
                  {delibTurns.map((t, i) => {
                    const phaseAr = t.phase === 'vote' ? 'تصويت' : t.phase === 'negotiation' ? 'تفاوض' : 'تحليل'
                    const tone = t.phase === 'vote' ? 'text-warn' : 'text-blue'
                    return (
                      <div key={i} className="rounded-md border border-border bg-bg p-2.5">
                        <div className="mb-1 flex items-center gap-2 text-[12px]">
                          <span className={`font-semibold ${tone}`} dir="auto">{t.persona}</span>
                          <span className="rounded bg-soft px-1.5 py-0.5 text-[10.5px] text-faint" dir="auto">
                            {phaseAr} · جولة {t.round}
                          </span>
                        </div>
                        <p className="text-[12.5px] leading-relaxed text-muted" dir="auto">{t.text}</p>
                      </div>
                    )
                  })}
                  {delibTallies.map((v, i) => (
                    <div
                      key={`tally-${i}`}
                      className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[12px] ${
                        v.converged ? 'border-good/30 bg-good/10 text-good' : 'border-border bg-soft text-muted'
                      }`}
                      dir="auto"
                    >
                      <span className="font-medium">نتيجة التصويت · جولة {v.round}:</span>
                      <span className="tnum">{v.ready}/{v.total} جاهز</span>
                      <span>{v.converged ? '· توافق ✓ (التقرير جاهز)' : '· لم يكتمل التوافق — جولة أخرى'}</span>
                    </div>
                  ))}
                  {delibSynth && (
                    <div className="rounded-md border border-blue/30 bg-blue/10 px-2.5 py-1.5 text-[12px] text-blue" dir="auto">
                      <span className="inline-flex items-center gap-2">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span className="font-medium">يصيغ المُنسّق التقرير النهائي</span>
                        <span className="tnum">{delibSynth.done}/{delibSynth.total}</span>
                        {delibSynth.title && <span className="text-muted">· {delibSynth.title}</span>}
                      </span>
                    </div>
                  )}
                  {delibStatus === 'done' && delibTurns.length > 0 && (
                    <div className="rounded-md border border-good/30 bg-good/10 px-2.5 py-1.5 text-[12px] text-good" dir="auto">
                      اكتملت المداولة · التقرير أدناه مبنيّ على نقاش الوكلاء.
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="overflow-hidden rounded-lg shadow-2xl">
              <ScenarioReport data={reportData} doc={reportDoc} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
