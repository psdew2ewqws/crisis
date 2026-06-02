import { Languages } from 'lucide-react'
import { useT, useLocaleStore } from '../lib/i18n'

// Always-visible floating control to flip the whole console between Arabic
// (default, RTL) and English (LTR). Pinned to the bottom corner on the side
// nearest the reading direction's start so it never sits under the sidebar.
export default function LangToggle() {
  const { locale, t } = useT()
  const toggle = useLocaleStore((s) => s.toggle)
  const next = locale === 'ar' ? 'English' : 'العربية'

  return (
    <button
      onClick={toggle}
      title={locale === 'ar' ? t('Switch to English') : t('Switch to Arabic')}
      aria-label={locale === 'ar' ? t('Switch to English') : t('Switch to Arabic')}
      className="fixed bottom-5 left-5 z-[70] flex items-center gap-2 rounded-full border border-border bg-card/90 px-3.5 py-2 text-[13px] font-semibold text-txt shadow-lg shadow-black/20 backdrop-blur transition-all hover:border-blue/60 hover:bg-cardhi active:scale-95"
    >
      <Languages className="h-4 w-4 text-blue" />
      <span>{next}</span>
    </button>
  )
}
