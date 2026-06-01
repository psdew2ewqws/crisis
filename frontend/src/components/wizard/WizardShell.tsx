import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { AnimatePresence } from 'motion/react'
import { useWizardStore, pathToStep, type WizardStep } from '../../stores/wizardStore'
import ProgressRail from './ProgressRail'
import StepFooter from './StepFooter'
import MiniTracker from './MiniTracker'

export default function WizardShell() {
  const { open, minimized, setStep, setMinimized, completeStep } = useWizardStore()
  const location = useLocation()

  // Sync wizard step when user navigates via sidebar or page buttons
  useEffect(() => {
    if (!open) return
    const matched = pathToStep(location.pathname)
    if (matched) {
      const currentStep = useWizardStore.getState().step
      // Auto-complete all steps before the matched step
      // (user navigated forward via page buttons, not wizard footer)
      if (matched > currentStep) {
        for (let s = currentStep; s < matched; s++) {
          completeStep(s as WizardStep)
        }
      }
      setStep(matched)
    } else {
      // User navigated to a non-wizard page (e.g. Dashboard) — minimize
      if (!minimized) setMinimized(true)
    }
  }, [location.pathname, open])

  // Keyboard: Esc toggles minimized
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        setMinimized(!useWizardStore.getState().minimized)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open])

  if (!open) return null

  return (
    <AnimatePresence>
      {minimized ? (
        <MiniTracker />
      ) : (
        <>
          <ProgressRail />
          <StepFooter />
        </>
      )}
    </AnimatePresence>
  )
}
