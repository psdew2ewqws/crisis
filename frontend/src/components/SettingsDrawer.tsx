import { X, Moon, Sun, Bell, Key, Shield, Languages } from 'lucide-react'
import { motion } from 'motion/react'
import { useThemeStore } from '../stores/themeStore'
import { useT, useLocaleStore } from '../lib/i18n'

interface Props {
  open: boolean
  onClose: () => void
}

export default function SettingsDrawer({ open, onClose }: Props) {
  const { theme, toggle } = useThemeStore()
  const { t, locale } = useT()
  const toggleLocale = useLocaleStore((s) => s.toggle)

  if (!open) return null

  return (
    <>
      {/* backdrop */}
      <div className="fixed inset-0 z-40 bg-black/40" onClick={onClose} />

      {/* drawer */}
      <motion.aside
        initial={{ x: -320, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: -320, opacity: 0 }}
        transition={{ type: 'spring', damping: 28, stiffness: 300 }}
        className="fixed start-[248px] top-0 z-50 flex h-full w-[340px] flex-col border-e border-border bg-card shadow-xl"
      >
        {/* header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-[16px] font-semibold text-txt">{t('Settings')}</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted hover:bg-cardhi hover:text-txt"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Appearance */}
          <section>
            <h3 className="text-[11px] font-semibold tracking-[0.14em] text-faint mb-3">{t('APPEARANCE')}</h3>
            <button
              onClick={toggle}
              className="flex w-full items-center justify-between rounded-lg border border-border bg-bg px-4 py-3 transition-colors hover:bg-cardhi"
            >
              <div className="flex items-center gap-3">
                {theme === 'dark' ? (
                  <Moon className="h-[18px] w-[18px] text-blue" />
                ) : (
                  <Sun className="h-[18px] w-[18px] text-warn" />
                )}
                <div className="text-start">
                  <div className="text-[13.5px] font-medium text-txt">
                    {theme === 'dark' ? t('Dark Mode') : t('Light Mode')}
                  </div>
                  <div className="text-[11px] text-faint">
                    {theme === 'dark' ? t('Switch to light theme') : t('Switch to dark theme')}
                  </div>
                </div>
              </div>
              <div
                className={`relative h-6 w-11 rounded-full transition-colors ${
                  theme === 'dark' ? 'bg-blue' : 'bg-muted'
                }`}
              >
                <div
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                    theme === 'dark' ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </div>
            </button>

            {/* Language */}
            <button
              onClick={toggleLocale}
              className="mt-2 flex w-full items-center justify-between rounded-lg border border-border bg-bg px-4 py-3 transition-colors hover:bg-cardhi"
            >
              <div className="flex items-center gap-3">
                <Languages className="h-[18px] w-[18px] text-blue" />
                <div className="text-start">
                  <div className="text-[13.5px] font-medium text-txt">{t('Language')}</div>
                  <div className="text-[11px] text-faint">{t('Switch interface language')}</div>
                </div>
              </div>
              <span className="rounded-md border border-border bg-cardhi px-2.5 py-1 font-mono text-[12px] font-medium text-muted">
                {locale === 'ar' ? 'العربية' : 'English'}
              </span>
            </button>
          </section>

          {/* Notifications (placeholder) */}
          <section>
            <h3 className="text-[11px] font-semibold tracking-[0.14em] text-faint mb-3">{t('NOTIFICATIONS')}</h3>
            <div className="flex items-center gap-3 rounded-lg border border-border bg-bg px-4 py-3">
              <Bell className="h-[18px] w-[18px] text-muted" />
              <div>
                <div className="text-[13.5px] font-medium text-txt">{t('Push Notifications')}</div>
                <div className="text-[11px] text-faint">{t('Coming soon')}</div>
              </div>
            </div>
          </section>

          {/* Security (placeholder) */}
          <section>
            <h3 className="text-[11px] font-semibold tracking-[0.14em] text-faint mb-3">{t('SECURITY')}</h3>
            <div className="space-y-2">
              <div className="flex items-center gap-3 rounded-lg border border-border bg-bg px-4 py-3">
                <Key className="h-[18px] w-[18px] text-muted" />
                <div>
                  <div className="text-[13.5px] font-medium text-txt">{t('API Keys')}</div>
                  <div className="text-[11px] text-faint">{t('Manage integrations')}</div>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border border-border bg-bg px-4 py-3">
                <Shield className="h-[18px] w-[18px] text-muted" />
                <div>
                  <div className="text-[13.5px] font-medium text-txt">{t('RBAC Policies')}</div>
                  <div className="text-[11px] text-faint">{t('Role-based access control')}</div>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* footer */}
        <div className="border-t border-border px-5 py-3">
          <div className="text-[11px] text-faint">AEGIS v1.0.0 · {t('Crisis Console')}</div>
        </div>
      </motion.aside>
    </>
  )
}
