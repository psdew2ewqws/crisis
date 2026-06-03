import { X, Keyboard, Book, MessageCircle, Info, Compass } from 'lucide-react'
import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { useLangStore } from '../stores/langStore'

interface Props {
  open: boolean
  onClose: () => void
  leftOffset?: number
  onReplayTour?: () => void
}

const SHORTCUTS = [
  { keys: ['?'], actionKey: 'help.sc.toggleHelp' },
  { keys: ['['], actionKey: 'help.sc.toggleSidebar' },
  { keys: ['Esc'], actionKey: 'help.sc.closePanels' },
  { keys: ['⌘ / Ctrl', '↵'], actionKey: 'help.sc.send' },
]

const GLOSSARY = [
  { termKey: 'brand.name', defKey: 'help.gloss.voc360', term: 'voc360' },
  { termKey: 'help.gloss.signalTerm', defKey: 'help.gloss.signal' },
  { termKey: 'help.gloss.clusterTerm', defKey: 'help.gloss.cluster' },
  { termKey: 'help.gloss.caseTerm', defKey: 'help.gloss.case' },
]

export default function HelpDrawer({ open, onClose, leftOffset = 248, onReplayTour }: Props) {
  const { t } = useTranslation()
  const rtl = useLangStore((s) => s.lang) === 'ar'
  if (!open) return null

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/40" onClick={onClose} />

      <motion.aside
        initial={{ x: rtl ? 320 : -320, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: rtl ? 320 : -320, opacity: 0 }}
        transition={{ type: 'spring', damping: 28, stiffness: 300 }}
        style={rtl ? { right: leftOffset } : { left: leftOffset }}
        className={`fixed top-0 z-50 flex h-full w-[340px] flex-col bg-card shadow-xl ${rtl ? 'border-l' : 'border-r'} border-border`}
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-[16px] font-semibold text-txt">{t('help.title')}</h2>
          <button
            onClick={onClose}
            aria-label={t('general.close')}
            className="rounded-lg p-1.5 text-muted hover:bg-cardhi hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          {onReplayTour && (
            <button
              onClick={onReplayTour}
              className="flex w-full items-center gap-3 rounded-lg border border-blue/30 bg-blue/5 px-4 py-3 text-start transition-colors hover:bg-blue/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
            >
              <Compass className="h-[18px] w-[18px] text-blue" />
              <div>
                <div className="text-[13.5px] font-medium text-txt">{t('help.replayTour')}</div>
                <div className="text-[11px] text-faint">{t('help.replayTourSub')}</div>
              </div>
            </button>
          )}

          <section>
            <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold tracking-[0.14em] text-faint">
              <Keyboard className="h-3.5 w-3.5" />
              {t('help.shortcutsTitle')}
            </h3>
            <div className="space-y-1.5">
              {SHORTCUTS.map((s) => (
                <div key={s.actionKey} className="flex items-center justify-between rounded-lg border border-border bg-bg px-4 py-2.5">
                  <span className="text-[13px] text-txt">{t(s.actionKey)}</span>
                  <div className="flex gap-1" dir="ltr">
                    {s.keys.map((k) => (
                      <kbd key={k} className="rounded border border-border bg-cardhi px-2 py-0.5 font-mono text-[11px] text-muted">
                        {k}
                      </kbd>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold tracking-[0.14em] text-faint">
              <Info className="h-3.5 w-3.5" />
              {t('help.glossaryTitle')}
            </h3>
            <div className="space-y-2">
              {GLOSSARY.map((g) => (
                <div key={g.defKey} className="rounded-lg border border-border bg-bg px-4 py-3">
                  <div className="text-[13px] font-medium text-txt">{g.term ?? t(g.termKey)}</div>
                  <div className="mt-0.5 text-[12px] leading-relaxed text-muted">{t(g.defKey)}</div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold tracking-[0.14em] text-faint">
              <Book className="h-3.5 w-3.5" />
              {t('help.resourcesTitle')}
            </h3>
            <a
              href="mailto:ops@aegis.gov.jo"
              className="flex items-center gap-3 rounded-lg border border-border bg-bg px-4 py-3 transition-colors hover:bg-cardhi focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
            >
              <MessageCircle className="h-[18px] w-[18px] text-muted" />
              <div>
                <div className="text-[13.5px] font-medium text-txt">{t('help.contact')}</div>
                <div className="text-[11px] text-faint" dir="ltr">ops@aegis.gov.jo</div>
              </div>
            </a>
          </section>

          <section>
            <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold tracking-[0.14em] text-faint">
              <Info className="h-3.5 w-3.5" />
              {t('help.aboutTitle')}
            </h3>
            <div className="space-y-1 rounded-lg border border-border bg-bg px-4 py-3">
              <div className="flex justify-between">
                <span className="text-[13px] text-muted">{t('help.version')}</span>
                <span className="font-mono text-[13px] text-txt" dir="ltr">1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[13px] text-muted">{t('help.dataSource')}</span>
                <span className="font-mono text-[13px] text-txt">{t('help.dataSourceValue')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[13px] text-muted">{t('help.environment')}</span>
                <span className="font-mono text-[13px] text-txt">{t('help.production')}</span>
              </div>
            </div>
          </section>
        </div>
      </motion.aside>
    </>
  )
}
