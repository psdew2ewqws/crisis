"""
Expert Chat — Gemma 4 chat interface with guardrail injection.

Endpoints (mounted via FastAPI router):
  POST /api/expert/chat          body: {message, history?, topic?}
  POST /api/expert/guardrail     body: {question, wrong_answer, correct_answer, topic?}
  GET  /api/expert/guardrails    query: active_only=true|false
  PATCH /api/expert/guardrails/{id}  body: {active: bool}
  DELETE /api/expert/guardrails/{id}
  GET  /api/expert/health        liveness + model reachability

Model transport:
  Uses the same Ollama-compatible ``/v1/chat/completions`` or Ollama native
  ``/api/chat`` endpoint as llm.py.  Configure via:
    GEMMA_BASE_URL  (default: same LLM_BASE_URL, i.e. http://localhost:11434)
    GEMMA_MODEL     (default: kimi-k2.5:cloud)  ← Kimi K2.5 via Ollama Pro cloud;
                                                  set to any local tag to run offline
    LLM_THINK       (default: false)            ← instant vs thinking mode (Kimi K2.5)
    GEMMA_TIMEOUT   (default: 30s)              ← generous; covers the cloud round-trip

  The module is import-safe and falls back to a deterministic response when the
  model server is unreachable so the UI always returns something useful.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Path, Query

from . import guardrails_store as gs

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


GEMMA_BASE_URL = _env("GEMMA_BASE_URL", _env("LLM_BASE_URL", "http://localhost:11434")).rstrip("/")
# Chat model. Default is LOCAL-first (gemma4:26b) so the swarm works out of the box
# without a cloud subscription; ``_resolve_model`` below auto-falls-back to whatever
# local model IS pulled if this exact tag is absent. Set GEMMA_MODEL to override.
GEMMA_MODEL = _env("GEMMA_MODEL", "gemma4:26b")
# Keep the loaded model warm between the ~20-40 serial swarm calls (avoids the
# multi-second cold reload of a 26B model that made deliberation look "stuck").
GEMMA_KEEP_ALIVE = _env("GEMMA_KEEP_ALIVE", "30m")
# Thinking-model toggle. false = instant mode → answer text only.
LLM_THINK = _env("LLM_THINK", "false").strip().lower() in ("1", "true", "yes", "on")
try:
    GEMMA_TIMEOUT = float(_env("GEMMA_TIMEOUT", "120"))
except Exception:
    GEMMA_TIMEOUT = 120.0

# Cache the local /api/tags list briefly so model resolution adds no per-call latency.
_TAGS_CACHE: Dict[str, Any] = {"ts": 0.0, "models": []}
_MODEL_PREF = ("gemma", "qwen", "llama", "mistral", "phi", "deepseek")


def _local_models() -> List[str]:
    import time
    now = time.monotonic()
    if now - _TAGS_CACHE["ts"] < 30:
        return _TAGS_CACHE["models"]
    models: List[str] = []
    try:
        req = urllib.request.Request(f"{GEMMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        models = [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception:
        models = []
    _TAGS_CACHE.update(ts=now, models=models)
    return models


def _resolve_model() -> str:
    """Use GEMMA_MODEL if it is actually pulled locally; otherwise (e.g. a ':cloud'
    tag with no subscription) fall back to whatever capable local model IS available."""
    local = _local_models()
    if not local or GEMMA_MODEL in local:
        return GEMMA_MODEL
    for pref in _MODEL_PREF:
        for m in local:
            if pref in m.lower():
                return m
    return local[0]

SYSTEM_PROMPT = """\
You are AEGIS Expert Assistant, a domain intelligence aide for the AEGIS water-crisis \
and citizen-services analytics platform. You help domain experts interpret data from \
voc360: citizen complaint signals, root-cause clusters, service performance trends, \
and forecasts.

