"""Environment check script — Phase 0 acceptance gate."""
import json
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")


def main() -> int:
    from app.core.config import get_settings
    s = get_settings()
    print(f"APP_ENV: {s.APP_ENV} | REPO_BACKEND: {s.REPO_BACKEND}")

    # Seed loads
    seed = json.load(open(s.SEED_PATH))
    print(f"seed nodes: {len(seed['nodes'])} edges: {len(seed['edges'])} signals: {len(seed['signals'])}")
    assert len(seed["nodes"]) >= 9 and len(seed["edges"]) >= 7

    # Engine works
    from app.engine.graph.store import CDG
    from app.engine.rootcause.layer_a import rank_root_causes
    from app.engine.types import Signal

    cdg = CDG.from_seed(seed["nodes"], seed["edges"])
    sigs = [
        Signal(id=x["id"], observes=x["observes"], metric=x["metric"],
               value=x["value"], baseline=x["baseline"],
               t_offset_s=x["t_offset_s"], severity_raw=x["severity_raw"])
        for x in seed["signals"] if not x.get("unrelated")
    ]
    res = rank_root_causes(cdg, sigs)
    print(f"root cause: {res.likely_cause} (confidence: {res.confidence})")
    assert res.likely_cause == "PIPE-ZN-44"

    print("ENV OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
