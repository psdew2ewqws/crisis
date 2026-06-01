"""LLM narration node for the AEGIS crisis brain — a LOCAL-model client.

Design contract: docs/D-llm.md (Track 3 — "LLM reasoning + valid solution").

This is the *optional* narration layer of the Deer Graph. It turns the
deterministic, graph-derived evidence (ranked ``ril_problem_clusters`` root
causes, recovered signal counts, the operator recommendation) into a short
natural-language operator brief. Per the AEGIS gap analysis, **the LLM only
ever narrates graph-derived evidence — it is never the source of the causal
claim.** Every fact it is given comes from real voc360 rows.

There is **NO hosted API key in this environment** (no OpenAI / Anthropic), so
this module talks to a *local* model only:

  * ``LLM_BASE_URL`` (default ``http://localhost:11434``) — an Ollama server or
    any OpenAI-compatible ``/v1/chat/completions`` endpoint on localhost.
  * ``LLM_MODEL``    (default ``llama3.1``)               — the model tag/name.
  * ``LLM_TIMEOUT``  (default ``8`` seconds)              — hard wall so a slow
    or absent server never blocks the ``/api/flow/run`` stream.

Transport is **stdlib ``urllib`` only** — no ``requests``, no SDK, no extra
deps — so the module is import-safe everywhere. If the local server is
unreachable, returns an error, or is simply not running, :func:`narrate`
silently falls back to a **grounded deterministic summary** built from the same
context dict, so the narration node always returns usable Arabic-aware text.

Public surface (consumed by ``deer_flow`` and ``main.py``):

    narrate(prompt, context) -> str        # the one entry point
    available() -> bool                    # is a local LLM reachable?
    grounded_summary(context) -> str       # the deterministic fallback (no net)
    health() -> dict                       # {available, base_url, model, ...}

All text is UTF-8 / Arabic-safe; callers serialize with ``ensure_ascii=False``.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

# --- optional .env loading, mirrored from db.py so config is consistent ----
try:  # pragma: no cover - dotenv is optional
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:  # pragma: no cover
    pass


# ===========================================================================
# Configuration (env-driven; all have safe localhost defaults).
# ===========================================================================
def _env(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


LLM_BASE_URL = _env("LLM_BASE_URL", "http://localhost:11434").rstrip("/")
LLM_MODEL = _env("LLM_MODEL", "llama3.1")
try:
    LLM_TIMEOUT = float(_env("LLM_TIMEOUT", "8"))
except Exception:  # pragma: no cover - defensive
    LLM_TIMEOUT = 8.0
# Keep generations short — this is a brief, not an essay.
try:
    LLM_MAX_TOKENS = int(_env("LLM_MAX_TOKENS", "320"))
except Exception:  # pragma: no cover
    LLM_MAX_TOKENS = 320

# System framing: bound the model to *narrate the given evidence only*.
SYSTEM_PROMPT = (
    "You are AEGIS, a crisis-operations analyst for Jordanian public services. "
    "You are given graph-derived evidence (ranked root-cause clusters with "
    "citizen-report counts and severity, plus recovered signal counts) that has "
    "ALREADY been computed deterministically. Your job is ONLY to narrate that "
    "evidence into a crisp operator brief. Do NOT invent facts, numbers, "
    "services, or causes that are not in the evidence. Be concise (4-6 "
    "sentences). Arabic service or cluster labels may appear verbatim; keep "
    "them as given. State the dominant root cause, why it ranks first, and the "
    "single recommended action."
)


# ===========================================================================
# Low-level HTTP (stdlib urllib only).
# ===========================================================================
def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> Optional[Dict[str, Any]]:
    """POST a JSON body and parse a JSON reply, or return None on any failure.

    Never raises — a missing/slow/broken local server must degrade to the
    grounded fallback, not blow up the caller's flow.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
        return json.loads(raw)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None
    except Exception:  # pragma: no cover - belt-and-braces; never propagate
        return None


