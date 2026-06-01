from app.engine.types import Signal


def zscore(value: float, baseline: float) -> float:
    """Compute a simplified z-score (deviation from baseline)."""
    if baseline == 0:
        return abs(value)
    return abs(value - baseline) / max(abs(baseline) * 0.1, 0.01)


def flag_anomalies(signals: list[Signal], threshold: float = 3.0) -> list[str]:
    """Return signal IDs whose value deviates significantly from baseline."""
    flagged = []
    for s in signals:
        z = zscore(s.value, s.baseline)
        if z >= threshold:
            flagged.append(s.id)
    return flagged
