import { create } from 'zustand'

interface AppState {
  running: boolean
  setRunning: (running: boolean) => void

  activeCaseId: string
  setActiveCaseId: (id: string) => void

  wizardOpen: boolean
  wizardStep: number
  setWizardOpen: (open: boolean) => void
  setWizardStep: (step: number) => void

  // Cross-page linking
  highlightedNodeId: string | null
  setHighlightedNodeId: (id: string | null) => void
  highlightedSignalId: string | null
  setHighlightedSignalId: (id: string | null) => void
}

export const useAppStore = create<AppState>((set) => ({
  running: false,
  setRunning: (running) => set({ running }),

  activeCaseId: 'zarqa-2025-08',
  setActiveCaseId: (id) => set({ activeCaseId: id }),

  wizardOpen: false,
  wizardStep: 1,
  setWizardOpen: (open) => set({ wizardOpen: open }),
  setWizardStep: (step) => set({ wizardStep: step }),

  highlightedNodeId: null,
  setHighlightedNodeId: (id) => set({ highlightedNodeId: id }),
  highlightedSignalId: null,
  setHighlightedSignalId: (id) => set({ highlightedSignalId: id }),
}))
