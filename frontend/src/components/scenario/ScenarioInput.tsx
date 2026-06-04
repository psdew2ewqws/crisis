import { motion } from 'motion/react'
import { Play, RotateCcw, Loader2, MapPin, Wrench, MessagesSquare, Lightbulb } from 'lucide-react'
import type { ScenarioOption } from '../../lib/voc'

interface ScenarioInputProps {
  text: string
  onText: (v: string) => void
  location: string
  onLocation: (v: string) => void
  service: string
  onService: (v: string) => void
  solution: string
  onSolution: (v: string) => void
  locations: ScenarioOption[]
  services: ScenarioOption[]
  runDebate: boolean
  onToggleDebate: (v: boolean) => void
  running: boolean
  onRun: () => void
  onReset: () => void
}

export default function ScenarioInput({
  text,
  onText,
  location,
  onLocation,
  service,
  onService,
  solution,
  onSolution,
  locations,
  services,
  runDebate,
  onToggleDebate,
  running,
  onRun,
  onReset,
}: ScenarioInputProps) {
  const disabled = running || text.trim().length < 6

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      if (!disabled) onRun()
    }
  }

  const selectCls =
    'w-full bg-transparent text-[13px] text-txt focus:outline-none [&>option]:bg-card [&>option]:text-txt'

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl border border-border bg-card p-5"
    >
      <div className="mb-3">
        <p className="text-[12px] uppercase tracking-wide text-faint" dir="auto">إدخال السيناريو · SCENARIO INTAKE</p>
        <h2 className="text-[15px] font-semibold text-txt" dir="auto">وصف الأزمة</h2>
      </div>

      <textarea
        dir="auto"
        value={text}
        onChange={(e) => onText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="صِف الأزمة التي تريد محاكاتها… مثال: انقطاع المياه وتلوّث محتمل في الزرقاء"
        className="min-h-[120px] w-full resize-y rounded-lg border border-border bg-bg px-3.5 py-3 text-[14px] leading-relaxed text-txt placeholder:text-faint transition-colors focus:border-blue focus:outline-none"
      />

      {/* location + service dropdowns + debate toggle */}
      <div className="mt-3 flex flex-wrap items-center gap-2.5">
        <label className="flex min-w-[160px] flex-1 items-center gap-2 rounded-lg border border-border bg-bg px-3 py-2 transition-colors focus-within:border-blue">
          <MapPin className="h-4 w-4 shrink-0 text-faint" />
          <select dir="auto" value={location} onChange={(e) => onLocation(e.target.value)} className={selectCls}>
            <option value="">الموقع — كل المحافظات</option>
            {locations.map((o) => (
              <option key={o.value} value={o.value}>{o.value} · {o.count}</option>
            ))}
          </select>
        </label>

        <label className="flex min-w-[160px] flex-1 items-center gap-2 rounded-lg border border-border bg-bg px-3 py-2 transition-colors focus-within:border-blue">
          <Wrench className="h-4 w-4 shrink-0 text-faint" />
          <select dir="auto" value={service} onChange={(e) => onService(e.target.value)} className={selectCls}>
            <option value="">الخدمة — كل الخدمات</option>
            {services.map((o) => (
              <option key={o.value} value={o.value}>{o.value} · {o.count}</option>
            ))}
          </select>
        </label>

        <button
          type="button"
          role="switch"
          aria-checked={runDebate}
          onClick={() => onToggleDebate(!runDebate)}
          className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-[13px] font-medium transition-colors ${
            runDebate
              ? 'border-blue/30 bg-blue/10 text-blue'
              : 'border-border bg-card text-muted hover:bg-cardhi hover:text-txt'
          }`}
        >
          <MessagesSquare className="h-4 w-4" />
          <span dir="auto">نقاش الوكلاء</span>
          <span className={`relative ms-0.5 h-4 w-7 shrink-0 rounded-full transition-colors ${runDebate ? 'bg-blue' : 'bg-border'}`}>
            <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${runDebate ? 'left-3.5' : 'left-0.5'}`} />
          </span>
        </button>
      </div>

      {/* optional: propose a solution to validate + optimize */}
      <label className="mt-3 flex items-start gap-2 rounded-lg border border-border bg-bg px-3 py-2 transition-colors focus-within:border-blue">
        <Lightbulb className="mt-1.5 h-4 w-4 shrink-0 text-faint" />
        <textarea
          dir="auto"
          value={solution}
          onChange={(e) => onSolution(e.target.value)}
          rows={2}
          placeholder="اقترح حلاً لتقييمه وتحسينه ومعرفة أثره المتوقّع (اختياري) — مثال: إرسال صهاريج طوارئ وإصلاح الشبكة"
          className="w-full resize-y bg-transparent py-1 text-[13px] leading-relaxed text-txt placeholder:text-faint focus:outline-none"
        />
      </label>

      <div className="mt-4 flex items-center justify-end gap-2.5">
        <button
          type="button"
          onClick={onReset}
          disabled={running}
          className="flex items-center gap-2 rounded-lg border border-border bg-card px-3.5 py-2.5 text-[13.5px] font-medium text-muted transition-colors hover:bg-cardhi hover:text-txt disabled:opacity-50"
        >
          <RotateCcw className="h-4 w-4" />
          <span dir="auto">إعادة</span>
        </button>

        <button
          type="button"
          onClick={onRun}
          disabled={disabled}
          className="flex items-center gap-2 rounded-lg bg-blue px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8] disabled:opacity-60"
        >
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          <span dir="auto">{running ? 'جارٍ التحليل…' : 'تشغيل المحاكاة'}</span>
        </button>
      </div>
    </motion.div>
  )
}
