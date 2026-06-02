"""Write-capable (read-write) connection helper for AEGIS internal tables.

The main db.py is intentionally read-only (default_transaction_read_only=on)
for safety against accidental writes to the voc360 source data.

This module provides a separate connection for tables we OWN (aegis_guardrails,
etc.) using a plain, writable connection — still over SSL, same credentials.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

import psycopg

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass

# Same DSN as db.py but WITHOUT the read-only option.
_WRITE_DSN = os.environ.get(
    "VOC_DSN",
    "host=87.239.129.246 port=5432 dbname=voc360 user=voc_admin "
    "password=uqKEQXkfzJL9qUXGvgzzIyFuQ281 sslmode=require",
)


@contextmanager
def get_conn() -> Generator[psycopg.Connection, None, None]:
    """Context manager: yields an open read-write psycopg connection."""
    with psycopg.connect(_WRITE_DSN) as conn:
        yield conn


def execute(sql: str, params: Any = None) -> None:
    """Run a single DML/DDL statement and commit."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()


def fetchall_write(sql: str, params: Any = None) -> list[dict[str, Any]]:
    """Run a SELECT on the write connection (avoids read-only pool)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetchone_write(sql: str, params: Any = None) -> dict[str, Any] | None:
    rows = fetchall_write(sql, params)
    return rows[0] if rows else None
