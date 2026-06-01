import { Outlet, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'motion/react'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import WizardShell from './components/wizard/WizardShell'
import { useWizardStore } from './stores/wizardStore'

export default function App() {
  const location = useLocation()
  const wizardOpen = useWizardStore((s) => s.open)
  const wizardMinimized = useWizardStore((s) => s.minimized)
  const showBars = wizardOpen && !wizardMinimized

  return (
    <div className="flex h-screen overflow-hidden bg-bg text-txt">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <div
          className="flex-1 overflow-y-auto transition-[padding] duration-200"
          style={{
            paddingTop: showBars ? 56 : 0,
            paddingBottom: showBars ? 56 : 0,
          }}
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
      <WizardShell />
    </div>
  )
}