Rules:
- Be concise and factual. If you do not know, say so clearly.
- When guardrails are provided below, treat them as authoritative ground truth that \
  MUST override any conflicting prior knowledge.
- Always cite which guardrail you are applying if one is relevant.
- Respond in the same language as the user's question (Arabic or English).
"""


# ---------------------------------------------------------------------------
# Low-level HTTP (stdlib only — no extra deps)
# ---------------------------------------------------------------------------
def _post_json(url: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=GEMMA_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
        return json.loads(raw)
    except Exception:
        return None


def _extract_text(reply: Optional[Dict[str, Any]]) -> str:
    if not reply or not isinstance(reply, dict):
        return ""
    # Ollama /api/chat native
    msg = reply.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
        return msg["content"].strip()
    # OpenAI-compatible /v1/chat/completions
    choices = reply.get("choices")
    if isinstance(choices, list) and choices:
        m = choices[0].get("message") or choices[0].get("delta") or {}
        if isinstance(m.get("content"), str):
            return m["content"].strip()
    return ""


def _is_ollama_native() -> bool:
    """Heuristic: if base URL has no /v1 path we assume native Ollama."""
    return "/v1" not in GEMMA_BASE_URL


def _call_model(messages: List[Dict[str, str]], num_predict: int = 512) -> tuple[str, bool]:
    """Call Gemma model; returns (text, model_available).
    ``num_predict`` caps the generated length (callers that need a longer, complete
    answer — e.g. a full report section — pass a higher budget).
    Falls back to offline message if unreachable."""
    model = _resolve_model()
    if _is_ollama_native():
        url = f"{GEMMA_BASE_URL}/api/chat"
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": LLM_THINK,
            "keep_alive": GEMMA_KEEP_ALIVE,
            "options": {"num_predict": num_predict, "temperature": 0.3},
        }
    else:
        url = f"{GEMMA_BASE_URL}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": num_predict,
            "temperature": 0.3,
        }

    reply = _post_json(url, payload)
    text = _extract_text(reply)
    if text:
        return text, True
    return (
        f"⚠️ The chat model server is not reachable right now. "
        f"Start Ollama and run `ollama pull {GEMMA_MODEL}` (Ollama Pro is required for "
        f"`:cloud` tags) to enable AI responses. "
        "Your guardrails are still being saved and will take effect once the model is available.",
        False,
    )


def model_available() -> bool:
    """A usable model exists = at least one local model is pulled (Ollama up). Honest:
    a ':cloud' tag with no local models returns False, so callers degrade deterministically
    instead of looping on empty cloud responses (the old check returned True for any tag)."""
    return bool(_local_models())


# ---------------------------------------------------------------------------
# Chat logic
# ---------------------------------------------------------------------------
def chat(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    topic: str = "",
) -> Dict[str, Any]:
    """Run a chat turn.  Returns dict with answer, guardrails_applied, model_ok."""
    message = message.strip()
    if not message:
        return {"answer": "Please type a question.", "guardrails_applied": [], "model_ok": False}

    # 0. Guardrails gateway — fail-closed on harm / out-of-scope / out-of-jurisdiction,
    #    redact PII before the message ever reaches the model.
    try:
        from . import guardrails_gateway as _guard
        _rail = _guard.input_rail(message)
        if _rail["action"] in ("refuse", "abstain"):
            return {"answer": _rail["reason_ar"], "refused": True,
                    "guardrails_applied": [{"rail": _rail["reason"]}], "model_ok": False}
        message = _guard.redact_pii(_rail["cleaned"] or message)
    except Exception:
        pass

    # 1. Find relevant guardrails
    relevant = gs.find_relevant(message, n=5)
    guardrail_block = ""
    if relevant:
        lines = ["--- DOMAIN EXPERT GUARDRAILS (treat as ground truth) ---"]
        for i, g in enumerate(relevant, 1):
            lines.append(
                f"{i}. Q: {g['question']}\n   CORRECT ANSWER: {g['correct_answer']}"
            )
        lines.append("--- END GUARDRAILS ---")
        guardrail_block = "\n".join(lines)

    # 2. Build message list
    system = SYSTEM_PROMPT
    if guardrail_block:
        system = system + "\n\n" + guardrail_block

    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]

    # inject conversation history (cap at last 10 turns for context window)
    for turn in (history or [])[-10:]:
        role = turn.get("role", "user")
        if role in ("user", "assistant") and turn.get("content"):
            messages.append({"role": role, "content": turn["content"]})

    messages.append({"role": "user", "content": message})

    # 3. Call model
    answer, model_ok = _call_model(messages)

    return {
        "answer": answer,
        "guardrails_applied": [
            {"id": g["id"], "topic": g.get("topic", ""), "question": g["question"]}
            for g in relevant
        ],
        "model_ok": model_ok,
        "model": GEMMA_MODEL,
    }


# ---------------------------------------------------------------------------
# FastAPI router
# ---------------------------------------------------------------------------
router = APIRouter(tags=["expert"])


@router.post("/api/expert/chat")
def expert_chat_endpoint(body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    message = str(body.get("message") or "").strip()
    history = body.get("history") or []
    topic = str(body.get("topic") or "")
    if not message:
        return {"ok": False, "error": "message is required"}
    result = chat(message, history=history, topic=topic)
    return {"ok": True, **result}


@router.post("/api/expert/guardrail")
def save_guardrail(body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    question = str(body.get("question") or "").strip()
    wrong = str(body.get("wrong_answer") or "").strip()
    correct = str(body.get("correct_answer") or "").strip()
    topic = str(body.get("topic") or "").strip()
    if not question or not correct:
        return {"ok": False, "error": "question and correct_answer are required"}
    approved = bool(body.get("approved", not bool(wrong)))  # no wrong_answer => approved path
    guardrail = gs.save(question=question, wrong_answer=wrong, correct_answer=correct, topic=topic, approved=approved)
    return {"ok": True, "guardrail": guardrail}


@router.get("/api/expert/guardrails")
def list_guardrails(active_only: bool = Query(False)) -> Dict[str, Any]:
    items = gs.get_all()
    if active_only:
        items = [i for i in items if i.get("active", True)]
    return {"ok": True, "guardrails": items, "count": len(items)}


@router.patch("/api/expert/guardrails/{guardrail_id}")
def toggle_guardrail(
    guardrail_id: str = Path(...),
    body: Dict[str, Any] = Body(default={}),
) -> Dict[str, Any]:
    active = bool(body.get("active", True))
    updated = gs.toggle(guardrail_id, active)
    if not updated:
        return {"ok": False, "error": "guardrail not found"}
    return {"ok": True, "guardrail": updated}


@router.delete("/api/expert/guardrails/{guardrail_id}")
def delete_guardrail(guardrail_id: str = Path(...)) -> Dict[str, Any]:
    deleted = gs.delete(guardrail_id)
    return {"ok": deleted, "error": None if deleted else "guardrail not found"}


@router.post("/api/expert/guardrails/migrate")
def migrate_guardrails() -> Dict[str, Any]:
    """Import existing guardrails.json rows into the DB (idempotent)."""
    try:
        n = gs.migrate_from_json()
        return {"ok": True, "migrated": n}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/api/expert/health")
def expert_health() -> Dict[str, Any]:
    ok = model_available()
    guardrails = gs.get_all()
    return {
        "ok": True,
        "model": GEMMA_MODEL,
        "model_available": ok,
        "base_url": GEMMA_BASE_URL,
        "embed_model": gs.EMBED_MODEL,
        "guardrails_count": len(guardrails),
        "active_guardrails": sum(1 for g in guardrails if g.get("active", True)),
        "approved_guardrails": sum(1 for g in guardrails if g.get("approved", False)),
        "guardrails_json": gs.GUARDRAILS_JSON_PATH,
    }
