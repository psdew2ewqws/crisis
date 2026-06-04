import { motion } from 'motion/react'
import {
  ShieldAlert,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowRight,
  Sparkles,
  Ban,
  Gauge,
  ClipboardCheck,
} from 'lucide-react'
import type {
  ScenarioDetection,
  ScenarioPrediction,
  ScenarioConfidence,
} from '../../lib/voc'

interface VerdictPanelProps {
  detection: ScenarioDetection
  prediction: ScenarioPrediction
  confidence: ScenarioConfidence
  flagsAr: string[]
}

// severity → tone token set
const SEVERITY_TONE: Record<
  ScenarioDetection['severity'],
  { wrap: string; text: string }
> = {
  low: { wrap: 'border-border bg-soft', text: 'text-muted' },
  elevated: { wrap: 'border-warn/30 bg-warn/10', text: 'text-warn' },
  critical: { wrap: 'border-danger/30 bg-danger/10', text: 'text-danger' },
}

// confidence band → tone
const BAND_TONE: Record<ScenarioConfidence['band'], string> = {
  high: 'text-good',
  medium: 'text-warn',
  low: 'text-muted',
}

const fmtPct = (v: number) => `${(v * 100).toFixed(1)}%`
const fmtNum = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1))

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="text-[12px] uppercase tracking-wide text-faint">{children}</span>
  )
}

