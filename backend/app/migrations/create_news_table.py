"""
Create (if not exists) the aegis_news table in voc360.

Run once:
    python -m app.migrations.create_news_table

Or call ensure_table() at startup (idempotent).
"""
from __future__ import annotations

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS aegis_news (
    id          TEXT        PRIMARY KEY,        -- sha1[:12] of article link
    title       TEXT        NOT NULL,
    summary     TEXT        NOT NULL DEFAULT '',
    source      TEXT        NOT NULL DEFAULT '',
    link        TEXT        NOT NULL,
    published   TIMESTAMPTZ,                    -- null when pubDate could not be parsed
    gov         TEXT,                           -- canonical gov id (amman/irbid/…); null = national/unlocated
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_aegis_news_gov
    ON aegis_news (gov)
    WHERE gov IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_aegis_news_published
    ON aegis_news (published DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_aegis_news_fetched
    ON aegis_news (fetched_at DESC);
"""


def ensure_table() -> None:
    """Create the table and indexes if they don't already exist (idempotent)."""
    from ..db_write import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_SQL)
        conn.commit()
    print("[news migration] aegis_news table ready.")


if __name__ == "__main__":
    ensure_table()
