// A horizontal rule with optional centered label ("or" / "أو"). No dependencies.
export default function AuthSeparator({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="h-px flex-1 bg-border" />
      {label && <span className="text-[12px] text-faint">{label}</span>}
      <span className="h-px flex-1 bg-border" />
    </div>
  )
}
