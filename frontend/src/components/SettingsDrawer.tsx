import { X, Moon, Sun, Bell, Key, Shield } from 'lucide-react'
import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { useThemeStore } from '../stores/themeStore'
import { useLangStore } from '../stores/langStore'

interface Props {
  open: boolean
  onClose: () => void
  leftOffset?: number
}

function Soon() {
  const { t } = useTranslation()
  return (
    <span className="shrink-0 rounded-md border border-border bg-soft px-2 py-0.5 text-[10px] font-semibold tracking-wide text-faint">
      {t('settings.soon')}
    </span>
  )
}

export default function SettingsDrawer({ open, onClose, leftOffset = 248 }: Props) {
  const { theme, toggle } = useThemeStore()
  const { t } = useTranslation()
  const rtl = useLangStore((s) => s.lang) === 'ar'

  if (!open) return null

  return (
    <>
      {/* backdrop */}
      <div className="fixed inset-0 z-40 bg-black/40" onClick={onClose} />

      {/* drawer — anchored to whichever side the sidebar is on */}
      <motion.aside
        initial={{ x: rtl ? 320 : -320, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: rtl ? 320 : -320, opacity: 0 }}
        transition={{ type: 'spring', damping: 28, stiffness: 300 }}
        style={rtl ? { right: leftOffset } : { left: leftOffset }}
        className={`fixed top-0 z-50 flex h-full w-[340px] flex-col bg-card shadow-xl ${rtl ? 'border-l' : 'border-r'} border-border`}
      >
        {/* header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-[16px] font-semibold text-txt">{t('nav.settings')}</h2>
          <button
            onClick={onClose}
            aria-label={t('general.close')}
            className="rounded-lg p-1.5 text-muted hover:bg-cardhi hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          {/* Appearance */}
          <section>
            <h3 className="mb-3 text-[11px] font-semibold tracking-[0.14em] text-faint ltr:tracking-[0.14em]">
              {t('settings.appearance')}
            </h3>
            <button
              onClick={toggle}
              aria-label={theme === 'dark' ? t('settings.switchToLight') : t('settings.switchToDark')}
              className="flex w-full items-center justify-between rounded-lg border border-border bg-bg px-4 py-3 transition-colors hover:bg-cardhi focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
            >
              <div className="flex items-center gap-3">
                {theme === 'dark' ? (
                  <Moon className="h-[18px] w-[18px] text-blue" />
                ) : (
                  <Sun className="h-[18px] w-[18px] text-warn" />
                )}
                <div className="text-start">
                  <div className="text-[13.5px] font-medium text-txt">
                    {theme === 'dark' ? t('settings.darkMode') : t('settings.lightMode')}
                  </div>
                  <div className="text-[11px] text-faint">
                    {theme === 'dark' ? t('settings.switchToLight') : t('settings.switchToDark')}
                  </div>
                </div>
              </div>
              <div className={`relative h-6 w-11 rounded-full transition-colors ${theme === 'dark' ? 'bg-blue' : 'bg-muted'}`}>
                <div
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                    theme === 'dark' ? 'translate-x-5 rtl:-translate-x-5' : 'translate-x-0.5 rtl:-translate-x-0.5'
                  }`}
                />
              </div>
            </button>
          </section>

          {/* Notifications (not yet wired) */}
          <section>
            <h3 className="mb-3 text-[11px] font-semibold tracking-[0.14em] text-faint">{t('settings.notifications')}</h3>
            <div aria-disabled className="flex items-center justify-between gap-3 rounded-lg border border-border bg-bg px-4 py-3 opacity-60">
              <div className="flex items-center gap-3">
                <Bell className="h-[18px] w-[18px] text-muted" />
                <div className="text-[13.5px] font-medium text-txt">{t('settings.pushNotifications')}</div>
              </div>
              <Soon />
            </div>
          </section>

          {/* Security (not yet wired) */}
          <section>
            <h3 className="mb-3 text-[11px] font-semibold tracking-[0.14em] text-faint">{t('settings.security')}</h3>
            <div className="space-y-2">
              <div aria-disabled className="flex items-center justify-between gap-3 rounded-lg border border-border bg-bg px-4 py-3 opacity-60">
                <div className="flex items-center gap-3">
                  <Key className="h-[18px] w-[18px] text-muted" />
                  <div>
                    <div className="text-[13.5px] font-medium text-txt">{t('settings.apiKeys')}</div>
                    <div className="text-[11px] text-faint">{t('settings.apiKeysSub')}</div>
                  </div>
                </div>
                <Soon />
              </div>
              <div aria-disabled className="flex items-center justify-between gap-3 rounded-lg border border-border bg-bg px-4 py-3 opacity-60">
                <div className="flex items-center gap-3">
                  <Shield className="h-[18px] w-[18px] text-muted" />
                  <div>
                    <div className="text-[13.5px] font-medium text-txt">{t('settings.rbac')}</div>
                    <div className="text-[11px] text-faint">{t('settings.rbacSub')}</div>
                  </div>
                </div>
                <Soon />
              </div>
            </div>
          </section>
        </div>

        {/* footer */}
        <div className="border-t border-border px-5 py-3">
          <div className="text-[11px] text-faint">{t('settings.footer')}</div>
        </div>
      </motion.aside>
    </>
  )
}