def _extract_text(reply: Dict[str, Any]) -> str:
    """Pull the generated text out of either an Ollama or OpenAI-style reply."""
    if not isinstance(reply, dict):
        return ""
    # Ollama /api/chat -> {"message": {"content": "..."}}
    msg = reply.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
        return msg["content"].strip()
    # Ollama /api/generate -> {"response": "..."}
    if isinstance(reply.get("response"), str):
        return reply["response"].strip()
    # OpenAI-compatible /v1/chat/completions -> {"choices":[{"message":{"content"}}]}
    choices = reply.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] or {}
        cmsg = first.get("message") if isinstance(first, dict) else None
        if isinstance(cmsg, dict) and isinstance(cmsg.get("content"), str):
            return cmsg["content"].strip()
        # legacy completion shape -> {"choices":[{"text": "..."}]}
        if isinstance(first, dict) and isinstance(first.get("text"), str):
            return first["text"].strip()
    return ""


def _try_ollama_chat(messages: List[Dict[str, str]]) -> Optional[str]:
    """Native Ollama chat endpoint (``/api/chat``, non-streaming)."""
    out = _post_json(
        f"{LLM_BASE_URL}/api/chat",
        {
            "model": LLM_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": LLM_MAX_TOKENS},
        },
        LLM_TIMEOUT,
    )
    if out is None:
        return None
    text = _extract_text(out)
    return text or None


def _try_openai_chat(messages: List[Dict[str, str]]) -> Optional[str]:
    """OpenAI-compatible endpoint (``/v1/chat/completions``), as exposed by
    Ollama's compat layer, llama.cpp ``server``, LM Studio, vLLM, etc."""
    out = _post_json(
        f"{LLM_BASE_URL}/v1/chat/completions",
        {
            "model": LLM_MODEL,
            "messages": messages,
            "stream": False,
            "temperature": 0.2,
            "max_tokens": LLM_MAX_TOKENS,
        },
        LLM_TIMEOUT,
    )
    if out is None:
        return None
    text = _extract_text(out)
    return text or None


# ===========================================================================
# Context rendering — turn the evidence dict into a compact, grounded prompt.
# ===========================================================================
def _fmt_root_causes(rcs: List[Dict[str, Any]], limit: int = 5) -> List[str]:
    """Render ranked root causes (rootcause.rank_root_causes shape) as lines.

    Real columns only: label_en/label_ar, members (member_count), severity_avg,
    score, optional signal_count recovered by the text linker.
    """
    lines: List[str] = []
    for rc in (rcs or [])[:limit]:
        if not isinstance(rc, dict):
            continue
        label = rc.get("label_en") or rc.get("label_ar") or rc.get("cluster_id") or "cluster"
        rank = rc.get("rank", len(lines) + 1)
        members = rc.get("members", rc.get("member_count", 0))
        sev = rc.get("severity_avg", 0)
        bits = [f"{members} reports", f"severity {sev}"]
        sig = rc.get("signal_count")
        if sig is not None:
            bits.append(f"{sig} recovered signals")
        score = rc.get("score")
        if score is not None:
            bits.append(f"score {score}")
        lines.append(f"  {rank}. {label} — {', '.join(str(b) for b in bits)}")
    return lines


