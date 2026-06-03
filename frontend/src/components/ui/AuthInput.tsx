// Themed text input for the auth pages (Phase 2 wires it). Matches the console's dark
// surfaces and blue focus. `dir="auto"` lets the field detect AR/EN as the user types.
import type { InputHTMLAttributes } from 'react'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

export default function AuthInput({ label, id, className = '', ...rest }: Props) {
  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="mb-1.5 block text-[13px] font-medium text-muted">
          {label}
        </label>
      )}
      <input
        id={id}
        dir="auto"
        className={`h-11 w-full rounded-lg border border-border bg-card px-3.5 text-[14px] text-txt outline-none transition-colors placeholder:text-faint hover:bg-cardhi focus:border-blue focus-visible:ring-2 focus-visible:ring-blue/40 ${className}`}
        {...rest}
      />
    </div>
  )
}
