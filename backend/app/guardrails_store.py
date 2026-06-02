"""
Guardrails store — PostgreSQL-backed correction log for the Expert Chat feature.

Each guardrail is a domain-expert-validated fact: either a correction (expert
saw a wrong model answer and provided the right one) or an approval (expert
confirmed the model's answer is correct ground truth for the agent swarm).

Primary storage: PostgreSQL ``aegis_guardrails`` table (see migrations/).
Audit log:       ``guardrails.json`` at project root (always written too).
Embeddings:      nomic-embed-text via Ollama (768-dim float8[]).
                 Falls back to keyword scoring if model unavailable.

Public API
----------
save(question, wrong_answer, correct_answer, topic, approved) -> dict
find_relevant(question, n)  -> list[dict]
get_all()                   -> list[dict]
toggle(id, active)          -> dict | None
delete(id)                  -> bool
migrate_from_json()         -> int
"""
from __future__ import annotations

import json
import math
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
GUARDRAILS_JSON_PATH = os.environ.get(
    "GUARDRAILS_PATH",
    os.path.normpath(os.path.join(_HERE, "..", "..", "guardrails.json")),
)

EMBED_BASE_URL = os.environ.get("GEMMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL    = os.environ.get("EMBED_MODEL", "bge-m3")   # multilingual: Arabic + English
EMBED_TIMEOUT  = int(os.environ.get("EMBED_TIMEOUT", "20"))

# ---------------------------------------------------------------------------
# Table bootstrap (idempotent — runs once at import time)
# ---------------------------------------------------------------------------
def _ensure_table() -> None:
    try:
        from backend.app.migrations.create_guardrails_table import ensure_table
        ensure_table()
    except Exception as exc:
        print(f"[guardrails_store] table bootstrap warning: {exc}")

_ensure_table()

# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------
def _embed(text: str) -> Optional[List[float]]:
    """Return embeddings from nomic-embed-text via Ollama, or None on failure."""
    try:
        import urllib.request
        # Try newer /api/embed endpoint first
        payload = json.dumps({"model": EMBED_MODEL, "input": text}).encode()
        req = urllib.request.Request(
            f"{EMBED_BASE_URL}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=EMBED_TIMEOUT) as resp:
            data = json.loads(resp.read())
        embs = data.get("embeddings") or []
        if embs and len(embs[0]) > 0:
            return embs[0]
        # Fallback: older /api/embeddings endpoint
        payload2 = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
        req2 = urllib.request.Request(
            f"{EMBED_BASE_URL}/api/embeddings",
            data=payload2,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=EMBED_TIMEOUT) as resp2:
            data2 = json.loads(resp2.read())
        emb2 = data2.get("embedding") or []
        return emb2 if emb2 else None
    except Exception as exc:
        print(f"[guardrails_store] embed failed ({EMBED_MODEL}): {exc}")
        return None


def _cosine(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# JSON audit-log helpers
# ---------------------------------------------------------------------------
def _json_read() -> List[Dict[str, Any]]:
    try:
        with open(GUARDRAILS_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def _json_write(items: List[Dict[str, Any]]) -> None:
    tmp = GUARDRAILS_JSON_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, GUARDRAILS_JSON_PATH)


def _json_upsert(guardrail: Dict[str, Any]) -> None:
    items = _json_read()
    for i, item in enumerate(items):
        if item.get("id") == guardrail["id"]:
            items[i] = {k: v for k, v in guardrail.items() if k != "embedding"}
            _json_write(items)
            return
    items.append({k: v for k, v in guardrail.items() if k != "embedding"})
    _json_write(items)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(row)
    d.pop("embedding", None)   # never send 768 floats to clients
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].isoformat()
    # ensure bool fields
    d.setdefault("active", True)
    d.setdefault("approved", False)
    return d


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def save(
    question:      str,
    wrong_answer:  str,
    correct_answer: str,
    topic:         str  = "",
    approved:      bool = False,
) -> Dict[str, Any]:
    """Insert a new guardrail, embed it, persist to DB + JSON audit log."""
    from backend.app.db_write import get_conn

    gid = uuid.uuid4().hex
    now = datetime.now(timezone.utc)

    embed_text = f"{question.strip()}\n{correct_answer.strip()}"
    embedding  = _embed(embed_text)
    embed_model = EMBED_MODEL if embedding else None

    guardrail: Dict[str, Any] = {
        "id":            gid,
        "created_at":    now.isoformat(),
        "question":      question.strip(),
        "wrong_answer":  wrong_answer.strip(),
        "correct_answer": correct_answer.strip(),
        "topic":         topic.strip(),
        "active":        True,
        "approved":      approved,
    }

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO aegis_guardrails
                        (id, created_at, question, wrong_answer, correct_answer,
                         topic, active, approved, embedding, embedding_model)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (gid, now, guardrail["question"], guardrail["wrong_answer"],
                     guardrail["correct_answer"], guardrail["topic"],
                     True, approved, embedding, embed_model),
                )
            conn.commit()
    except Exception as exc:
        print(f"[guardrails_store] DB insert failed: {exc}")

    _json_upsert(guardrail)
    return guardrail


def get_all() -> List[Dict[str, Any]]:
    """All guardrails, newest-first (no embedding column)."""
    from backend.app.db_write import fetchall_write
    try:
        rows = fetchall_write(
            """SELECT id, created_at, question, wrong_answer, correct_answer,
                      topic, active, approved, embedding_model
               FROM aegis_guardrails ORDER BY created_at DESC"""
        )
        return [_row_to_dict(r) for r in rows]
    except Exception as exc:
        print(f"[guardrails_store] get_all DB failed: {exc}")
        return sorted(_json_read(), key=lambda r: r.get("created_at", ""), reverse=True)


def find_relevant(question: str, n: int = 5) -> List[Dict[str, Any]]:
    """Top-n active guardrails most relevant to the question.

    Uses cosine similarity on stored embeddings when available;
    falls back to keyword-overlap scoring otherwise.
    """
    from backend.app.db_write import fetchall_write
    try:
        rows = fetchall_write(
            """SELECT id, created_at, question, wrong_answer, correct_answer,
                      topic, active, approved, embedding, embedding_model
               FROM aegis_guardrails WHERE active = TRUE ORDER BY created_at DESC"""
        )
    except Exception as exc:
        print(f"[guardrails_store] find_relevant DB failed: {exc}")
        rows = [r for r in _json_read() if r.get("active", True)]

    if not rows:
        return []

    q_emb = _embed(question)
    results: List[tuple[float, Dict[str, Any]]] = []

    for row in rows:
        g_emb = row.get("embedding")
        if q_emb and g_emb and len(g_emb) == len(q_emb):
            score = _cosine(q_emb, g_emb)
        else:
            q_tok = set(_tokenise(question))
            g_tok = set(_tokenise(row.get("question", "")))
            overlap = len(q_tok & g_tok)
            if overlap == 0:
                continue
            topic  = row.get("topic", "").lower()
            bonus  = 0.5 if topic and topic in question.lower() else 0.0
            score  = overlap + bonus

        if score > 0:
            results.append((score, row))

    results.sort(key=lambda x: x[0], reverse=True)
    return [_row_to_dict(row) for _, row in results[:n]]


def toggle(guardrail_id: str, active: bool) -> Optional[Dict[str, Any]]:
    from backend.app.db_write import fetchone_write, get_conn
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE aegis_guardrails SET active = %s WHERE id = %s",
                    (active, guardrail_id),
                )
            conn.commit()
        row = fetchone_write(
            """SELECT id, created_at, question, wrong_answer, correct_answer,
                      topic, active, approved, embedding_model
               FROM aegis_guardrails WHERE id = %s""",
            (guardrail_id,),
        )
        if row:
            items = _json_read()
            for item in items:
                if item.get("id") == guardrail_id:
                    item["active"] = active
            _json_write(items)
            return _row_to_dict(row)
        return None
    except Exception as exc:
        print(f"[guardrails_store] toggle DB failed: {exc}")
        items = _json_read()
        for item in items:
            if item.get("id") == guardrail_id:
                item["active"] = active
                _json_write(items)
                return item
        return None


