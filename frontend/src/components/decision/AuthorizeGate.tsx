import { useState } from 'react'

interface Props {
  onAuthorized: () => void
}

export default function AuthorizeGate({ onAuthorized }: Props) {
  const [confirming, setConfirming] = useState(false)
  const [nameInput, setNameInput] = useState('')
  const [authorized, setAuthorized] = useState(false)

  const matched = nameInput.trim().toLowerCase() === 'haddad'

  const handleConfirm = () => {
    if (!matched) return
    setAuthorized(true)
    setTimeout(onAuthorized, 2000)
  }

  if (authorized) {
    return (
      <div className="rounded-xl border border-good/30 bg-good/5 p-5 apex-glow" style={{ '--glow-color': '#34D399' } as React.CSSProperties}>
        <div className="text-[15px] font-semibold text-good">✓ Authorized — dispatching intervention</div>
        <div className="mt-1 text-[13px] text-good/70">Redirecting to outcome…</div>
      </div>
    )
  }

  if (confirming) {
    return (
      <div className="rounded-xl border border-border bg-card p-5">
        <label className="text-[13px] text-txt">
          Type your name to confirm:
        </label>
        <div className="mt-2 flex items-center gap-3">
          <input
            type="text"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            placeholder="Enter name…"
            className="rounded-lg border border-border bg-bg px-3 py-2 text-[13px] text-txt placeholder:text-faint focus:border-blue focus:outline-none w-48"
            autoFocus
          />
          <button
            onClick={handleConfirm}
            disabled={!matched}
            className={`rounded-lg px-4 py-2 text-[13px] font-semibold transition-colors ${
              matched
                ? 'bg-blue text-white hover:bg-bluehi'
                : 'bg-card text-faint cursor-not-allowed border border-border'
            }`}
          >
            Confirm
          </button>
          <button
            onClick={() => { setConfirming(false); setNameInput('') }}
            className="rounded-lg border border-border px-3 py-2 text-[12px] text-muted hover:text-txt hover:bg-cardhi"
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <button
      onClick={() => setConfirming(true)}
      className="rounded-lg bg-blue px-6 py-3 text-[16px] font-semibold text-white transition-colors hover:bg-bluehi"
    >
      🔒 AUTHORIZE
    </button>
  )
}
