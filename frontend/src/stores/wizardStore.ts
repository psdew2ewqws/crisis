import { create } from 'zustand'

export type WizardStep = 1 | 2 | 3 | 4 | 5 | 6 | 7
export type WizardMode = 'tour' | 'live'

export const WIZARD_STEPS = [
  { step: 1 as const, label: 'Signals', route: '/signals', icon: 'Radio' },
  { step: 2 as const, label: 'Incident', route: '/case/:id/graph', icon: 'GitBranch' },
  { step: 3 as const, label: 'Root Cause', route: '/case/:id/root-cause', icon: 'Target' },
  { step: 4 as const, label: 'Solutions', route: '/case/:id/solutions', icon: 'Lightbulb' },
  { step: 5 as const, label: 'Validate', route: '/case/:id/sim', icon: 'FlaskConical' },
  { step: 6 as const, label: 'DECIDE', route: '/case/:id/decide', icon: 'ShieldCheck' },
  { step: 7 as const, label: 'Outcome', route: '/case/:id/outcome', icon: 'TrendingDown' },
] as const

export function stepRoute(step: WizardStep, caseId: string): string {
  const cfg = WIZARD_STEPS[step - 1]
  return cfg.route.replace(':id', caseId)
}

/** Match a pathname to a wizard step (or null) */
export function pathToStep(pathname: string): WizardStep | null {
  if (pathname === '/signals') return 1
  if (pathname.includes('/graph')) return 2
  if (pathname.includes('/root-cause')) return 3
  if (pathname.includes('/solutions')) return 4
  if (pathname.includes('/sim')) return 5
  if (pathname.includes('/decide')) return 6
  if (pathname.includes('/outcome')) return 7
  return null
}

interface WizardState {
  open: boolean
  minimized: boolean
  step: WizardStep
  mode: WizardMode
  caseId: string

  completedSteps: Set<WizardStep>
  highestReached: WizardStep

  guards: Record<WizardStep, boolean>

  setOpen: (open: boolean) => void
  setMinimized: (min: boolean) => void
  setStep: (step: WizardStep) => void
  completeStep: (step: WizardStep) => void
  setGuard: (step: WizardStep, passed: boolean) => void
  startTour: () => void
  startLive: (caseId: string) => void
  reset: () => void
}

export const useWizardStore = create<WizardState>((set) => ({
  open: false,
  minimized: false,
  step: 1,
  mode: 'tour',
  caseId: 'zarqa-2025-08',

  completedSteps: new Set<WizardStep>(),
  highestReached: 1,

  guards: { 1: false, 2: false, 3: false, 4: false, 5: false, 6: false, 7: false },

  setOpen: (open) => set({ open }),
  setMinimized: (min) => set({ minimized: min }),
  setStep: (step) =>
    set((s) => ({
      step,
      highestReached: Math.max(s.highestReached, step) as WizardStep,
    })),
  completeStep: (step) =>
    set((s) => {
      const next = new Set(s.completedSteps)
      next.add(step)
      return { completedSteps: next }
    }),
  setGuard: (step, passed) =>
    set((s) => ({ guards: { ...s.guards, [step]: passed } })),

  startTour: () =>
    set({
      open: true,
      minimized: false,
      step: 1,
      mode: 'tour',
      caseId: 'zarqa-2025-08',
      completedSteps: new Set<WizardStep>(),
      highestReached: 1,
      // Pre-set guards 1-3 for tour (fixture data satisfies them)
      guards: { 1: true, 2: true, 3: true, 4: false, 5: false, 6: false, 7: true },
    }),

  startLive: (caseId) =>
    set({
      open: true,
      minimized: false,
      step: 1,
      mode: 'live',
      caseId,
      completedSteps: new Set<WizardStep>(),
      highestReached: 1,
      guards: { 1: false, 2: false, 3: false, 4: false, 5: false, 6: false, 7: false },
    }),

  reset: () =>
    set({
      open: false,
      minimized: false,
      step: 1,
      completedSteps: new Set<WizardStep>(),
      highestReached: 1,
      guards: { 1: false, 2: false, 3: false, 4: false, 5: false, 6: false, 7: false },
    }),
}))
