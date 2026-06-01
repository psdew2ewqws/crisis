import json
from app.engine.graph.store import CDG
from app.engine.types import Signal
from app.repositories.memory.store import MemoryStore


def load_seed(path: str) -> MemoryStore:
    data = json.load(open(path))
    s = MemoryStore()
    s.cdg = CDG.from_seed(data["nodes"], data["edges"])
    s.signals = [
        Signal(
            id=x["id"], observes=x["observes"], metric=x["metric"],
            value=x["value"], baseline=x["baseline"],
            t_offset_s=x["t_offset_s"], severity_raw=x["severity_raw"],
        )
        for x in data["signals"] if not x.get("unrelated")
    ]
    inc = data["incident"]
    s.incidents[inc["id"]] = inc
    s.interventions = data.get("interventions", [])
    return s
