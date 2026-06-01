from app.engine.types import Signal


def base_risk(node_id: str, signals: list[Signal], criticality: float = 0.5) -> float:
    """Per-node risk r(n) from severity/criticality (§5.2).
    risk = criticality * max(signal_severity for signals observing this node)."""
    sev_map = {"high": 0.9, "med": 0.6, "low": 0.3}
    max_sev = 0.0
    for s in signals:
        if s.observes == node_id:
            max_sev = max(max_sev, sev_map.get(s.severity_raw, 0.3))
    if max_sev == 0.0:
        return 0.0
    return round(criticality * max_sev, 3)
