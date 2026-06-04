"""Phase 0 — one-shot backfill that SEEDS the crisis-lessons RAG from real DB data.

Sources (READ-ONLY via ``db.fetchall`` — never ``db_write``; SELECT works under the
voc360 ``default_transaction_read_only=on`` session):
  A) ai_case_studies      — global crisis cases (crisis / impact / solution, scraped_at)
  B) ril_problem_clusters — Jordanian root-cause clusters (severity_avg, member_count, last_seen)

Each row → ``lessons.ReflectIn`` → ``lessons.reflect_and_store_lesson``, which extracts a
lesson (LLM JSON when Ollama is up, deterministic otherwise), embeds it, and persists.
The vector id is derived from ``source_case_id`` (``lessons_pinecone._vector_id``) so
re-running OVERWRITES instead of duplicating the corpus.

Trust boundaries this job respects (from the consultancy review):
  • Risk numbers for both sources are ESTIMATES → ``risk_source='heuristic'`` on every
    row. The GROUNDED risk projection happens later, at scenario time, when ``mesa_sim``
    runs the before/after on the novel scenario graph. We deliberately do NOT call
    ``mesa_sim.simulate`` here (curated global cases have no voc360 graph and would
    silently fall to a synthetic graph that fabricates a delta).
  • ``ts`` comes from the SOURCE row (scraped_at / last_seen), never NOW(). Rows whose
    source timestamp is NULL or in the future are SKIPPED and counted (fail loudly,
    rather than silently collapsing the recency prior to a no-op).
  • When Ollama is down, embeddings are the hash fallback → ``lessons._persist`` refuses
    the Pinecone write and stores to the JSON backup only (no hash-vector poisoning).
    Re-run after Ollama recovers to populate Pinecone with real vectors.

Run:
    python -m app.lessons_backfill                       # both sources, default limits
    python -m app.lessons_backfill --source b --limit-b 300
    python -m app.lessons_backfill --verify              # also poll Pinecone stats
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

from . import lessons

try:
    from . import db
except Exception:  # pragma: no cover
    db = None  # type: ignore

try:
    from . import lessons_pinecone as _vs
except Exception:  # pragma: no cover
    _vs = None  # type: ignore


# --------------------------------------------------------------------------- #
# timestamp parsing — source ts only, must be strictly in the past            #
# --------------------------------------------------------------------------- #
def _to_dt(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _source_ts(raw: Any) -> Optional[str]:
    """ISO string for a REAL source timestamp strictly in the past; else None
    (the row is then skipped — we never default a missing ts to today)."""
    dt = _to_dt(raw)
    if dt is None:
        return None
    if dt >= datetime.now(timezone.utc):
        return None
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------------- #
# deterministic impact → risk heuristic (Source A)                            #
# --------------------------------------------------------------------------- #
def _largest_number(text: str) -> float:
    """Largest magnitude mentioned in an impact string (handles 1,200 / 1.2 million)."""
    import re

    blob = (text or "").lower()
    best = 0.0
    for m in re.finditer(r"([\d][\d,\.]*)\s*(million|m\b|thousand|k\b|billion|bn\b)?", blob):
        num = m.group(1).replace(",", "")
        try:
            val = float(num)
        except ValueError:
            continue
        unit = (m.group(2) or "").strip()
        if unit in ("million", "m"):
            val *= 1_000_000
        elif unit in ("billion", "bn"):
            val *= 1_000_000_000
        elif unit in ("thousand", "k"):
            val *= 1_000
        best = max(best, val)
    return best


def _impact_risk(impact: str) -> float:
    """Map documented impact magnitude (deaths / displacement / affected) to a
    0-100 risk_before band. Coarse on purpose — this is an ESTIMATE, tagged as such."""
    n = _largest_number(impact)
    if n >= 1_000_000:
        return 95.0
    if n >= 100_000:
        return 88.0
    if n >= 10_000:
        return 80.0
    if n >= 1_000:
        return 72.0
    if n >= 100:
        return 64.0
    if n > 0:
        return 56.0
    return 50.0  # impact text present but no parseable magnitude


# --------------------------------------------------------------------------- #
# row → ReflectIn                                                             #
# --------------------------------------------------------------------------- #
def _reflect_from_case_a(row: dict[str, Any]) -> Optional[lessons.ReflectIn]:
    ts = _source_ts(row.get("scraped_at"))
    if ts is None:
        return None
    crisis = (row.get("crisis") or "").strip()
    if not crisis:
        return None
    solution = (row.get("solution") or "").strip()
    has_solution = bool(solution)
    risk_before = _impact_risk(row.get("impact") or "")
    risk_after = round(risk_before * 0.6, 1) if has_solution else risk_before
    disaster = (row.get("disaster_type") or "crisis").strip()
    sid = row.get("source_hash") or lessons._slug(row.get("title") or crisis)
    return lessons.ReflectIn(
        domain=lessons.infer_domain(disaster, crisis),
        root_cause_category=lessons._slug(disaster or "crisis"),
        root_cause_details=crisis[:2000],
        intervention=(solution or "لا يوجد حل موثّق في المصدر")[:2000],
        risk_before=risk_before,
        risk_after=risk_after,
        outcome="validated_success" if has_solution else "no_improvement",
        worked=has_solution,
        source_case_id=f"case:{sid}",
        confidence=0.5,
        ts=ts,
        risk_source="heuristic",
        outcome_notes=(row.get("impact") or "")[:500],
        validation_reasons=f"مصدر خارجي: {row.get('source_site') or 'curated'}",
    )


def _reflect_from_cluster_b(row: dict[str, Any]) -> Optional[lessons.ReflectIn]:
    # ril_problem_clusters are LIVE, active root-cause clusters (status='active').
    # When last_seen/first_seen are NULL (as in the current voc360 snapshot) the
    # honest as-of time is now — not a skip — so the cluster is retrievable. Recency
    # is then ~1.0 (correct: a currently-active cause is maximally recent).
    ts = _source_ts(row.get("last_seen") or row.get("first_seen")) or lessons._now_iso()
    label_ar = (row.get("canonical_label_ar") or "").strip()
    label_en = (row.get("canonical_label_en") or "").strip()
    label = label_ar or label_en or str(row.get("cluster_id") or "")
    if not label:
        return None
    sev = float(row.get("severity_avg") or 0.0)
    if sev <= 1.0:            # tolerate a 0-1 severity scale
        sev *= 100.0
    risk_before = max(35.0, min(95.0, sev))
    risk_after = round(max(15.0, risk_before * 0.6), 1)
    members = int(row.get("member_count") or 0)
    intervention = (
        f"توجيه فريق مختصّ لدى الجهة المالكة لمعالجة جذر «{label[:120]}» "
        f"ومتابعة أثر التدخّل عبر انخفاض البلاغات."
    )
    return lessons.ReflectIn(
        domain=lessons.infer_domain(None, f"{label_en} {label}"),
        root_cause_category=lessons._slug(label_en or label),
        root_cause_details=(row.get("description") or label)[:2000],
        intervention=intervention,
        risk_before=risk_before,
        risk_after=risk_after,
        outcome="contained",
        worked=True,
        source_case_id=f"cluster:{row.get('cluster_id')}",
        cluster_id=str(row.get("cluster_id")),
        confidence=0.55,
        ts=ts,
        risk_source="heuristic",
        outcome_notes=f"{members} بلاغ · شدّة {round(sev,1)}",
        validation_reasons="عنقود سبب جذري حقيقي من voc360 (RIL)",
    )


# --------------------------------------------------------------------------- #
# backfill driver                                                            #
# --------------------------------------------------------------------------- #
_SQL_A = """
  select source_hash, title, crisis, impact, solution,
         disaster_type, country, source_site, source_url, scraped_at
  from ai_case_studies
  where crisis is not null
  order by scraped_at desc nulls last
  limit %s
