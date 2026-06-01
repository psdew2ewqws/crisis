from app.engine.types import Signal


def validate_and_ingest(repos, raw: dict) -> Signal:
    """Validate, normalize, and persist a signal."""
    sig = Signal(
        id=raw.get("id", f"SIG-{len(repos.signals.list()) + 1}"),
        observes=raw["observes"],
        metric=raw["metric"],
        value=raw["value"],
        baseline=raw.get("baseline", 0.0),
        t_offset_s=raw.get("t_offset_s", 0),
        severity_raw=raw.get("severity_raw", "low"),
    )
    repos.signals.add(sig)
    return sig
