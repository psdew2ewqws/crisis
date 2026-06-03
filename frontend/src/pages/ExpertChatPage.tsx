/**
 * ExpertChatPage — domain-expert chat interface with Gemma 4
 *
 * Features:
 *  • Chat with the Gemma model (Ollama, local)
 *  • Each AI message has "✓ Correct" / "✗ Correct this" buttons
 *  • Correction modal → saved as a guardrail to guardrails.json (backend)
 *  • Badge shows when a guardrail was applied in a response
 *  • Guardrails panel (drawer) lists all saved corrections
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  MessageCircle,
  Send,
  XCircle,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  Trash2,
  ToggleLeft,
  ToggleRight,
  AlertTriangle,
  Bot,
  User,
  Loader2,
} from 'lucide-react'

/* ─── palette (matches AEGIS tokens) ───────────────────────────────────────
 * Neutral surfaces reference the same CSS variables the rest of the app uses
 * (see index.css [data-theme]) so this page tracks light/dark automatically.
 * Accents stay static; their tinted backgrounds/borders use alpha so they read
 * correctly on both a dark and a white surface.                              */
const C = {
  bg: 'var(--color-bg)',
  card: 'var(--color-card)',
  cardhi: 'var(--color-cardhi)',
  border: 'var(--color-border)',
  soft: 'var(--color-soft)',
  txt: 'var(--color-txt)',
  muted: 'var(--color-muted)',
  faint: 'var(--color-faint)',
  blue: '#3B82F6',
  danger: '#F04359',
  good: '#34D399',
  warn: '#FBBF24',
  goodBg: 'rgba(52,211,153,0.12)',
  goodBorder: 'rgba(52,211,153,0.35)',
  warnBg: 'rgba(251,191,36,0.12)',
  warnBorder: 'rgba(251,191,36,0.35)',
} as const

/* ─── API client ────────────────────────────────────────────────────────── */
const BASE =
  (import.meta.env.VITE_API as string | undefined) ??
  `${window.location.protocol}//${window.location.hostname}:8000`

async function apiFetch<T>(path: string, init?: RequestInit, fallback?: T): Promise<T> {
  try {
    const r = await fetch(BASE + path, init)
    if (!r.ok) return fallback as T
    return (await r.json()) as T
  } catch {
    return fallback as T
  }
}

const apiPost = <T,>(path: string, body: unknown, fallback: T) =>
  apiFetch<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }, fallback)

/* ─── types ─────────────────────────────────────────────────────────────── */
interface GuardrailApplied {
  id: string
  topic: string
  question: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  guardrails_applied?: GuardrailApplied[]
  model_ok?: boolean
  corrected?: boolean        // user approved this answer as a guardrail
  wrong?: boolean            // user marked this as wrong (correction form open)
  approvedGuardrail?: boolean // saved directly via approve button
}

interface Guardrail {
  id: string
  created_at: string
  question: string
  wrong_answer: string
  correct_answer: string
  topic: string
  active: boolean
}

interface ChatResponse {
  ok: boolean
  answer: string
  guardrails_applied: GuardrailApplied[]
  model_ok: boolean
  model: string
}

interface GuardrailsResponse {
  ok: boolean
  guardrails: Guardrail[]
  count: number
}

interface HealthResponse {
  ok: boolean
  model: string
  model_available: boolean
  base_url: string
  guardrails_count: number
  active_guardrails: number
}

/* ─── helpers ───────────────────────────────────────────────────────────── */
function uid() {
  return Math.random().toString(36).slice(2)
}
function isRtl(s: string) {
  return /[؀-ۿ]/.test(s)
}
function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

/* ─── sub-components ────────────────────────────────────────────────────── */

function ModelBadge({ available, model }: { available: boolean; model: string }) {
  return (
    <span
      className="flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[9px] tracking-[0.1em]"
      style={{ background: C.soft, color: available ? C.good : C.warn }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: available ? C.good : C.warn }}
      />
      {available ? model.toUpperCase() : 'MODEL OFFLINE'}
    </span>
  )
}

