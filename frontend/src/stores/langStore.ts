// Language store — mirrors themeStore. Owns the active language and keeps the DOM
// (`<html dir>` + `<html lang>`), localStorage, and i18next all in sync from one place.
import { create } from 'zustand'
import i18n from '../lib/i18n'

export type Lang = 'en' | 'ar'

interface LangState {
  lang: Lang
  setLang: (l: Lang) => void
  toggle: () => void
}

function applyLang(l: Lang) {
  const el = document.documentElement
  el.setAttribute('lang', l)
  el.setAttribute('dir', l === 'ar' ? 'rtl' : 'ltr')
  localStorage.setItem('aegis-lang', l)
  if (i18n.language !== l) void i18n.changeLanguage(l)
}

const stored = (typeof localStorage !== 'undefined' ? localStorage.getItem('aegis-lang') : null) as Lang | null
const initial: Lang = stored ?? 'en'

// Apply on load so dir/lang are correct before the first interaction.
if (typeof document !== 'undefined') applyLang(initial)

export const useLangStore = create<LangState>((set) => ({
  lang: initial,
  setLang: (l) => {
    applyLang(l)
    set({ lang: l })
  },
  toggle: () =>
    set((s) => {
      const next: Lang = s.lang === 'en' ? 'ar' : 'en'
      applyLang(next)
      return { lang: next }
    }),
}))
