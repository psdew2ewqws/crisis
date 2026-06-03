"""
Create (if not exists) the aegis_guardrails table in voc360.

Run once:
    python -m backend.app.migrations.create_guardrails_table

Or call ensure_table() at startup (idempotent).
"""
from __future__ import annotations

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS aegis_guardrails (
    id              TEXT        PRIMARY KEY,            -- uuid4 hex
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    question        TEXT        NOT NULL,               -- original expert question
    wrong_answer    TEXT        NOT NULL DEFAULT '',    -- what the model said (audit)
    correct_answer  TEXT        NOT NULL,               -- expert-verified ground truth
    topic           TEXT        NOT NULL DEFAULT '',    -- free-text tag
    active          BOOLEAN     NOT NULL DEFAULT TRUE,  -- soft-disable without delete
    approved        BOOLEAN     NOT NULL DEFAULT FALSE, -- TRUE = approved-as-correct path
    embedding       FLOAT8[]    DEFAULT NULL,           -- nomic-embed-text 768-dim vector
    embedding_model TEXT        DEFAULT NULL            -- model used for the embedding
);

CREATE INDEX IF NOT EXISTS idx_guardrails_active
    ON aegis_guardrails (active);

CREATE INDEX IF NOT EXISTS idx_guardrails_topic
    ON aegis_guardrails (topic)
    WHERE topic <> '';

CREATE INDEX IF NOT EXISTS idx_guardrails_created
    ON aegis_guardrails (created_at DESC);
"""


def ensure_table() -> None:
    """Create the table and indexes if they don't already exist (idempotent)."""
    from ..db_write import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_SQL)
        conn.commit()
    print("[guardrails migration] aegis_guardrails table ready.")


if __name__ == "__main__":
    ensure_table()
