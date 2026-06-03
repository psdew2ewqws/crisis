// i18next setup. Resources are bundled inline (no async loading) so the first paint
// already has translations. The active language is read from localStorage so it
// survives reloads; langStore drives changes at runtime.
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from '../locales/en'
import ar from '../locales/ar'

const stored = (typeof localStorage !== 'undefined' ? localStorage.getItem('aegis-lang') : null) as
  | 'en'
  | 'ar'
  | null

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ar: { translation: ar },
  },
  lng: stored ?? 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export default i18n
