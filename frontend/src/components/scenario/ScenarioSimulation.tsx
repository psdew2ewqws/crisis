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

import { useCallback, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { AlertTriangle, Info, Sparkles } from 'lucide-react'
import {
  streamScenario,
  type ScenarioEvent,
  type ScenarioCitation,
  type ScenarioAgent,
} from '../../lib/voc'
import ScenarioInput from './ScenarioInput'
import ScenarioStepper, { type StageKey } from './ScenarioStepper'
import PrecedentCards from './PrecedentCards'
import AgentRoster from './AgentRoster'
import ScenarioCharts from './ScenarioCharts'
import VerdictPanel from './VerdictPanel'
import DebateStream, { type DebateTurn } from './DebateStream'

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
  const [runDebate, setRunDebate] = useState(false)
  const [running, setRunning] = useState(false)

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
      case 'done':
        setRunning(false)
        setDoneEngine(e.engine ?? null)
        setCurrent(null)
        break
      default:
        break
    }
  }, [])

  const onRun = useCallback(async () => {
    // Abort any in-flight run before starting a fresh one.
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    resetState()
    startedRef.current = true
    setRunning(true)
    setCurrent('parse')

    const hint = service.trim()
    const body = {
      text,
      run_debate: runDebate,
      top_k: 6,
      case_hint: hint ? `service:${hint}` : undefined,
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
  }, [text, service, runDebate, onEvent, resetState])

  const onReset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    startedRef.current = false
    setRunning(false)
    resetState()
  }, [resetState])

  const warnings = parse?.warnings ?? []
  const started = startedRef.current

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

        {/* Idle hint — before the first run */}
        {!started && (
          <div className="mt-12 flex flex-col items-center justify-center gap-2 text-faint">
            <Sparkles className="h-6 w-6" />
            <span className="text-[13.5px]" dir="auto">
              صِف أزمة جديدة ثم شغّل المحاكاة لاسترجاع السوابق والكشف والتنبؤ
            </span>
          </div>
        )}

        {/* Pipeline progress */}
        {started && (
          <div className="mt-6">
            <ScenarioStepper done={doneStages} current={current} />
          </div>
        )}

        {/* Retrieved precedents */}
        {retrieved && (
          <div className="mt-6">
            <PrecedentCards cases={cases} bestRelevance={bestRelevance} />
          </div>
        )}

        {/* Selected agents */}
        {agents.length > 0 && (
          <div className="mt-6">
            <AgentRoster agents={agents} engine={selectEngine} />
          </div>
        )}

        {/* Simulation charts */}
        {sim && (
          <div className="mt-6">
            <ScenarioCharts sim={sim} />
          </div>
        )}

        {/* Verdict — detection + prediction + confidence */}
        {verdict && verdict.detection && verdict.prediction && verdict.confidence && (
          <div className="mt-6">
            <VerdictPanel
              detection={verdict.detection}
              prediction={verdict.prediction}
              confidence={verdict.confidence}
              flagsAr={flagsAr}
            />
          </div>
        )}

        {/* Agent debate */}
        {debateTurns.length > 0 && (
          <div className="mt-6">
            <DebateStream turns={debateTurns} />
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
    </div>
  )
}
