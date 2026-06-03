"""Legal scholarly + open-data clients — the lawful replacement for any paywall-
circumvention source. STDLIB urllib only (matches llm.py's 'no requests' convention).

Every client is DEGRADE-SAFE: any error, timeout, rate-limit, or missing key returns an
empty/None result so the research agent ABSTAINS rather than fabricates — and the whole
layer works with Ollama DOWN (it is pure HTTP + parsing, no LLM in the loop).

Honest identification: we send a real contact User-Agent (never a spoofed browser UA) and
respect each source's polite-pool / rate conventions. No Cloudflare bypass, no scraping of
anti-bot-protected pages — only documented public APIs.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

CONTACT = os.environ.get("RESEARCH_CONTACT", "os.zoned@gmail.com")
UA = os.environ.get("RESEARCH_UA", f"AegisCrisisManager/1.0 (+contact: {CONTACT})")
_TIMEOUT = float(os.environ.get("RESEARCH_HTTP_TIMEOUT", "8"))


def http_json(url: str, *, timeout: Optional[float] = None, headers: Optional[dict] = None) -> Optional[Any]:
    """GET and parse JSON. Returns the parsed object on 2xx, or None on ANY failure
    (network, timeout, non-2xx, bad JSON) — degrade-safe by contract."""
    try:
        req = urllib.request.Request(
            url, method="GET",
            headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})},
        )
        with urllib.request.urlopen(req, timeout=timeout or _TIMEOUT) as r:
            if 200 <= getattr(r, "status", 200) < 300:
                return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None
    return None
