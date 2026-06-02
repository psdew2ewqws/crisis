"""PostgreSQL persistence for successful_lessons (write-capable pool).

voc360 reads use ``db`` (read-only). Lessons use the same ``VOC_DSN`` without
``default_transaction_read_only`` so we can CREATE/INSERT into our own table.
Failures degrade gracefully — the in-memory/file path in ``lessons`` still works.
"""
from __future__ import annotations

import os
from typing import Any, List, Optional

import psycopg

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:  # pragma: no cover
    pass

DSN = os.environ.get("VOC_DSN", "")
_pool: Any = None  # None=uninit, False=no pool, else ConnectionPool


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    if not DSN:
        return False
    try:
        from psycopg_pool import ConnectionPool

        _pool = ConnectionPool(
            DSN, min_size=1, max_size=4, max_idle=300, timeout=90, open=True,
        )
    except Exception:
        _pool = False
    return _pool


def execute(sql: str, params: Any = None) -> None:
    pool = _get_pool()
    if pool:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
        return
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        conn.commit()


def fetchall(sql: str, params: Any = None) -> list[dict[str, Any]]:
    pool = _get_pool()
    if pool:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params or ())
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetchone(sql: str, params: Any = None) -> dict[str, Any] | None:
    rows = fetchall(sql, params)
    return rows[0] if rows else None


def available() -> bool:
    return bool(DSN)


def ensure_schema() -> dict[str, Any]:
    """Create successful_lessons if missing. Idempotent."""
    if not available():
        return {"ok": False, "error": "VOC_DSN is not set"}
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS successful_lessons (
                id TEXT PRIMARY KEY,
                ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                kind TEXT NOT NULL DEFAULT 'success',
                domain TEXT NOT NULL,
                root_cause_category TEXT NOT NULL,
                root_cause_details TEXT NOT NULL,
                intervention TEXT NOT NULL,
                risk_before DOUBLE PRECISION NOT NULL,
                risk_after DOUBLE PRECISION NOT NULL,
                risk_delta DOUBLE PRECISION NOT NULL,
                outcome TEXT NOT NULL,
                lesson_text TEXT NOT NULL,
                why_it_worked TEXT NOT NULL,
                applicable_when TEXT NOT NULL,
                source_case_id TEXT NOT NULL,
                confidence DOUBLE PRECISION NOT NULL DEFAULT 0.8,
                embedding DOUBLE PRECISION[],
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb
            )
        """)
        # The table predates failure-storage; add `kind` for tables already in the
        # wild. 'success' = an intervention that worked; 'failure' = a confirmed
        # anti-pattern (validation rejected it, or it did not reduce risk).
        execute("""
            ALTER TABLE successful_lessons
            ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'success'
        """)
        execute("""
            CREATE INDEX IF NOT EXISTS idx_successful_lessons_domain
            ON successful_lessons (domain)
        """)
        execute("""
            CREATE INDEX IF NOT EXISTS idx_successful_lessons_category
            ON successful_lessons (root_cause_category)
        """)
        execute("""
            CREATE INDEX IF NOT EXISTS idx_successful_lessons_kind
            ON successful_lessons (kind)
        """)
        execute("""
            CREATE INDEX IF NOT EXISTS idx_successful_lessons_ts
            ON successful_lessons (ts DESC)
        """)
        n = fetchone("select count(*)::int as n from successful_lessons")
        by = fetchall("select kind, count(*)::int as n from successful_lessons group by kind")
        counts = {r["kind"]: r["n"] for r in by}
        return {
            "ok": True,
            "table": "successful_lessons",
            "count": (n or {}).get("n", 0),
            "success_count": counts.get("success", 0),
            "failure_count": counts.get("failure", 0),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def insert_lesson(row: dict[str, Any]) -> dict[str, Any]:
    row = {"kind": "success", **row}  # default kind for older callers
    execute("""
        INSERT INTO successful_lessons (
            id, ts, kind, domain, root_cause_category, root_cause_details, intervention,
            risk_before, risk_after, risk_delta, outcome, lesson_text, why_it_worked,
            applicable_when, source_case_id, confidence, embedding, metadata
        ) VALUES (
            %(id)s, %(ts)s, %(kind)s, %(domain)s, %(root_cause_category)s, %(root_cause_details)s,
            %(intervention)s, %(risk_before)s, %(risk_after)s, %(risk_delta)s, %(outcome)s,
            %(lesson_text)s, %(why_it_worked)s, %(applicable_when)s, %(source_case_id)s,
            %(confidence)s, %(embedding)s, %(metadata)s::jsonb
        )
        ON CONFLICT (id) DO NOTHING
    """, row)
    return row


def list_lessons(limit: int = 50) -> List[dict[str, Any]]:
    return fetchall("""
        SELECT id, ts, kind, domain, root_cause_category, root_cause_details, intervention,
               risk_before, risk_after, risk_delta, outcome, lesson_text, why_it_worked,
               applicable_when, source_case_id, confidence, embedding, metadata
        FROM successful_lessons
        ORDER BY ts DESC
        LIMIT %(lim)s
    """, {"lim": limit})


def fetch_candidates(
    domain: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 200,
    kind: Optional[str] = None,
) -> List[dict[str, Any]]:
    clauses = ["1=1"]
    params: dict[str, Any] = {"lim": limit}
    if domain:
        clauses.append("domain = %(domain)s")
        params["domain"] = domain
    if kind:
        clauses.append("kind = %(kind)s")
        params["kind"] = kind
    if category:
        clauses.append(
            "(root_cause_category = %(cat)s OR root_cause_category ILIKE %(cat_like)s "
            "OR root_cause_details ILIKE %(cat_like)s OR lesson_text ILIKE %(cat_like)s)"
        )
        params["cat"] = category
        params["cat_like"] = f"%{category}%"
    sql = f"""
        SELECT id, ts, kind, domain, root_cause_category, root_cause_details, intervention,
               risk_before, risk_after, risk_delta, outcome, lesson_text, why_it_worked,
               applicable_when, source_case_id, confidence, embedding, metadata
        FROM successful_lessons
        WHERE {' AND '.join(clauses)}
        ORDER BY confidence DESC, ts DESC
        LIMIT %(lim)s
    """
    return fetchall(sql, params)