def build_context_block(context: Optional[Dict[str, Any]]) -> str:
    """Serialize the evidence dict into a tight, human-readable block.

    Accepts the loose shape produced by deer_flow / rootcause / graph_builder:
        {case, signal_stats|stats, root_causes, recommendation}
    Any subset is fine; missing pieces are simply omitted.
    """
    context = context or {}
    parts: List[str] = []

    case = context.get("case")
    parts.append(f"CASE: {case if case else 'all services (national view)'}")

    stats = context.get("signal_stats") or context.get("stats") or {}
    if isinstance(stats, dict) and stats:
        signals = stats.get("signals")
        services = stats.get("services")
        sources = stats.get("sources")
        clusters = stats.get("clusters")
        real_links = stats.get("real_links")
        sline = []
        if signals is not None:
            sline.append(f"{signals} signals")
        if services is not None:
            sline.append(f"{services} services")
        if sources is not None:
            sline.append(f"{sources} sources")
        if clusters is not None:
            sline.append(f"{clusters} root-cause clusters")
        if real_links is not None:
            sline.append(f"{real_links} signals linked to clusters by text")
        if sline:
            parts.append("SIGNAL GRAPH: " + ", ".join(sline) + ".")

    rcs = context.get("root_causes") or context.get("rootcauses") or []
    rc_lines = _fmt_root_causes(rcs)
    if rc_lines:
        parts.append("RANKED ROOT CAUSES (ril_problem_clusters):")
        parts.extend(rc_lines)
        evidence = (rcs[0] or {}).get("evidence") if rcs else None
        if isinstance(evidence, list) and evidence:
            sample = str(evidence[0])[:160]
            parts.append(f"SAMPLE CITIZEN SEGMENT (top cluster): {sample}")

    rec = context.get("recommendation")
    if isinstance(rec, str) and rec.strip():
        parts.append(f"DETERMINISTIC RECOMMENDATION: {rec.strip()}")

    return "\n".join(parts)


# ===========================================================================
# Grounded deterministic fallback (no network — always works).
# ===========================================================================
def grounded_summary(context: Optional[Dict[str, Any]]) -> str:
    """Synthesize an operator brief from the evidence dict WITHOUT any model.

    This is the load-bearing fallback: it reads the exact same real voc360
    fields the prompt would, so the narration node stays grounded and useful
    even when no local LLM is running. Deterministic, side-effect free.
    """
    context = context or {}
    rcs = context.get("root_causes") or context.get("rootcauses") or []
    stats = context.get("signal_stats") or context.get("stats") or {}
    case = context.get("case")
    scope = case if case else "the national VOC graph"

    if not rcs:
        sig = stats.get("signals") if isinstance(stats, dict) else None
        head = f"Across {sig} citizen signals, " if sig else ""
        return (
            f"{head}no root-cause cluster cleared the ranking threshold for "
            f"{scope}. Keep ingesting signals from the_data and re-run the "
            f"root-cause pass once a dominant cluster emerges."
        )

    top = rcs[0] if isinstance(rcs[0], dict) else {}
    label = top.get("label_en") or top.get("label_ar") or top.get("cluster_id") or "the dominant cluster"
    members = top.get("members", top.get("member_count", 0))
    sev = top.get("severity_avg", 0)
    sig_count = top.get("signal_count")

    sentences: List[str] = []
    lead = (
        f"For {scope}, the dominant root cause is '{label}', the highest-ranked "
        f"of {len(rcs)} problem clusters with {members} citizen reports "
        f"(avg severity {sev})."
    )
    if sig_count is not None:
        lead = lead[:-1] + f" and {sig_count} signals recovered to it by text-match."
    sentences.append(lead)

    if len(rcs) > 1 and isinstance(rcs[1], dict):
        nxt = rcs[1]
        nlabel = nxt.get("label_en") or nxt.get("label_ar") or "the next cluster"
        nmem = nxt.get("members", nxt.get("member_count", 0))
        sentences.append(
            f"It outranks the next cause, '{nlabel}' ({nmem} reports), so it "
            f"carries the most concentrated citizen harm right now."
        )

    if isinstance(stats, dict):
        services = stats.get("services")
        sources = stats.get("sources")
        if services and sources:
            sentences.append(
                f"The supporting signal graph spans {services} services and "
                f"{sources} data sources."
            )

    rec = context.get("recommendation")
    if isinstance(rec, str) and rec.strip():
        sentences.append(rec.strip())
    else:
        sentences.append(
            f"Recommended action: route '{label}' to its owning agency, brief "
            f"the service team, and track whether complaint volume on this "
            f"cluster falls after intervention."
        )

    return " ".join(sentences)


