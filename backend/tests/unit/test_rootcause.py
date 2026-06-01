from app.engine.rootcause.layer_a import rank_root_causes
from app.engine.types import Signal


def test_apex_is_pipe_not_911(cdg, seed):
    """Tech Spec §4.1: root cause is PIPE-ZN-44, not the loud 911 surge."""
    sigs = [
        Signal(
            id=s["id"], observes=s["observes"], metric=s["metric"],
            value=s["value"], baseline=s["baseline"], t_offset_s=s["t_offset_s"],
            severity_raw=s["severity_raw"],
        )
        for s in seed["signals"] if not s.get("unrelated")
    ]
    res = rank_root_causes(cdg, sigs)
    assert res.likely_cause == "PIPE-ZN-44"
    ids = [h.node_id for h in res.hypotheses]
    # PIPE-ZN-44 must rank higher than COMMS-911 (loud != causal)
    assert ids.index("PIPE-ZN-44") < ids.index("COMMS-911") if "COMMS-911" in ids else True


def test_confidence_is_high(cdg, seed):
    sigs = [
        Signal(
            id=s["id"], observes=s["observes"], metric=s["metric"],
            value=s["value"], baseline=s["baseline"], t_offset_s=s["t_offset_s"],
            severity_raw=s["severity_raw"],
        )
        for s in seed["signals"] if not s.get("unrelated")
    ]
    res = rank_root_causes(cdg, sigs)
    assert res.confidence > 0.5