function Chip({
  tone,
  children,
}: {
  tone: 'good' | 'warn' | 'danger' | 'blue' | 'neutral'
  children: React.ReactNode
}) {
  const map: Record<typeof tone, string> = {
    good: 'border-good/30 bg-good/10 text-good',
    warn: 'border-warn/30 bg-warn/10 text-warn',
    danger: 'border-danger/30 bg-danger/10 text-danger',
    blue: 'border-blue/30 bg-blue/10 text-blue',
    neutral: 'border-border bg-soft text-muted',
  }
  return (
    <span
      dir="auto"
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] font-medium ${map[tone]}`}
    >
      {children}
    </span>
  )
}

// thin labeled progress bar for confidence breakdown (width = 0..1)
function MeterBar({
  label,
  value,
  pct,
}: {
  label: string
  value: number
  pct: boolean
}) {
  const clamped = Math.max(0, Math.min(1, value))
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-[12px] text-muted" dir="auto">{label}</span>
        <span className="tnum text-[12px] text-faint">
          {pct ? fmtPct(clamped) : fmtNum(value)}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-soft">
        <div
          className="h-full rounded-full bg-blue transition-[width]"
          style={{ width: `${clamped * 100}%` }}
        />
      </div>
    </div>
  )
}

export default function VerdictPanel({
  detection,
  prediction,
  confidence,
  flagsAr,
}: VerdictPanelProps) {
  const sevTone = SEVERITY_TONE[detection.severity]
  const worked = prediction.which_intervention_worked
  const traj = prediction.risk_trajectory
  const b = confidence.breakdown

  const hasTrajectory =
    traj.risk_before != null || traj.risk_after != null || traj.risk_reduction != null

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl border border-border bg-card p-5"
    >
      {/* ───────────────────────── 1. DETECTION ───────────────────────── */}
      <section>
        <div className="mb-3 flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-faint" />
          <Eyebrow>التشخيص · Detection</Eyebrow>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* large severity badge */}
          <div
            dir="auto"
            className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-[18px] font-semibold ${sevTone.wrap} ${sevTone.text}`}
          >
            <Gauge className="h-4 w-4" />
            {detection.severity_ar}
          </div>

          {/* crisis yes/no */}
          {detection.is_crisis ? (
            <Chip tone="danger">
              <AlertTriangle className="h-3.5 w-3.5" />
              أزمة قائمة
            </Chip>
          ) : (
            <Chip tone="good">لا توجد أزمة</Chip>
          )}

          {/* escalation indicator */}
          {detection.escalating ? (
            <Chip tone="danger">
              <TrendingUp className="h-3.5 w-3.5" />
              تصاعد
            </Chip>
          ) : (
            <Chip tone="good">
              <TrendingDown className="h-3.5 w-3.5" />
              استقرار
            </Chip>
          )}
        </div>

        {detection.escalation_source && (
          <p dir="auto" className="mt-2 text-[12px] text-faint">
            المصدر:{' '}
            {detection.escalation_source === 'simulation'
              ? 'محاكاة'
              : detection.escalation_source === 'forecast'
                ? 'تنبؤ'
                : detection.escalation_source}
          </p>
        )}
      </section>

      <div className="my-5 h-px bg-border" />

      {/* ──────────────────────── 2. PREDICTION ───────────────────────── */}
      <section>
        <div className="mb-3 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-faint" />
          <Eyebrow>التنبؤ · Prediction</Eyebrow>
        </div>

        {/* likely outcome chip */}
        {prediction.likely_outcome_ar && (
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span className="text-[13px] text-muted" dir="auto">النتيجة المرجّحة:</span>
            <Chip tone="blue">
              <span dir="auto">{prediction.likely_outcome_ar}</span>
            </Chip>
          </div>
        )}

        {/* most-effective intervention sub-card */}
        <div className="rounded-lg border border-good/30 bg-good/5 p-4">
          <div className="mb-2 text-[13px] font-semibold text-good" dir="auto">
            التدخّل الأنجع تاريخيًّا
          </div>

          {worked ? (
            <>
              <p dir="auto" className="text-[14px] leading-relaxed text-txt">
                {worked.intervention}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Chip tone="good">
                  <TrendingDown className="h-3.5 w-3.5" />
                  <span className="tnum">
                    −{fmtNum(worked.risk_reduction)}
                  </span>{' '}
                  نقطة خطر
                </Chip>
                {worked.risk_source_ar && (
                  <Chip tone="neutral">
                    <span dir="auto">{worked.risk_source_ar}</span>
                  </Chip>
                )}
              </div>
              {(worked.source_case_id || worked.ts) && (
                <p dir="auto" className="mt-2 text-[12px] text-faint">
                  {worked.source_case_id && <span>المصدر: {worked.source_case_id}</span>}
                  {worked.source_case_id && worked.ts && <span> · </span>}
                  {worked.ts && <span className="tnum">{worked.ts}</span>}
                </p>
              )}
            </>
          ) : (
            <p dir="auto" className="text-[13px] text-faint">
              لا يوجد تدخّل ناجح موثّق بعد
            </p>
          )}
        </div>

        {/* risk trajectory */}
        {hasTrajectory && (
          <div className="mt-4">
            <div className="mb-1.5 text-[12px] text-muted" dir="auto">مسار الخطر</div>
            <div className="flex flex-wrap items-center gap-2 text-[15px] font-semibold text-txt">
              <span className="tnum">
                {traj.risk_before != null ? fmtNum(traj.risk_before) : '—'}
              </span>
              <ArrowRight className="h-4 w-4 text-faint" />
              <span className="tnum">
                {traj.risk_after != null ? fmtNum(traj.risk_after) : '—'}
              </span>
              {traj.risk_reduction != null && (
                <Chip tone="good">
                  <Minus className="h-3.5 w-3.5" />
                  <span className="tnum">{fmtNum(traj.risk_reduction)}</span> نقطة
                </Chip>
              )}
              {traj.risk_source_ar && (
                <Chip tone="neutral">
                  <span dir="auto">{traj.risk_source_ar}</span>
                </Chip>
              )}
            </div>
          </div>
        )}

        {/* avoid anti-patterns */}
        {prediction.avoid.length > 0 && (
          <div className="mt-4">
            <div className="mb-2 text-[12px] text-muted" dir="auto">تجنّب</div>
            <ul className="space-y-1.5">
              {prediction.avoid.map((a, i) => (
                <li
                  key={a.source_case_id ? `${a.source_case_id}-${i}` : i}
                  dir="auto"
                  className="flex items-start gap-2 rounded-lg border border-warn/30 bg-warn/10 px-3 py-2 text-[13px] text-warn"
                >
                  <Ban className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{a.warning}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <div className="my-5 h-px bg-border" />

      {/* ──────────────────────── 3. CONFIDENCE ───────────────────────── */}
      <section>
        <div className="mb-3 flex items-center gap-2">
          <ClipboardCheck className="h-4 w-4 text-faint" />
          <Eyebrow>الثقة · Confidence</Eyebrow>
        </div>

        <div
          dir="auto"
          className={`mb-4 text-[20px] font-semibold ${BAND_TONE[confidence.band]}`}
        >
          {confidence.band_ar}{' '}
          <span className="tnum text-[15px] font-medium text-faint">
            ({confidence.score.toFixed(1)})
          </span>
        </div>

        <div className="space-y-3">
          <MeterBar label="متوسط الصِلة" value={b.mean_relevance} pct />
          <MeterBar label="توافق النتائج" value={b.outcome_agreement} pct />
          <MeterBar label="عامل التحقّق" value={b.validation_factor} pct />
        </div>

        <p className="mt-4 text-[13px] text-muted" dir="auto">
          السوابق:{' '}
          <span className="tnum font-semibold text-txt">{b.distinct_precedents}</span>
        </p>
      </section>

      {/* ───────────────────────── flags / notes ──────────────────────── */}
      {flagsAr.length > 0 && (
        <div className="mt-5 border-t border-border pt-4">
          <div className="mb-2 text-[12px] text-muted" dir="auto">ملاحظات:</div>
          <div className="flex flex-wrap gap-2">
            {flagsAr.map((f, i) => (
              <span
                key={i}
                dir="auto"
                className="inline-flex items-center gap-1.5 rounded-full border border-warn/30 bg-warn/10 px-2.5 py-1 text-[12px] font-medium text-warn"
              >
                <AlertTriangle className="h-3.5 w-3.5" />
                {f}
              </span>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  )
}
