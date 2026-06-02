import { Component, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { translate, useLocaleStore } from '../lib/i18n'

// A view-level error boundary so a single panel/page render error degrades to a
// recoverable card instead of unmounting the whole console (black screen).
export default class ErrorBoundary extends Component<
  { children: ReactNode; onReset?: () => void },
  { error: Error | null }
> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error) {
    // surface in the console for debugging; the UI stays alive
    console.error('[AEGIS] view error:', error)
  }

  reset = () => {
    this.setState({ error: null })
    this.props.onReset?.()
  }

  render() {
    if (this.state.error) {
      const locale = useLocaleStore.getState().locale
      const tr = (k: string) => translate(locale, k)
      return (
        <div className="grid min-h-0 flex-1 place-items-center p-8">
          <div className="max-w-md rounded-xl border border-danger/40 bg-card p-6 text-center">
            <AlertTriangle className="mx-auto h-6 w-6 text-danger" />
            <h2 className="mt-3 text-[15px] font-semibold text-txt">{tr('This view hit an error')}</h2>
            <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
              {tr('The rest of the console is still running. You can retry this view.')}
            </p>
            <p className="mt-2 break-words font-mono text-[11px] text-faint">
              {String(this.state.error?.message ?? this.state.error)}
            </p>
            <button
              onClick={this.reset}
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[#2f76e8]"
            >
              <RefreshCw className="h-4 w-4" />
              {tr('Retry')}
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
