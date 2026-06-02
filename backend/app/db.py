"""Read-only, POOLED connection to the voc360 Voice-of-Customer database.

A connection pool reuses open connections instead of paying the SSL handshake
(~1-2s to the remote host) on every query — which makes the multi-query engines
(graph, whys, forecast) fast. Falls back to per-query connections if
psycopg_pool is unavailable.
"""
from __future__ import annotations
import os
from typing import Any

import psycopg

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:  # pragma: no cover
    pass

DSN = os.environ.get("VOC_DSN", "")
_RO = "-c default_transaction_read_only=on"

_pool: Any = None  # None=uninit, False=no pool (fallback), else a ConnectionPool


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    if not DSN:
        raise RuntimeError("VOC_DSN is not set — create backend/.env (see .env.example)")
    try:
        from psycopg_pool import ConnectionPool

        _pool = ConnectionPool(
            DSN, min_size=1, max_size=6, max_idle=300, timeout=90,
            kwargs={"options": _RO}, open=True,
        )
    except Exception:
        _pool = False  # degrade to direct connections
    return _pool


def fetchall(sql: str, params: Any = None) -> list[dict[str, Any]]:
    pool = _get_pool()
    if pool:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params or ())
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    with psycopg.connect(DSN, options=_RO) as conn, conn.cursor() as cur:  # fallback
        cur.execute(sql, params or ())
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetchone(sql: str, params: Any = None) -> dict[str, Any] | None:
    rows = fetchall(sql, params)
    return rows[0] if rows else None


def health() -> dict[str, Any]:
    row = fetchone("select version() as v, current_database() as db")
    return {"connected": True, "database": row["db"], "server": row["v"].split(" on ")[0]}