def delete(guardrail_id: str) -> bool:
    from backend.app.db_write import get_conn
    deleted_db = False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM aegis_guardrails WHERE id = %s RETURNING id",
                    (guardrail_id,),
                )
                deleted_db = cur.fetchone() is not None
            conn.commit()
    except Exception as exc:
        print(f"[guardrails_store] delete DB failed: {exc}")

    items   = _json_read()
    new     = [i for i in items if i.get("id") != guardrail_id]
    changed = len(new) < len(items)
    if changed:
        _json_write(new)
    return deleted_db or changed


def migrate_from_json() -> int:
    """Import guardrails.json rows into the DB. Skips duplicates. Returns count."""
    from backend.app.db_write import get_conn, fetchall_write

    items = _json_read()
    if not items:
        return 0

    existing = {r["id"] for r in fetchall_write("SELECT id FROM aegis_guardrails")}
    inserted = 0

    for item in items:
        gid = item.get("id")
        if not gid or gid in existing:
            continue
        try:
            ts = datetime.fromisoformat(item.get("created_at", ""))
        except Exception:
            ts = datetime.now(timezone.utc)

        embed_text = f"{item.get('question','')}\n{item.get('correct_answer','')}"
        embedding  = _embed(embed_text)
        embed_model = EMBED_MODEL if embedding else None

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO aegis_guardrails
                               (id, created_at, question, wrong_answer, correct_answer,
                                topic, active, approved, embedding, embedding_model)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (id) DO NOTHING""",
                        (gid, ts,
                         item.get("question",""), item.get("wrong_answer",""),
                         item.get("correct_answer",""), item.get("topic",""),
                         item.get("active", True), item.get("approved", False),
                         embedding, embed_model),
                    )
                conn.commit()
            inserted += 1
            existing.add(gid)
        except Exception as exc:
            print(f"[migrate_from_json] row {gid}: {exc}")

    print(f"[guardrails_store] migrated {inserted}/{len(items)} rows JSON→DB")
    return inserted


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------
def _tokenise(text: str) -> List[str]:
    stop = {"the","a","an","is","in","of","to","and","for","what","how","why",
            "are","was","be","been","i","it","this","that","with",
            "من","في","على","إلى","هل","ما","كيف"}
    tokens = re.split(r"[\s،,.!?؟\"\'()\[\]{}/\\<>:;]+", text.lower())
    return [t for t in tokens if t and len(t) > 2 and t not in stop]