function GuardrailBadge({ items }: { items: GuardrailApplied[] }) {
  if (!items.length) return null
  return (
    <span
      className="flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[9px] tracking-[0.1em]"
      style={{ background: C.goodBg, color: C.good, border: `1px solid ${C.goodBorder}` }}
      title={items.map((g) => g.question).join('\n')}
    >
      <ShieldCheck className="h-2.5 w-2.5" />
      {items.length} GUARDRAIL{items.length > 1 ? 'S' : ''} APPLIED
    </span>
  )
}

/** Inline correction form shown below a wrong AI message */
function CorrectionForm({
  originalQuestion,
  onSave,
  onCancel,
}: {
  originalQuestion: string
  wrongAnswer: string
  onSave: (correct: string, topic: string) => void
  onCancel: () => void
}) {
  const [correct, setCorrect] = useState('')
  const [topic, setTopic] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  return (
    <div
      className="mt-2 rounded-lg border p-3"
      style={{ borderColor: C.warnBorder, background: C.warnBg }}
    >
      <div className="mb-2 flex items-center gap-1.5 font-mono text-[9px] tracking-[0.12em]" style={{ color: C.warn }}>
        <ShieldCheck className="h-3 w-3" />
        ADD CORRECTION AS GUARDRAIL
      </div>
      <div className="mb-2 text-[11px]" style={{ color: C.faint }}>
        <span style={{ color: C.muted }}>Question:</span>{' '}
        <span dir={isRtl(originalQuestion) ? 'rtl' : 'ltr'}>{originalQuestion}</span>
      </div>
      <textarea
        ref={textareaRef}
        value={correct}
        onChange={(e) => setCorrect(e.target.value)}
        placeholder="Type the correct answer…"
        dir={isRtl(correct) ? 'rtl' : 'ltr'}
        rows={3}
        className="w-full resize-none rounded border px-3 py-2 text-[13px] text-txt placeholder:text-faint focus:outline-none"
        style={{ background: C.bg, borderColor: C.border }}
      />
      <div className="mt-2 flex items-center gap-2">
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Topic tag (optional)"
          className="min-w-0 flex-1 rounded border px-2.5 py-1.5 text-[12px] text-txt placeholder:text-faint focus:outline-none"
          style={{ background: C.bg, borderColor: C.border }}
        />
        <button
          disabled={!correct.trim()}
          onClick={() => onSave(correct.trim(), topic.trim())}
          className="flex items-center gap-1.5 rounded px-3 py-1.5 text-[12px] font-semibold transition-colors disabled:opacity-40"
          style={{ background: C.warn, color: '#0a0a0b' }}
        >
          <ShieldCheck className="h-3.5 w-3.5" />
          Save Guardrail
        </button>
        <button
          onClick={onCancel}
          className="rounded px-3 py-1.5 text-[12px] transition-colors hover:text-txt"
          style={{ color: C.muted }}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

/** Single chat message bubble */
function MessageBubble({
  msg,
  lastUserContent,
  onCorrect,
  onApproveAsGuardrail,
  onSaveGuardrail,
  onCancelCorrection,
}: {
  msg: ChatMessage
  lastUserContent: string
  onCorrect: (id: string) => void
  onApproveAsGuardrail: (id: string) => void
  onSaveGuardrail: (msgId: string, correct: string, topic: string) => void
  onCancelCorrection: (id: string) => void
}) {
  const isUser = msg.role === 'user'
  const rtl = isRtl(msg.content)

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* avatar */}
      <div
        className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
        style={{ background: isUser ? C.blue : C.soft, border: `1px solid ${C.border}` }}
      >
        {isUser ? (
          <User className="h-3.5 w-3.5 text-white" />
        ) : (
          <Bot className="h-3.5 w-3.5" style={{ color: C.good }} />
        )}
      </div>

      <div className={`flex min-w-0 max-w-[78%] flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        {/* bubble */}
        <div
          className="rounded-2xl px-4 py-2.5 text-[13.5px] leading-relaxed"
          dir={rtl ? 'rtl' : 'ltr'}
          style={{
            background: isUser ? C.blue : C.card,
            color: isUser ? '#FFFFFF' : C.txt,
            border: isUser ? 'none' : `1px solid ${C.border}`,
            borderTopLeftRadius: isUser ? undefined : 4,
            borderTopRightRadius: isUser ? 4 : undefined,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {msg.content}
        </div>

        {/* meta badges + action buttons (assistant only) */}
        {!isUser && (
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            {msg.guardrails_applied && msg.guardrails_applied.length > 0 && (
              <GuardrailBadge items={msg.guardrails_applied} />
            )}
            {msg.model_ok === false && (
              <span
                className="flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[9px]"
                style={{ background: C.soft, color: C.warn }}
              >
                <AlertTriangle className="h-2.5 w-2.5" />
                MODEL OFFLINE
              </span>
            )}

            {/* correct / wrong action buttons */}
            {!msg.corrected && !msg.wrong && (
              <>
                <button
                  onClick={() => onApproveAsGuardrail(msg.id)}
                  className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium transition-colors"
                  style={{ color: C.good, border: `1px solid ${C.goodBorder}`, background: C.goodBg }}
                  title="Approve this answer as a guardrail for the agent swarm"
                >
                  <ShieldCheck className="h-3 w-3" />
                  Approve as Guardrail
                </button>
                <button
                  onClick={() => onCorrect(msg.id)}
                  className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] transition-colors"
                  style={{ color: C.warn, border: `1px solid ${C.warnBorder}`, background: C.warnBg }}
                  title="This answer is wrong — correct it"
                >
                  <XCircle className="h-3 w-3" />
                  Correct this
                </button>
              </>
            )}
            {msg.corrected && (
              <span
                className="flex items-center gap-1 text-[11px]"
                style={{ color: C.good }}
              >
                <ShieldCheck className="h-3 w-3" />
                {msg.approvedGuardrail ? 'Approved as guardrail' : 'Correction saved'}
              </span>
            )}
          </div>
        )}

        {/* correction form */}
        {msg.wrong && !msg.corrected && (
          <CorrectionForm
            originalQuestion={lastUserContent}
            wrongAnswer={msg.content}
            onSave={(correct, topic) => onSaveGuardrail(msg.id, correct, topic)}
            onCancel={() => onCancelCorrection(msg.id)}
          />
        )}
      </div>
    </div>
  )
}

/** Guardrails management drawer */
function GuardrailsPanel({
  guardrails,
  onToggle,
  onDelete,
  onRefresh,
}: {
  guardrails: Guardrail[]
  onToggle: (id: string, active: boolean) => void
  onDelete: (id: string) => void
  onRefresh: () => void
}) {
  return (
    <div className="flex flex-col" style={{ height: '100%' }}>
      <div className="flex items-center justify-between border-b px-5 py-3" style={{ borderColor: C.border }}>
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4" style={{ color: C.good }} />
          <span className="text-[13px] font-semibold text-txt">Saved Guardrails</span>
          <span
            className="rounded-full px-2 py-0.5 font-mono text-[10px]"
            style={{ background: C.soft, color: C.muted }}
          >
            {guardrails.filter((g) => g.active).length} active / {guardrails.length} total
          </span>
        </div>
        <button
          onClick={onRefresh}
          className="text-[11px] transition-colors hover:text-txt"
          style={{ color: C.faint }}
        >
          Refresh
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {guardrails.length === 0 ? (
          <p className="py-8 text-center text-[13px]" style={{ color: C.faint }}>
            No guardrails saved yet. Approve a correct answer or correct a wrong one to add guardrails.
          </p>
        ) : (
          guardrails.map((g) => (
            <div
              key={g.id}
              className="rounded-xl border p-4"
              style={{
                borderColor: g.active ? C.goodBorder : C.border,
                background: g.active ? C.goodBg : C.card,
                opacity: g.active ? 1 : 0.55,
              }}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    {g.topic && (
                      <span
                        className="rounded px-1.5 py-0.5 font-mono text-[9px]"
                        style={{ background: C.soft, color: C.muted }}
                      >
                        {g.topic}
                      </span>
                    )}
                    <span className="font-mono text-[9px]" style={{ color: C.faint }}>
                      {fmtDate(g.created_at)}
                    </span>
                  </div>
                  <p
                    className="text-[12.5px] font-medium text-txt"
                    dir={isRtl(g.question) ? 'rtl' : 'ltr'}
                  >
                    Q: {g.question}
                  </p>
                  {g.wrong_answer && (
                    <p
                      className="mt-1 text-[11.5px] line-through"
                      style={{ color: C.danger }}
                      dir={isRtl(g.wrong_answer) ? 'rtl' : 'ltr'}
                    >
                      ✗ {g.wrong_answer.slice(0, 120)}{g.wrong_answer.length > 120 ? '…' : ''}
                    </p>
                  )}
                  <p
                    className="mt-1 text-[12px]"
                    style={{ color: C.good }}
                    dir={isRtl(g.correct_answer) ? 'rtl' : 'ltr'}
                  >
                    ✓ {g.correct_answer}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <button
                    onClick={() => onToggle(g.id, !g.active)}
                    title={g.active ? 'Disable' : 'Enable'}
                    style={{ color: g.active ? C.good : C.faint }}
                    className="transition-colors hover:opacity-80"
                  >
                    {g.active ? (
                      <ToggleRight className="h-4 w-4" />
                    ) : (
                      <ToggleLeft className="h-4 w-4" />
                    )}
                  </button>
                  <button
                    onClick={() => onDelete(g.id)}
                    title="Delete"
                    className="transition-colors hover:opacity-80"
                    style={{ color: C.faint }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

/* ─── main page ─────────────────────────────────────────────────────────── */
export default function ExpertChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [guardrails, setGuardrails] = useState<Guardrail[]>([])
  const [showGuardrails, setShowGuardrails] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // load health + guardrails on mount
  useEffect(() => {
    void apiFetch<HealthResponse>('/api/expert/health', undefined, {
      ok: false,
      model: 'gemma3',
      model_available: false,
      base_url: '',
      guardrails_count: 0,
      active_guardrails: 0,
    }).then(setHealth)
    void loadGuardrails()
  }, [])

  const loadGuardrails = useCallback(async () => {
    const res = await apiFetch<GuardrailsResponse>('/api/expert/guardrails', undefined, {
      ok: false,
      guardrails: [],
      count: 0,
    })
    setGuardrails(res.guardrails ?? [])
  }, [])

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')

    const userMsg: ChatMessage = { id: uid(), role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    try {
      // build history for context window (last 20 msgs)
      const historyForApi = messages.slice(-20).map((m) => ({
        role: m.role,
        content: m.content,
      }))

      const res = await apiPost<ChatResponse>(
        '/api/expert/chat',
        { message: text, history: historyForApi },
        { ok: false, answer: 'Error contacting the backend.', guardrails_applied: [], model_ok: false, model: 'unknown' },
      )

      const aiMsg: ChatMessage = {
        id: uid(),
        role: 'assistant',
        content: res.answer,
        guardrails_applied: res.guardrails_applied ?? [],
        model_ok: res.model_ok,
      }
      setMessages((prev) => [...prev, aiMsg])
    } finally {
      setLoading(false)
    }
  }, [input, loading, messages])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendMessage()
    }
  }

  // find the user message that immediately preceded a given assistant message
  const getPrecedingUserContent = (msgId: string): string => {
    const idx = messages.findIndex((m) => m.id === msgId)
    for (let i = idx - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return messages[i].content
    }
    return ''
  }

  const handleApproveAsGuardrail = useCallback(
    async (msgId: string) => {
      const msg = messages.find((m) => m.id === msgId)
      if (!msg) return
      const question = getPrecedingUserContent(msgId)

      const res = await apiPost<{ ok: boolean; guardrail?: Guardrail }>(
        '/api/expert/guardrail',
        { question, wrong_answer: '', correct_answer: msg.content, topic: '' },
        { ok: false },
      )

      if (res.ok) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId ? { ...m, corrected: true, wrong: false, approvedGuardrail: true } : m,
          ),
        )
        await loadGuardrails()
        showToast('Answer approved as guardrail ✓')
      } else {
        showToast('Failed to save guardrail')
      }
    },
    [messages, loadGuardrails],
  )

  const handleOpenCorrection = (id: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, wrong: true, corrected: false } : m)),
    )
  }

  const handleCancelCorrection = (id: string) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, wrong: false } : m)))
  }

  const handleSaveGuardrail = useCallback(
    async (msgId: string, correctAnswer: string, topic: string) => {
      const msg = messages.find((m) => m.id === msgId)
      if (!msg) return
      const question = getPrecedingUserContent(msgId)
      const wrongAnswer = msg.content

      const res = await apiPost<{ ok: boolean; guardrail?: Guardrail }>(
        '/api/expert/guardrail',
        { question, wrong_answer: wrongAnswer, correct_answer: correctAnswer, topic },
        { ok: false },
      )

      if (res.ok) {
        setMessages((prev) =>
          prev.map((m) => (m.id === msgId ? { ...m, wrong: false, corrected: true } : m)),
        )
        await loadGuardrails()
        showToast('Guardrail saved ✓')
      } else {
        showToast('Failed to save guardrail')
      }
    },
    [messages, loadGuardrails],
  )

  const handleToggleGuardrail = useCallback(
    async (id: string, active: boolean) => {
      await apiFetch(`/api/expert/guardrails/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active }),
      })
      await loadGuardrails()
    },
    [loadGuardrails],
  )

  const handleDeleteGuardrail = useCallback(
    async (id: string) => {
      await apiFetch(`/api/expert/guardrails/${id}`, { method: 'DELETE' })
      await loadGuardrails()
      showToast('Guardrail deleted')
    },
    [loadGuardrails],
  )

  return (
    <div className="flex h-full overflow-hidden" style={{ background: C.bg }}>
      {/* ── chat column ─────────────────────────────────────────────────── */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* header */}
        <div
          className="flex items-center justify-between border-b px-6 py-3.5"
          style={{ borderColor: C.border, background: C.card }}
        >
          <div className="flex items-center gap-3">
            <div
              className="grid h-8 w-8 place-items-center rounded-lg"
              style={{ background: C.goodBg, border: `1px solid ${C.goodBorder}` }}
            >
              <Bot className="h-4 w-4" style={{ color: C.good }} />
            </div>
            <div>
              <div className="text-[14px] font-semibold text-txt">Expert Chat</div>
              <div className="text-[11px]" style={{ color: C.faint }}>
                Gemma · Domain intelligence with guardrails
              </div>
            </div>
            {health && (
              <ModelBadge available={health.model_available} model={health.model} />
            )}
          </div>
          <button
            onClick={() => setShowGuardrails((s) => !s)}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] transition-colors"
            style={{
              background: showGuardrails ? C.goodBg : C.soft,
              color: showGuardrails ? C.good : C.muted,
              border: `1px solid ${showGuardrails ? C.goodBorder : C.border}`,
            }}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            Guardrails
            <span
              className="rounded-full px-1.5 py-0.5 font-mono text-[9px]"
              style={{ background: C.card, color: C.muted }}
            >
              {guardrails.filter((g) => g.active).length}
            </span>
            {showGuardrails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        </div>

        {/* model-offline banner */}
        {health && !health.model_available && (
          <div
            className="flex items-center gap-2 px-6 py-2.5 text-[12.5px]"
            style={{ background: C.warnBg, borderBottom: `1px solid ${C.warnBorder}`, color: C.warn }}
          >
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            Gemma model offline. Start Ollama and run{' '}
            <code className="rounded px-1 font-mono text-[11px]" style={{ background: C.soft }}>
              ollama pull {health.model}
            </code>{' '}
            to enable AI responses. Guardrails still save normally.
          </div>
        )}

        {/* messages */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <MessageCircle className="mb-4 h-10 w-10" style={{ color: C.faint }} />
              <p className="text-[14px] font-medium text-txt">Ask a domain question</p>
              <p className="mt-1 max-w-sm text-[12.5px]" style={{ color: C.muted }}>
                Ask about root causes, signals, forecasts, or any voc360 insight. If the answer is
                wrong, correct it — your correction becomes a guardrail for future answers.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {[
                  'What are the top root-cause clusters right now?',
                  'Which service is forecast to escalate?',
                  'Explain the why-chain for urgent service fees',
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => setInput(q)}
                    className="rounded-full border px-3 py-1.5 text-[12px] transition-colors hover:text-txt"
                    style={{ borderColor: C.border, color: C.muted, background: C.card }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              msg={msg}
              lastUserContent={getPrecedingUserContent(msg.id)}
              onCorrect={handleOpenCorrection}
                onApproveAsGuardrail={handleApproveAsGuardrail}
              onSaveGuardrail={handleSaveGuardrail}
              onCancelCorrection={handleCancelCorrection}
            />
          ))}

          {loading && (
            <div className="flex gap-3">
              <div
                className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
                style={{ background: C.soft, border: `1px solid ${C.border}` }}
              >
                <Bot className="h-3.5 w-3.5" style={{ color: C.good }} />
              </div>
              <div
                className="flex items-center gap-2 rounded-2xl px-4 py-2.5 text-[13px]"
                style={{ background: C.card, border: `1px solid ${C.border}`, color: C.muted, borderTopLeftRadius: 4 }}
              >
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Thinking…
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* input bar */}
        <div
          className="border-t px-6 py-4"
          style={{ borderColor: C.border, background: C.card }}
        >
          <div
            className="flex items-end gap-3 rounded-xl border px-4 py-3"
            style={{ borderColor: C.border, background: C.bg }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              dir={isRtl(input) ? 'rtl' : 'ltr'}
              placeholder="Ask a domain question… (Enter to send, Shift+Enter for newline)"
              rows={1}
              className="min-w-0 flex-1 resize-none bg-transparent text-[13.5px] text-txt placeholder:text-faint focus:outline-none"
              style={{ maxHeight: 120, overflowY: 'auto' }}
            />
            <button
              onClick={() => void sendMessage()}
              disabled={!input.trim() || loading}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors disabled:opacity-40"
              style={{ background: C.blue }}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin text-white" />
              ) : (
                <Send className="h-4 w-4 text-white" />
              )}
            </button>
          </div>
          <p className="mt-1.5 text-[10.5px]" style={{ color: C.faint }}>
            Mark wrong answers with "Correct this" to add guardrails · Guardrails are saved to{' '}
            <code className="font-mono">guardrails.json</code>
          </p>
        </div>
      </div>

      {/* ── guardrails panel ─────────────────────────────────────────────── */}
      {showGuardrails && (
        <div
          className="w-[400px] shrink-0 border-l"
          style={{ borderColor: C.border, background: C.card }}
        >
          <GuardrailsPanel
            guardrails={guardrails}
            onToggle={handleToggleGuardrail}
            onDelete={handleDeleteGuardrail}
            onRefresh={loadGuardrails}
          />
        </div>
      )}

      {/* toast */}
      {toast && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-xl px-5 py-2.5 text-[13px] font-medium shadow-xl"
          style={{ background: C.good, color: '#0a0a0b', zIndex: 100 }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}
