// EvidencePanel — verified references from the legal research agent (the sci-hub
// replacement). Each item is a REAL paper/record whose DOI/URL passed verify_source;
// nothing here is fabricated, and the panel abstains honestly when no source resolves.

import { motion } from 'motion/react'
import { BookOpen, ExternalLink, ShieldCheck } from 'lucide-react'
import type { ScenarioEvidence } from '../../lib/voc'

const OA_TONE: Record<string, string> = {
  gold: 'border-good/30 bg-good/10 text-good',
  diamond: 'border-good/30 bg-good/10 text-good',
  green: 'border-good/30 bg-good/10 text-good',
  hybrid: 'border-blue/30 bg-blue/10 text-blue',
  bronze: 'border-warn/30 bg-warn/10 text-warn',
  closed: 'border-border bg-soft text-muted',
}

export default function EvidencePanel({
  items,
  abstained,
}: {
  items: ScenarioEvidence[]
  abstained?: boolean
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl border border-border bg-card p-5"
    >
      <div className="mb-3 flex items-center gap-2">
        <BookOpen className="h-4 w-4 text-blue" />
        <h2 className="text-[15px] font-semibold text-txt" dir="auto">الأدلة والمراجع</h2>
        <span className="text-[12px] uppercase tracking-wide text-faint">· EVIDENCE & REFERENCES</span>
        {items.length > 0 && (
          <span className="ms-auto rounded-full border border-border px-2 py-0.5 text-[11.5px] text-muted tnum">
            {items.length}
          </span>
        )}
      </div>

      {abstained || items.length === 0 ? (
        <div className="rounded-lg border border-border bg-bg px-3 py-4 text-center text-[13px] text-faint" dir="auto">
          لا توجد أدلة كافية موثّقة من مصادر مفتوحة لهذا الموضوع — لم نختلق مرجعًا.
        </div>
      ) : (
        <ul className="space-y-2.5">
          {items.map((e, i) => (
            <li
              key={(e.doi || e.url || String(i))}
              className="rounded-lg border border-border bg-bg p-3 transition-colors hover:bg-cardhi"
            >
              <div className="flex items-start justify-between gap-3">
                <a
                  href={e.url || (e.doi ? `https://doi.org/${e.doi}` : '#')}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex-1 text-[13.5px] font-medium leading-snug text-txt hover:text-blue"
                  dir="auto"
                >
                  {e.title || e.doi || e.url}
                  <ExternalLink className="ms-1 inline h-3 w-3 opacity-0 transition-opacity group-hover:opacity-70" />
                </a>
                {e.verified && (
                  <span className="flex shrink-0 items-center gap-1 text-[11px] text-good" title={e.verify_how} dir="auto">
                    <ShieldCheck className="h-3.5 w-3.5" /> موثّق
                  </span>
                )}
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11.5px] text-faint">
                {e.year && <span className="tnum">{e.year}</span>}
                {e.oa_status && (
                  <span className={`rounded border px-1.5 py-0.5 ${OA_TONE[e.oa_status] ?? OA_TONE.closed}`} dir="auto">
                    OA: {e.oa_status}
                  </span>
                )}
                {typeof e.cited_by === 'number' && e.cited_by > 0 && (
                  <span className="tnum">{e.cited_by} اقتباس</span>
                )}
                {e.doi && <span className="font-mono">doi:{e.doi}</span>}
                {e.source && <span className="ms-auto uppercase">{e.source}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </motion.div>
  )
}
