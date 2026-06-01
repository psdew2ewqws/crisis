import { create } from 'zustand'

export type Theme = 'dark' | 'light'

interface ThemeState {
  theme: Theme
  setTheme: (t: Theme) => void
  toggle: () => void
}

function applyTheme(t: Theme) {
  document.documentElement.setAttribute('data-theme', t)
  localStorage.setItem('aegis-theme', t)
}

const stored = (typeof localStorage !== 'undefined' ? localStorage.getItem('aegis-theme') : null) as Theme | null
const initial: Theme = stored ?? 'dark'

// Apply on load
if (typeof document !== 'undefined') applyTheme(initial)

export const useThemeStore = create<ThemeState>((set) => ({
  theme: initial,
  setTheme: (t) => {
    applyTheme(t)
    set({ theme: t })
  },
  toggle: () =>
    set((s) => {
      const next = s.theme === 'dark' ? 'light' : 'dark'
      applyTheme(next)
      return { theme: next }
    }),
}))

/* ── Chart / inline-style palette keyed by theme ── */
const palettes = {
  dark: {
    bg: '#0A0A0B',
    card: '#131417',
    cardhi: '#181A1E',
    border: '#212228',
    soft: '#1A1B20',
    txt: '#ECEDEE',
    muted: '#8B8D96',
    faint: '#62646D',
    gridStroke: '#1A1B20',
  },
  light: {
    bg: '#F4F5F7',
    card: '#FFFFFF',
    cardhi: '#F0F1F3',
    border: '#D4D6DB',
    soft: '#E8E9EC',
    txt: '#1A1B1E',
    muted: '#5F6368',
    faint: '#9AA0A6',
    gridStroke: '#E0E2E6',
  },
} as const

export function useChartColors() {
  const theme = useThemeStore((s) => s.theme)
  return palettes[theme]
}