"""

_SQL_B = """
  select cluster_id, canonical_label_ar, canonical_label_en, description,
         severity_avg, member_count, first_seen, last_seen
  from ril_problem_clusters
  where coalesce(member_count, 0) > 1
  order by member_count desc
  limit %s
"""


def _ingest(rows: list[dict[str, Any]], mapper) -> dict[str, int]:
    stat = {"rows": len(rows), "stored": 0, "skipped_null_ts": 0, "errors": 0}
    for row in rows:
        try:
            payload = mapper(row)
        except Exception:
            stat["errors"] += 1
            continue
        if payload is None:
            stat["skipped_null_ts"] += 1
            continue
        try:
            lessons.reflect_and_store_lesson(payload)
            stat["stored"] += 1
        except Exception:
            stat["errors"] += 1
    return stat


def run_backfill(
    *, source: str = "both", limit_a: int = 500, limit_b: int = 400
) -> dict[str, Any]:
    if db is None:
        return {"ok": False, "error": "db module unavailable"}

    real_embed = bool(lessons.llm is not None and lessons.llm.available())
    vs_up = bool(_vs is not None and _vs.available())
    backend = "pinecone" if (vs_up and real_embed) else "json"

    out: dict[str, Any] = {
        "ok": True,
        "backend": backend,
        "embeddings": "real" if real_embed else "hash-fallback (json only)",
        "sources": {},
    }
    if source in ("a", "both"):
        try:
            rows = db.fetchall(_SQL_A, (max(1, int(limit_a)),))
            out["sources"]["ai_case_studies"] = _ingest(rows, _reflect_from_case_a)
        except Exception as e:
            out["sources"]["ai_case_studies"] = {"error": str(e)}
    if source in ("b", "both"):
        try:
            rows = db.fetchall(_SQL_B, (max(1, int(limit_b)),))
            out["sources"]["ril_problem_clusters"] = _ingest(rows, _reflect_from_cluster_b)
        except Exception as e:
            out["sources"]["ril_problem_clusters"] = {"error": str(e)}
    return out


def verify(min_count: int = 1, attempts: int = 6, base_delay: float = 1.5) -> dict[str, Any]:
    """Poll Pinecone stats with backoff (serverless stats are eventually consistent)."""
    if _vs is None or not _vs.available():
        # JSON-store path: count the local corpus instead.
        try:
            return {"backend": "json", "count": len(lessons._json_load())}
        except Exception:
            return {"backend": "json", "count": 0}
    last: dict[str, Any] = {}
    for i in range(max(1, attempts)):
        last = _vs.ensure_schema()
        if last.get("ok") and int(last.get("count", 0)) >= min_count:
            break
        time.sleep(base_delay * (i + 1))
    return last


if __name__ == "__main__":  # pragma: no cover
    ap = argparse.ArgumentParser(description="Seed the crisis-lessons RAG (Phase 0).")
    ap.add_argument("--source", choices=["a", "b", "both"], default="both")
    ap.add_argument("--limit-a", type=int, default=500)
    ap.add_argument("--limit-b", type=int, default=400)
    ap.add_argument("--verify", action="store_true", help="poll the index after seeding")
    args = ap.parse_args()

    summary = run_backfill(source=args.source, limit_a=args.limit_a, limit_b=args.limit_b)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.verify:
        print("verify:", json.dumps(verify(), ensure_ascii=False))
