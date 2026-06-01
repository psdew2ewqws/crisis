from app.engine.risk.base_risk import base_risk
from app.engine.risk.propagation import propagate
from app.engine.risk.index import national_index
from app.engine.types import Signal


def test_base_risk_pipe(cdg, seed):
    sigs = [
        Signal(id=s["id"], observes=s["observes"], metric=s["metric"],
               value=s["value"], baseline=s["baseline"], t_offset_s=s["t_offset_s"],
               severity_raw=s["severity_raw"])
        for s in seed["signals"] if not s.get("unrelated")
    ]
    # PS-12 has a high-severity signal
    r = base_risk("PS-12", sigs, criticality=0.9)
    assert r > 0.5


def test_propagation_reaches_downstream(cdg, seed):
    source_risks = {"PIPE-ZN-44": 0.9}
    risks = propagate(cdg, source_risks)
    assert "PS-12" in risks
    assert risks["PS-12"] > 0


def test_national_index_nonzero(cdg, seed):
    source_risks = {"PIPE-ZN-44": 0.9, "PS-12": 0.7}
    risks = propagate(cdg, source_risks)
    idx = national_index(risks)
    assert idx["national"] > 0
    assert len(idx["top_contributors"]) > 0
