import { X, Keyboard, Book, MessageCircle, Info } from 'lucide-react'
import { motion } from 'motion/react'
import { useT } from '../lib/i18n'

interface Props {
  open: boolean
  onClose: () => void
}

const SHORTCUTS = [
  { keys: ['Esc'], action: 'Toggle wizard mini-tracker' },
  { keys: ['Ctrl', 'K'], action: 'Command palette (future)' },
  { keys: ['Ctrl', '?'], action: 'Open help' },
]

export default function HelpDrawer({ open, onClose }: Props) {
  const { t } = useT()
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
          <h2 className="text-[16px] font-semibold text-txt">{t('Help & Support')}</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted hover:bg-cardhi hover:text-txt"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Keyboard shortcuts */}
          <section>
            <h3 className="flex items-center gap-2 text-[11px] font-semibold tracking-[0.14em] text-faint mb-3">
              <Keyboard className="h-3.5 w-3.5" />
              {t('KEYBOARD SHORTCUTS')}
            </h3>
            <div className="space-y-1.5">
              {SHORTCUTS.map((s) => (
                <div
                  key={s.action}
                  className="flex items-center justify-between rounded-lg border border-border bg-bg px-4 py-2.5"
                >
                  <span className="text-[13px] text-txt">{t(s.action)}</span>
                  <div className="flex gap-1">
                    {s.keys.map((k) => (
                      <kbd
                        key={k}
                        className="rounded border border-border bg-cardhi px-2 py-0.5 font-mono text-[11px] text-muted"
                      >
                        {k}
                      </kbd>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Quick Links */}
          <section>
            <h3 className="flex items-center gap-2 text-[11px] font-semibold tracking-[0.14em] text-faint mb-3">
              <Book className="h-3.5 w-3.5" />
              {t('RESOURCES')}
            </h3>
            <div className="space-y-2">
              <div className="flex items-center gap-3 rounded-lg border border-border bg-bg px-4 py-3">
                <Book className="h-[18px] w-[18px] text-muted" />
                <div>
                  <div className="text-[13.5px] font-medium text-txt">{t('Documentation')}</div>
                  <div className="text-[11px] text-faint">{t('AEGIS user guide & API reference')}</div>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border border-border bg-bg px-4 py-3">
                <MessageCircle className="h-[18px] w-[18px] text-muted" />
                <div>
                  <div className="text-[13.5px] font-medium text-txt">{t('Contact Support')}</div>
                  <div className="text-[11px] text-faint">ops@aegis.gov.jo</div>
                </div>
              </div>
            </div>
          </section>

          {/* About */}
          <section>
            <h3 className="flex items-center gap-2 text-[11px] font-semibold tracking-[0.14em] text-faint mb-3">
              <Info className="h-3.5 w-3.5" />
              {t('ABOUT')}
            </h3>
            <div className="rounded-lg border border-border bg-bg px-4 py-3 space-y-1">
              <div className="flex justify-between">
                <span className="text-[13px] text-muted">{t('Version')}</span>
                <span className="font-mono text-[13px] text-txt">1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[13px] text-muted">{t('Build')}</span>
                <span className="font-mono text-[13px] text-txt">2025.08.01</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[13px] text-muted">{t('Environment')}</span>
                <span className="font-mono text-[13px] text-txt">{t('Production')}</span>
              </div>
            </div>
          </section>
        </div>
      </motion.aside>
    </>
  )
}
