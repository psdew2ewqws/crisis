// Guided spotlight tour for first-time operators. Each step points at a real element
// tagged with `data-tour="<id>"` elsewhere in the chrome; we read its bounding box,
// dim everything else with a single big box-shadow "hole", and float a tooltip beside
// it. Skippable and replayable (App opens it from the welcome card or the Help drawer).
// Pure client-side — no backend, no data.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X, ArrowLeft, ArrowRight, Check } from 'lucide-react'

interface Step {
  id: string
  n: number
  place: 'right' | 'bottom' | 'left' | 'top'
}

// Workflow-aligned tour. `id` matches a data-tour anchor in the chrome; `n` keys the
// localized title/body (tour.step{n}.title / .text).
const STEPS: Step[] = [
  { id: 'nav', n: 1, place: 'right' },
  { id: 'signals', n: 2, place: 'right' },
  { id: 'run', n: 3, place: 'right' },
  { id: 'rootcause', n: 4, place: 'right' },
  { id: 'deepanalysis', n: 5, place: 'right' },
  { id: 'decisions', n: 6, place: 'right' },
]

interface Rect {
  top: number
  left: number
  width: number
  height: number
}

const PAD = 6
const TIP_W = 320

function tipPosition(r: Rect, rawPlace: Step['place']) {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const gap = 14
  // In RTL the chrome (sidebar) sits on the right, so flip horizontal placements.
  const rtl = typeof document !== 'undefined' && document.documentElement.dir === 'rtl'
  const place = rtl && rawPlace === 'right' ? 'left' : rtl && rawPlace === 'left' ? 'right' : rawPlace
  let top: number
  let left: number
  if (place === 'right') {
    left = r.left + r.width + gap
    top = r.top
  } else if (place === 'left') {
    left = r.left - TIP_W - gap
    top = r.top
  } else if (place === 'top') {
    left = r.left
    top = r.top - gap - 170
  } else {
    left = r.left
    top = r.top + r.height + gap
  }
  // clamp into the viewport with a small margin
  left = Math.max(12, Math.min(left, vw - TIP_W - 12))
  top = Math.max(12, Math.min(top, vh - 180))
  return { top, left }
}

export default function Tour({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const [i, setI] = useState(0)
  const [rect, setRect] = useState<Rect | null>(null)
  const rafRef = useRef<number | null>(null)

  const step = STEPS[i]

  const measure = useCallback(() => {
    const el = document.querySelector<HTMLElement>(`[data-tour="${STEPS[i].id}"]`)
    if (!el) {
      setRect(null)
      return
    }
    const b = el.getBoundingClientRect()
    setRect({ top: b.top, left: b.left, width: b.width, height: b.height })
  }, [i])

  // reset to first step every time the tour is (re)opened
  useEffect(() => {
    if (open) setI(0)
  }, [open])

  useLayoutEffect(() => {
    if (!open) return
    measure()
    const onChange = () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      rafRef.current = requestAnimationFrame(measure)
    }
    window.addEventListener('resize', onChange)
    window.addEventListener('scroll', onChange, true)
    return () => {
      window.removeEventListener('resize', onChange)
      window.removeEventListener('scroll', onChange, true)
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [open, measure])

  // keyboard: Esc closes, arrows navigate
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowRight') setI((v) => Math.min(v + 1, STEPS.length - 1))
      else if (e.key === 'ArrowLeft') setI((v) => Math.max(v - 1, 0))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const last = i === STEPS.length - 1
  const next = () => (last ? onClose() : setI((v) => v + 1))
  const back = () => setI((v) => Math.max(v - 1, 0))

  const tip = rect ? tipPosition(rect, step.place) : { top: window.innerHeight / 2 - 90, left: window.innerWidth / 2 - TIP_W / 2 }

  return (
    <div className="fixed inset-0 z-[80]" role="dialog" aria-modal="true" aria-label="Product tour">
      {/* click-catcher: blocks interaction with the app behind the tour */}
      <div className="absolute inset-0" onClick={onClose} />

      {/* spotlight hole over the current target (dims everything else) */}
      {rect && (
        <div
          className="pointer-events-none absolute rounded-xl"
          style={{
            top: rect.top - PAD,
            left: rect.left - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
            boxShadow: '0 0 0 9999px rgba(0,0,0,0.62)',
            outline: '2px solid #3b82f6',
            transition: 'top .25s ease, left .25s ease, width .25s ease, height .25s ease',
          }}
        />
      )}

      {/* tooltip */}
      <div
        className="absolute rounded-xl border border-border bg-card p-4 shadow-2xl"
        style={{ top: tip.top, left: tip.left, width: TIP_W, transition: 'top .25s ease, left .25s ease' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-[14.5px] font-semibold text-txt">{t(`tour.step${step.n}.title`)}</h3>
          <button
            onClick={onClose}
            aria-label={t('general.close')}
            className="-mr-1 -mt-1 rounded-lg p-1 text-muted transition-colors hover:bg-soft hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{t(`tour.step${step.n}.text`)}</p>

        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            {STEPS.map((s, idx) => (
              <span
                key={s.id}
                className={`h-1.5 rounded-full transition-all ${idx === i ? 'w-4 bg-blue' : 'w-1.5 bg-border'}`}
              />
            ))}
          </div>
          <div className="flex items-center gap-1.5">
            {i > 0 && (
              <button
                onClick={back}
                className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[12.5px] text-muted transition-colors hover:bg-soft hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
              >
                <ArrowLeft className="h-3.5 w-3.5 rtl:rotate-180" />
                {t('general.back')}
              </button>
            )}
            <button
              onClick={next}
              className="flex items-center gap-1.5 rounded-lg bg-blue px-3 py-1.5 text-[12.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
            >
              {last ? (
                <>
                  <Check className="h-3.5 w-3.5" />
                  {t('general.done')}
                </>
              ) : (
                <>
                  {t('general.next')}
                  <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
