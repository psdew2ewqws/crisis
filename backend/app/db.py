"""Read-only connection to the voc360 Voice-of-Customer database."""
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


def _connect() -> psycopg.Connection:
    if not DSN:
        raise RuntimeError("VOC_DSN is not set — create backend/.env (see .env.example)")
    # Enforce read-only at the session level — this service never writes.
    return psycopg.connect(DSN, options="-c default_transaction_read_only=on")


def fetchall(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetchone(sql: str, params: tuple | None = None) -> dict[str, Any] | None:
    rows = fetchall(sql, params)
    return rows[0] if rows else None


def health() -> dict[str, Any]:
    row = fetchone("select version() as v, current_database() as db")
    return {"connected": True, "database": row["db"], "server": row["v"].split(" on ")[0]}
