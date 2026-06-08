// AgentBasedSimulation — the "Agent-Based" tab. Describes a crisis, then streams
// POST /api/abm/simulate: a society of Jordan agents (citizens, services, a
// government operator with detection/decision lag + ramp, and media) is seeded
// from voc360, run once with NO intervention (the problem) and once WITH a
// data-calibrated intervention (the solution), and compared. Reuses ScenarioCharts
// for the before/after panel and EvidencePanel for scholarly references; Arabic-first.

import { useCallback, useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import {
  Play, RotateCcw, Loader2, MapPin, Wrench, Users, Building2, Megaphone,
  ShieldAlert, FlaskConical, Clock, Activity,
} from 'lucide-react'
import {
  streamAbm, getScenarioOptions,
  type AbmEvent, type AbmAgentPopulations, type AbmCalibration,
  type AbmTimelineEvent, type ScenarioOption, type ScenarioEvent, type ScenarioEvidence,
} from '../../lib/voc'
import ScenarioCharts from './ScenarioCharts'
import EvidencePanel from './EvidencePanel'

const STAGES: { key: AbmEvent['stage']; label: string }[] = [
  { key: 'seed_society', label: 'بناء المجتمع' },
  { key: 'calibrate', label: 'المعايرة' },
  { key: 'simulate_problem', label: 'محاكاة الأزمة' },
  { key: 'simulate_solution', label: 'محاكاة الحلّ' },
  { key: 'evidence', label: 'الأدلة العلمية' },
  { key: 'synthesize', label: 'الخلاصة' },
]

const CONF_AR: Record<string, string> = { high: 'مرتفعة', medium: 'متوسطة', low: 'منخفضة' }
const SRC_AR: Record<string, string> = {
  data: 'من البيانات التاريخية', dowhy: 'من البيانات + فحص سببي', prior: 'قيمة افتراضية',
}

export default function AgentBasedSimulation() {
  const [text, setText] = useState('')
  const [location, setLocation] = useState('')
  const [service, setService] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [locations, setLocations] = useState<ScenarioOption[]>([])
  const [services, setServices] = useState<ScenarioOption[]>([])
  useEffect(() => {
    getScenarioOptions()
      .then((o) => { setLocations(o.locations ?? []); setServices(o.services ?? []) })
      .catch(() => { /* dropdowns stay empty */ })
  }, [])

  // accumulated stage state
  const [done, setDone] = useState<Set<string>>(new Set())
  const [pops, setPops] = useState<AbmAgentPopulations | null>(null)
  const [engineNotes, setEngineNotes] = useState<{ mesa: boolean; langgraph: boolean; dowhy: boolean } | null>(null)
  const [calib, setCalib] = useState<AbmCalibration | null>(null)
  const [sim, setSim] = useState<AbmEvent | null>(null)
  const [timeline, setTimeline] = useState<AbmTimelineEvent[]>([])
  const [evidence, setEvidence] = useState<ScenarioEvidence[]>([])
  const [evidenceAbstained, setEvidenceAbstained] = useState(false)
  const [synthesis, setSynthesis] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setDone(new Set()); setPops(null); setEngineNotes(null); setCalib(null)
    setSim(null); setTimeline([]); setEvidence([]); setEvidenceAbstained(false)
    setSynthesis(null); setError(null)
  }, [])

  const onEvent = useCallback((e: AbmEvent) => {
    if (e.status === 'done' || e.stage === 'simulate_solution' || e.stage === 'compare') {
      setDone((d) => new Set(d).add(e.stage))
    }
    switch (e.stage) {
      case 'seed_society':
        setPops(e.agent_populations ?? null)
        setEngineNotes(e.engine_notes ?? null)
        break
      case 'calibrate':
        if (e.status === 'done') setCalib(e.calibration ?? null)
        break
      case 'simulate_solution':
        setSim(e)
        break
      case 'compare':
        setTimeline(e.intervention_timeline ?? [])
        break
      case 'evidence':
        if (e.status === 'done') {
          setEvidence(e.items ?? [])
          setEvidenceAbstained(!!e.abstained)
        }
        break
      case 'synthesize':
        if (e.status === 'done') setSynthesis(e.synthesis ?? null)
        break
      case 'error':
        setError(e.detail ?? 'تعذّرت المحاكاة')
        break
      default:
        break
    }
  }, [])

  const run = useCallback(async () => {
    const txt = text.trim()
    if (txt.length < 6) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    reset()
    setRunning(true)
    try {
      await streamAbm(
        { text: txt, location: location || undefined, service: service || undefined, steps: 50, seed: 42 },
        onEvent, controller.signal,
      )
    } catch (err) {
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        setError(err instanceof Error ? err.message : 'تعذّرت المحاكاة')
      }
    } finally {
      setRunning(false)
    }
  }, [text, location, service, onEvent, reset])

  const disabled = running || text.trim().length < 6
  const selectCls = 'w-full bg-transparent text-[13px] text-txt focus:outline-none [&>option]:bg-card [&>option]:text-txt'

  return (
    <div className="space-y-5">
      {/* intake */}
      <motion.div
        initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
        className="rounded-xl border border-border bg-card p-5"
      >
        <div className="mb-3">
          <p className="text-[12px] uppercase tracking-wide text-faint" dir="auto">محاكاة قائمة على الوكلاء · AGENT-BASED</p>
          <h2 className="text-[15px] font-semibold text-txt" dir="auto">صِف الأزمة — سيُحاكيها مجتمع من الوكلاء</h2>
        </div>
        <textarea
          dir="auto" value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !disabled) run() }}
          placeholder="مثال: نقص حادّ في المياه بالمفرق مع تصاعد الشكاوى وتباطؤ الاستجابة"
          className="min-h-[110px] w-full resize-y rounded-lg border border-border bg-bg px-3.5 py-3 text-[14px] leading-relaxed text-txt placeholder:text-faint focus:border-blue focus:outline-none"
        />
        <div className="mt-3 flex flex-wrap items-center gap-2.5">
          <label className="flex min-w-[160px] flex-1 items-center gap-2 rounded-lg border border-border bg-bg px-3 py-2 focus-within:border-blue">
            <MapPin className="h-4 w-4 shrink-0 text-faint" />
            <select dir="auto" value={location} onChange={(e) => setLocation(e.target.value)} className={selectCls}>
              <option value="">الموقع — كل المحافظات</option>
              {locations.map((o) => <option key={o.value} value={o.value}>{o.value} · {o.count}</option>)}
            </select>
          </label>
          <label className="flex min-w-[160px] flex-1 items-center gap-2 rounded-lg border border-border bg-bg px-3 py-2 focus-within:border-blue">
            <Wrench className="h-4 w-4 shrink-0 text-faint" />
            <select dir="auto" value={service} onChange={(e) => setService(e.target.value)} className={selectCls}>
              <option value="">الخدمة — كل الخدمات</option>
              {services.map((o) => <option key={o.value} value={o.value}>{o.value} · {o.count}</option>)}
            </select>
          </label>
          <div className="flex items-center gap-2.5">
            <button type="button" onClick={reset} disabled={running}
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-3.5 py-2.5 text-[13.5px] font-medium text-muted transition-colors hover:bg-cardhi hover:text-txt disabled:opacity-50">
              <RotateCcw className="h-4 w-4" /><span dir="auto">إعادة</span>
            </button>
            <button type="button" onClick={run} disabled={disabled}
              className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-60">
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              <span dir="auto">{running ? 'جارٍ المحاكاة…' : 'تشغيل'}</span>
            </button>
          </div>
        </div>
      </motion.div>

      {error && (
        <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-[13px] text-danger" dir="auto">{error}</div>
      )}

      {/* stage stepper */}
      {(running || done.size > 0) && (
        <div className="flex flex-wrap items-center gap-2">
          {STAGES.map((s) => {
            const isDone = done.has(s.key)
            return (
              <span key={s.key}
                className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                  isDone ? 'border-good/40 bg-good/10 text-good'
                    : running ? 'border-blue/40 bg-blue/10 text-blue'
                    : 'border-border text-faint'
                }`}>
                {isDone ? <Activity className="h-3 w-3" /> : <Loader2 className={`h-3 w-3 ${running ? 'animate-spin' : ''}`} />}
                <span dir="auto">{s.label}</span>
              </span>
            )
          })}
        </div>
      )}

      {/* agent society */}
      {pops && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border bg-card p-5">
          <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
            <Users className="h-3.5 w-3.5" /> مجتمع الوكلاء
            {engineNotes && (
              <span className="ms-auto flex items-center gap-1.5 normal-case tracking-normal text-faint">
                <span className={`rounded px-1.5 py-0.5 ${engineNotes.mesa ? 'bg-good/10 text-good' : 'bg-soft'}`}>Mesa {engineNotes.mesa ? 'on' : 'fallback'}</span>
                <span className={`rounded px-1.5 py-0.5 ${engineNotes.dowhy ? 'bg-good/10 text-good' : 'bg-soft'}`}>DoWhy {engineNotes.dowhy ? 'on' : 'off'}</span>
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { icon: Users, label: 'مواطنون (تجمّعات)', value: pops.citizens, sub: `${pops.citizen_pop_total.toLocaleString('en-US')} إشارة` },
              { icon: Building2, label: 'خدمات', value: pops.services, sub: 'وكلاء خدمة' },
              { icon: ShieldAlert, label: 'جهة مشغّلة', value: pops.operators, sub: 'حكومة/تدخّل' },
              { icon: Megaphone, label: 'إعلام', value: pops.media, sub: 'تضخيم' },
            ].map((c) => (
              <div key={c.label} className="rounded-lg border border-border/60 bg-soft/40 px-3 py-2.5">
                <div className="flex items-center gap-1.5 text-[11px] text-faint" dir="auto"><c.icon className="h-3.5 w-3.5" />{c.label}</div>
                <div className="mt-1 font-mono text-[20px] font-semibold text-txt">{c.value}</div>
                <div className="text-[10px] text-faint" dir="auto">{c.sub}</div>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* calibration badge */}
      {calib && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border bg-card p-5">
          <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
            <FlaskConical className="h-3.5 w-3.5" /> معايرة التدخّل
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="rounded-lg border border-blue/30 bg-blue/10 px-3 py-1.5 text-[13px] font-semibold text-blue">
              حجم الأثر {Math.round(calib.effect_size * 100)}٪
            </span>
            <span className="rounded-lg border border-border bg-soft px-2.5 py-1.5 text-[12px] text-muted" dir="auto">
              ثقة {CONF_AR[calib.confidence] ?? calib.confidence}
            </span>
            <span className="rounded-lg border border-border bg-soft px-2.5 py-1.5 text-[12px] text-muted" dir="auto">
              {SRC_AR[calib.source] ?? calib.source}
            </span>
            {calib.refutation?.available && (
              <span className={`rounded-lg px-2.5 py-1.5 text-[12px] ${calib.refutation.robust ? 'bg-good/10 text-good' : 'bg-warn/10 text-warn'}`} dir="auto">
                {calib.refutation.robust ? 'متين سببيًّا' : 'غير متين'}
              </span>
            )}
          </div>
          <p className="mt-2 text-[12px] leading-relaxed text-muted" dir="rtl">{calib.notes_ar}</p>
        </motion.div>
      )}

      {/* intervention timeline */}
      {timeline.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border bg-card p-5">
          <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
            <Clock className="h-3.5 w-3.5" /> توقيت التدخّل (تأخّر واقعي)
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {timeline.map((t, i) => (
              <span key={i} className="flex items-center gap-1.5 rounded-full border border-border bg-soft/50 px-2.5 py-1 text-[11px] text-txt">
                <span className="font-mono text-faint">t={t.tick}</span>
                <span dir="auto">
                  {t.event === 'detected' ? 'اكتشاف الأزمة'
                    : t.event === 'intervene' ? 'قرار التدخّل'
                    : t.event === 'ramp_full' ? 'بلوغ الأثر الكامل' : t.event}
                </span>
              </span>
            ))}
          </div>
        </motion.div>
      )}

      {/* before/after charts — reuse ScenarioCharts (problem vs solution) */}
      {sim && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border bg-card p-5">
          <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-txt" dir="auto">
            <Activity className="h-4 w-4 text-blue" /> الأزمة (دون تدخّل) مقابل الحلّ (تدخّل مُعاير)
          </div>
          <ScenarioCharts sim={sim as unknown as ScenarioEvent} />
        </motion.div>
      )}

      {/* scholarly evidence (OpenAlex open-access — same papers as Sci-Hub, legal route) */}
      {(evidence.length > 0 || evidenceAbstained) && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
          <EvidencePanel items={evidence} abstained={evidenceAbstained} />
        </motion.div>
      )}

      {/* synthesis */}
      {synthesis && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-blue/30 bg-blue/5 p-5">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-blue">الخلاصة</div>
          <p className="text-[14px] leading-relaxed text-txt" dir="rtl">{synthesis}</p>
        </motion.div>
      )}
    </div>
  )
}