# ===========================================================================
# Reachability probe.
# ===========================================================================
def available() -> bool:
    """Best-effort check that a local LLM server is reachable.

    Tries Ollama's ``/api/tags`` (cheap, lists models); on failure tries the
    OpenAI-compatible ``/v1/models``. Uses a short timeout and never raises.
    """
    short = min(LLM_TIMEOUT, 3.0)
    for path in ("/api/tags", "/v1/models"):
        try:
            req = urllib.request.Request(f"{LLM_BASE_URL}{path}", method="GET")
            with urllib.request.urlopen(req, timeout=short) as resp:
                if 200 <= getattr(resp, "status", 200) < 500:
                    return True
        except Exception:
            continue
    return False


def health() -> dict:
    """Report the narration node's config + live reachability (for /api/health)."""
    return {
        "available": available(),
        "base_url": LLM_BASE_URL,
        "model": LLM_MODEL,
        "timeout_s": LLM_TIMEOUT,
        "fallback": "grounded_summary",
    }


# ===========================================================================
# Public entry point.
# ===========================================================================
def narrate(prompt: str = "", context: Optional[Dict[str, Any]] = None) -> str:
    """Narrate graph-derived evidence into an operator brief.

    Builds a grounded prompt from ``context`` (the evidence dict produced by the
    Deer Graph), asks the LOCAL model (Ollama native, then OpenAI-compatible),
    and returns its text. If the local server is unreachable / errors / times
    out, returns :func:`grounded_summary` — a deterministic brief built from the
    same real voc360 fields, so this function ALWAYS returns usable text.

    Args:
        prompt:  Optional extra instruction from the caller (e.g. the stage
                 detail or an operator question). May be empty.
        context: The evidence dict: ``{case, signal_stats|stats, root_causes,
                 recommendation}``. Any subset is accepted.

    Returns:
        A short UTF-8 / Arabic-safe narration string (never empty, never raises).
    """
    context = context or {}
    evidence = build_context_block(context)
    fallback = grounded_summary(context)

    user_msg = "EVIDENCE (graph-derived, voc360):\n" + evidence
    if prompt and prompt.strip():
        user_msg += f"\n\nOPERATOR REQUEST: {prompt.strip()}"
    user_msg += (
        "\n\nWrite the operator brief now, narrating ONLY the evidence above."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    # Try native Ollama first, then the OpenAI-compatible shape. Any single
    # transport failure simply moves on; total failure -> grounded fallback.
    for transport in (_try_ollama_chat, _try_openai_chat):
        try:
            text = transport(messages)
        except Exception:  # pragma: no cover - transports already swallow errors
            text = None
        if text:
            return text.strip()

    return fallback


__all__ = [
    "narrate",
    "available",
    "health",
    "grounded_summary",
    "build_context_block",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_TIMEOUT",
    "SYSTEM_PROMPT",
]


# ===========================================================================
# Manual smoke test — exercises the grounded fallback with no network.
# ===========================================================================
if __name__ == "__main__":  # pragma: no cover
    demo = {
        "case": "Sanad",
        "signal_stats": {"signals": 15800, "services": 8, "sources": 6, "clusters": 20, "real_links": 1180},
        "root_causes": [
            {
                "rank": 1,
                "cluster_id": "c0001",
                "label_en": "National-Aid-Fund support delays",
                "label_ar": "تأخير دعم صندوق المعونة",
                "members": 551,
                "severity_avg": 0.62,
                "score": 612.0,
                "signal_count": 41,
                "evidence": ["تأخير صرف المعونة لأكثر من شهرين دون إشعار"],
            },
            {
                "rank": 2,
                "cluster_id": "c0002",
                "label_en": "Urgent-service fees",
                "label_ar": "رسوم الخدمة المستعجلة",
                "members": 69,
                "severity_avg": 0.55,
            },
        ],
        "recommendation": "Prioritise 'National-Aid-Fund support delays' (551 reports).",
    }
    print("health:", json.dumps(health(), ensure_ascii=False))
    print("\n--- narrate() (local model if up, else grounded) ---")
    print(narrate("Summarize the crisis for the operator.", demo))
    print("\n--- grounded_summary() (always deterministic) ---")
    print(grounded_summary(demo))
