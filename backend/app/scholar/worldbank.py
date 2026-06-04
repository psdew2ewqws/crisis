"""World Bank Indicators API — numeric facts (not copyrightable). The backbone for
Jordan water/economy time-series. No key; degrade-safe; store {year, value} + source_url."""
from __future__ import annotations

from typing import Any, Dict, List

from . import http_json

BASE = "https://api.worldbank.org/v2"


def indicator(code: str, country: str = "JOR", *, mrv: int = 25) -> List[Dict[str, Any]]:
    """Return [{year, value}] oldest-first for an indicator (e.g. ER.H2O.INTR.PC),
    most-recent `mrv` values. Empty list on any failure."""
    data = http_json(f"{BASE}/country/{country}/indicator/{code}?format=json&per_page=100&mrv={max(1, int(mrv))}")
    if not (isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list)):
        return []
    out: List[Dict[str, Any]] = []
    for row in data[1]:
        v = row.get("value")
        if v is not None:
            try:
                out.append({"year": int(row.get("date")), "value": float(v)})
            except (TypeError, ValueError):
                continue
    return sorted(out, key=lambda x: x["year"])


def source_url(code: str, country: str = "JOR") -> str:
    return f"{BASE}/country/{country}/indicator/{code}?format=json"
