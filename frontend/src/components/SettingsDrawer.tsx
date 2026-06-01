import { X, Moon, Sun, Bell, Key, Shield } from 'lucide-react'
import { motion } from 'motion/react'
import { useThemeStore } from '../stores/themeStore'

interface Props {
  open: boolean
  onClose: () => void
}

export default function SettingsDrawer({ open, onClose }: Props) {
  const { theme, toggle } = useThemeStore()

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
        className="fixed left-[248px] top-0 z-50 flex h-full w-[340px] flex-col border-r border-border bg-card shadow-xl"
      >
        {/* header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-[16px] font-semibold text-txt">Settings</h2>
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
            <h3 className="text-[11px] font-semibold tracking-[0.14em] text-faint mb-3">APPEARANCE</h3>
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
                <div className="text-left">
                  <div className="text-[13.5px] font-medium text-txt">
                    {theme === 'dark' ? 'Dark Mode' : 'Light Mode'}
                  </div>
                  <div className="text-[11px] text-faint">Switch to {theme === 'dark' ? 'light' : 'dark'} theme</div>
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
          </section>

          {/* Notifications (placeholder) */}
          <section>
            <h3 className="text-[11px] font-semibold tracking-[0.14em] text-faint mb-3">NOTIFICATIONS</h3>
            <div className="flex items-center gap-3 rounded-lg border border-border bg-bg px-4 py-3">
              <Bell className="h-[18px] w-[18px] text-muted" />
              <div>
                <div className="text-[13.5px] font-medium text-txt">Push Notifications</div>
                <div className="text-[11px] text-faint">Coming soon</div>
              </div>
            </div>
          </section>

          {/* Security (placeholder) */}
          <section>
            <h3 className="text-[11px] font-semibold tracking-[0.14em] text-faint mb-3">SECURITY</h3>
            <div className="space-y-2">
              <div className="flex items-center gap-3 rounded-lg border border-border bg-bg px-4 py-3">
                <Key className="h-[18px] w-[18px] text-muted" />
                <div>
                  <div className="text-[13.5px] font-medium text-txt">API Keys</div>
                  <div className="text-[11px] text-faint">Manage integrations</div>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border border-border bg-bg px-4 py-3">
                <Shield className="h-[18px] w-[18px] text-muted" />
                <div>
                  <div className="text-[13.5px] font-medium text-txt">RBAC Policies</div>
                  <div className="text-[11px] text-faint">Role-based access control</div>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* footer */}
        <div className="border-t border-border px-5 py-3">
          <div className="text-[11px] text-faint">AEGIS v1.0.0 · Crisis Console</div>
        </div>
      </motion.aside>
    </>
  )
}
