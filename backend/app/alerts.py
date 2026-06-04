"""alerts.py — send crisis alerts as real SMS via the josms.net (Jordan) gateway.

The gateway is called SERVER-SIDE so the account password never reaches the browser,
and credentials come ONLY from the environment (never hard-coded, never committed):

    JOSMS_ACCNAME   gateway account username (fixed)
    JOSMS_ACCPASS   gateway account password (fixed)   ← secret, lives in backend/.env
    JOSMS_SENDER    approved sender id (e.g. "Nexara")

Endpoints:
    GET  /api/alert/balance              remaining SMS credits (read-only)
    POST /api/alert/send  {message, numbers|number}   send one or many (≤120/bulk call)

If the env is not configured the endpoints respond ``configured: false`` (no crash) so the
UI can show a clear "gateway not set up" hint instead of failing silently.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Path

router = APIRouter(tags=["alerts"])

_BASE = "https://www.josms.net"
_UA = "AegisCrisisAlerts/1.0"
_TIMEOUT = 25.0
_BULK_MAX = 120  # gateway caps a bulk call at 120 numbers

# Saved recipient groups (for one-tap bulk "instant send") live in the gitignored data dir.
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_GROUPS_JSON = os.path.join(_DATA_DIR, "alert_recipients.json")


def _cfg() -> Tuple[str, str, str]:
    return (
        (os.environ.get("JOSMS_ACCNAME") or "").strip(),
        (os.environ.get("JOSMS_ACCPASS") or "").strip(),
        (os.environ.get("JOSMS_SENDER") or "").strip(),
    )


def configured() -> bool:
    acc, pwd, sender = _cfg()
    return bool(acc and pwd and sender)


def _http_get(url: str) -> Tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", "replace").strip()
    except urllib.error.HTTPError as e:  # surface the body, don't hide
        body = ""
        try:
            body = e.read().decode("utf-8", "replace").strip()
        except Exception:
            body = str(e)
        return e.code, body
    except Exception as e:
        return 0, str(e)


def normalize_number(raw: str) -> Optional[str]:
    """Normalise a Jordanian mobile to the gateway form 9627XXXXXXXX (12 digits).

    Accepts 07XXXXXXXX, 7XXXXXXXX, +962…, 00962…, 962…. Returns None if it is not a
    valid Jordan mobile (operator prefix must be 77 / 78 / 79).
    """
    d = re.sub(r"\D", "", raw or "")
    if d.startswith("00962"):
        d = d[2:]
    elif d.startswith("962"):
        pass
    elif d.startswith("0") and len(d) == 10:   # 07XXXXXXXX
        d = "962" + d[1:]
    elif len(d) == 9 and d.startswith("7"):     # 7XXXXXXXX
        d = "962" + d
    return d if re.fullmatch(r"962(7[789])\d{7}", d) else None


def _sent_ok(code: int, body: str) -> bool:
    """josms returns a positive numeric message id on success; error codes are
    negative numbers or text. Treat HTTP 200 + (positive int | non-error text) as sent."""
    if code != 200:
        return False
    b = (body or "").strip().strip('"')
    if re.fullmatch(r"-?\d+", b):
        return int(b) > 0
    low = b.lower()
    return bool(b) and not b.startswith("-") and "error" not in low and "fail" not in low


def get_balance() -> Dict[str, Any]:
    acc, pwd, _ = _cfg()
    if not (acc and pwd):
        return {"ok": False, "configured": False, "balance": None,
                "message_ar": "بوابة الرسائل غير مُهيّأة."}
    url = (f"{_BASE}/SMS/API/GetBalance"
           f"?AccName={urllib.parse.quote(acc)}&AccPass={urllib.parse.quote(pwd)}")
    code, body = _http_get(url)
    b = (body or "").strip().strip('"')
    val = int(b) if re.fullmatch(r"\d+", b) else None
    return {"ok": code == 200 and val is not None, "configured": True,
            "balance": val, "raw": body, "http": code}


def send(numbers: List[str], message: str) -> Dict[str, Any]:
    acc, pwd, sender = _cfg()
    if not (acc and pwd and sender):
        return {"ok": False, "configured": False,
                "message_ar": "بوابة الرسائل غير مُهيّأة — أضِف JOSMS_ACCNAME وJOSMS_ACCPASS "
                              "وJOSMS_SENDER إلى backend/.env."}
    msg = (message or "").strip()
    if not msg:
        return {"ok": False, "configured": True, "error": "empty_message",
                "message_ar": "نص التنبيه فارغ."}

    valid: List[str] = []
    invalid: List[str] = []
    for n in numbers:
        v = normalize_number(str(n))
        (valid.append(v) if v else invalid.append(str(n)))
    valid = list(dict.fromkeys(valid))  # dedupe, keep order
    if not valid:
        return {"ok": False, "configured": True, "error": "no_valid_numbers",
                "invalid": invalid,
                "message_ar": "لا يوجد رقم صالح. استخدم صيغة مثل 07XXXXXXXX أو 9627XXXXXXXX."}

    q_msg = urllib.parse.quote(msg, safe="")
    q_acc = urllib.parse.quote(acc)
    q_pwd = urllib.parse.quote(pwd)
    q_send = urllib.parse.quote(sender)
    results: List[Dict[str, Any]] = []

    if len(valid) == 1:
        url = (f"{_BASE}/SMSServices/Clients/Prof/RestSingleSMS_General/SendSMS"
               f"?senderid={q_send}&numbers={valid[0]}&accname={q_acc}&AccPass={q_pwd}&msg={q_msg}")
        code, body = _http_get(url)
        results.append({"numbers": valid, "http": code, "response": body, "ok": _sent_ok(code, body)})
    else:
        for i in range(0, len(valid), _BULK_MAX):
            batch = valid[i:i + _BULK_MAX]
            nums = ",".join(batch) + ","   # gateway expects a trailing comma
            url = (f"{_BASE}/sms/api/SendBulkMessages.cfm"
                   f"?numbers={nums}&senderid={q_send}&AccName={q_acc}&AccPass={q_pwd}"
                   f"&msg={q_msg}&requesttimeout=5000000")
            code, body = _http_get(url)
            results.append({"numbers": batch, "http": code, "response": body, "ok": _sent_ok(code, body)})

    ok = bool(results) and all(r["ok"] for r in results)
    sent_count = sum(len(r["numbers"]) for r in results if r["ok"])
    return {
        "ok": ok, "configured": True,
        "sent_to": valid, "sent_count": sent_count, "invalid": invalid,
        "results": results,
        "message_ar": (f"تم إرسال التنبيه إلى {sent_count} رقم."
                       if ok else "تعذّر الإرسال — راجع رد البوابة أدناه."),
    }


# --------------------------------------------------------------------------- #
# Saved recipient groups — name + numbers, for one-tap bulk "instant send".    #
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _gid(name: str) -> str:
    """Deterministic id so re-saving the same name overwrites that group."""
    return "grp:" + hashlib.sha256((name or "").strip().lower().encode("utf-8")).hexdigest()[:12]


def groups_load() -> List[Dict[str, Any]]:
    try:
        with open(_GROUPS_JSON, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def groups_save(rows: List[Dict[str, Any]]) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_GROUPS_JSON, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)


def group_upsert(name: str, numbers: List[str]) -> Dict[str, Any]:
    valid: List[str] = []
    invalid: List[str] = []
    for n in numbers:
        v = normalize_number(str(n))
        (valid.append(v) if v else invalid.append(str(n)))
    valid = list(dict.fromkeys(valid))
    rec = {"id": _gid(name), "name": (name or "").strip(),
           "numbers": valid, "count": len(valid), "ts": _now_iso()}
    rows = [r for r in groups_load() if r.get("id") != rec["id"]]
    rows.insert(0, rec)
    groups_save(rows)
    return {"group": rec, "invalid": invalid}


def group_delete(gid: str) -> bool:
    rows = groups_load()
    kept = [r for r in rows if r.get("id") != gid]
    if len(kept) == len(rows):
        return False
    groups_save(kept)
    return True


@router.get("/api/alert/balance")
def alert_balance() -> Dict[str, Any]:
    return get_balance()


@router.post("/api/alert/send")
def alert_send(body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    message = str(body.get("message") or "")
    raw = body.get("numbers", body.get("number"))
    if isinstance(raw, str):
        raw = re.split(r"[,\s;]+", raw)
    numbers = [str(n).strip() for n in (raw or []) if str(n).strip()]
    # Optional: resolve a saved group's numbers server-side (one-tap instant send).
    gid = str(body.get("group_id") or "").strip()
    if gid:
        grp = next((g for g in groups_load() if g.get("id") == gid), None)
        if grp:
            numbers = list(dict.fromkeys(numbers + (grp.get("numbers") or [])))
    if not numbers:
        return {"ok": False, "configured": configured(), "error": "no_numbers",
                "message_ar": "أدخل رقم هاتف واحدًا على الأقل أو اختر مجموعة."}
    return send(numbers, message)


@router.get("/api/alert/groups")
def alert_groups() -> Dict[str, Any]:
    return {"groups": groups_load()}


@router.post("/api/alert/groups")
def alert_group_save(body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    name = str(body.get("name") or "").strip()
    raw = body.get("numbers")
    if isinstance(raw, str):
        raw = re.split(r"[,\s;]+", raw)
    numbers = [str(n).strip() for n in (raw or []) if str(n).strip()]
    if not name:
        return {"ok": False, "error": "name_required", "message_ar": "أدخل اسمًا للمجموعة."}
    if not numbers:
        return {"ok": False, "error": "no_numbers", "message_ar": "أضِف رقمًا واحدًا على الأقل."}
    res = group_upsert(name, numbers)
    if not res["group"]["numbers"]:
        return {"ok": False, "error": "no_valid_numbers", "invalid": res["invalid"],
                "message_ar": "لا يوجد رقم صالح في القائمة."}
    return {"ok": True, **res}


@router.delete("/api/alert/groups/{gid}")
def alert_group_delete(gid: str = Path(...)) -> Dict[str, Any]:
    return {"ok": group_delete(gid)}
