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
import { downloadElementAsPdf } from '../../lib/pdf'
import { FileText, Download, X } from 'lucide-react'

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
  const [downloading, setDownloading] = useState(false)

  const downloadReport = useCallback(async () => {
    const el = document.getElementById('aegis-report')
    if (!el) return
    setDownloading(true)
    try {
      const stamp = new Date().toISOString().slice(0, 10)
      await downloadElementAsPdf(el, `AEGIS-Report-${stamp}.pdf`)
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

    const body = {
      text: txt,
      run_debate: runDebate,
      top_k: 6,
      location: location || undefined,
      service: service || undefined,
      solution: solution.trim() || undefined,
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
    solutionEval,
    evidence,
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
              onClick={() => setShowReport(true)}
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
          <div className="my-4" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-end gap-2">
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
                onClick={() => setShowReport(false)}
                className="flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-[13.5px] text-white transition-colors hover:bg-white/20"
              >
                <X className="h-4 w-4" />
                <span dir="auto">إغلاق</span>
              </button>
            </div>
            <div className="overflow-hidden rounded-lg shadow-2xl">
              <ScenarioReport data={reportData} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
