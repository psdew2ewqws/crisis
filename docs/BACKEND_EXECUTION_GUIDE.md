# Backend Execution Guide — step-by-step build playbook

**Audience: the engineer (or coding agent) on the terminal who will type the commands and create the files.** This guide is prescriptive: follow phases **in order**, create the files **exactly** as named in `BACKEND_PLAN.md §4`, and after each phase run the **CHECK** block — do not move on until it passes. Copy-pasteable code is given for the load-bearing files (the ones easy to get wrong); for mechanical files the **signature + responsibility** is given and you fill the body to match.

**Three hard rules for this build (do not violate):**
1. **LLM is local Ollama only.** Model `gemma4:26B`, base URL `http://localhost:11434`. Never import a cloud SDK. All model calls go through `app/llm/`.
2. **No database yet.** The store is `repositories/memory/`, seeded from `data/seeds/zarqa.json`. Services/engine/swarm import **only `repositories/base.py` Protocols**. Never write SQL in this phase. `app/db/` and `repositories/postgres/` are created as stubs (`raise NotImplementedError`).
3. **The `engine/` package never imports FastAPI, redis, ollama, or any repo.** Pure functions in, dataclasses out. This is what keeps the unit tests deterministic.

Working directory for everything below: `crisis/backend/`.

---

## Phase 0 — Bootstrap

### 0.1 Create the project and virtualenv

```bash
cd crisis
mkdir -p backend && cd backend
python3 -m venv .venv
source .venv/bin/activate
python -V            # must print Python 3.12.x
```

### 0.2 `pyproject.toml`

Create `crisis/backend/pyproject.toml`:

```toml
[project]
name = "crisis-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "python-ulid>=2.2",
  "structlog>=24.1",
  "redis>=5.0",
  "arq>=0.26",
  "httpx>=0.27",
  # swarm + llm (local Ollama)
  "langgraph>=0.2",
  "langchain-core>=0.3",
  "langchain-ollama>=0.2",
  # engine libs
  "rustworkx>=0.15",
  "networkx>=3.3",
  "numpy>=1.26",
  "scipy>=1.13",
  "pyod>=1.1",
  "ortools>=9.10",
  # forecasting
  "timesfm",          # see 0.4 — may need the [torch] extra; pin after first install
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-asyncio>=0.23", "schemathesis>=3.30", "ruff>=0.5", "mypy>=1.10"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

### 0.3 Install (do engine + app deps first; TimesFM separately so a failure there can't block everything)

```bash
pip install -e ".[dev]"        # if timesfm line fails, comment it out, re-run, then do 0.4
```

### 0.4 TimesFM install (version-sensitive — verify before trusting)

TimesFM ships JAX and PyTorch backends; on macOS use **PyTorch**. The package API has changed across releases, so **install, then check the actual version and adapt** (`engine/prediction/timesfm_forecaster.py` has a fallback so the pipeline never blocks if this is fiddly):

```bash
pip install "timesfm[torch]" || pip install timesfm
python -c "import timesfm, importlib.metadata as m; print('timesfm', m.version('timesfm'))"
```

The checkpoint downloads from HuggingFace on first use (you are logged in as `KhaledSalehKL1`). Default repo id: `google/timesfm-2.0-500m-pytorch`. Set `HF_HOME=./data/timesfm` so it caches in-repo (gitignored).

### 0.5 Directory skeleton

Create the full tree from `BACKEND_PLAN.md §4`. Quick scaffold:

```bash
mkdir -p app/{core,llm,db,models,schemas,api/v1,api/ws,repositories/memory,repositories/postgres,services,engine/{graph,resolution,correlation,anomaly,rootcause,risk,prediction,optimization,simulation},swarm/nodes,packs/water/seed,sources/{synthetic,adapters},workers,bus,storage}
mkdir -p data/seeds data/timesfm data/artifacts migrations/versions seeds scripts tests/{unit,integration,contract}
find app -type d -exec touch {}/__init__.py \;
touch app/__init__.py
echo "data/timesfm/\ndata/artifacts/\n.venv/\n__pycache__/\n*.pyc" > .gitignore
```

### 0.6 `.env`

Create `crisis/backend/.env`:

```
APP_ENV=dev
REPO_BACKEND=memory
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=gemma4:26B
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_REQUEST_TIMEOUT=120
TIMESFM_CHECKPOINT=google/timesfm-2.0-500m-pytorch
TIMESFM_BACKEND=cpu
HF_HOME=./data/timesfm
SEED_PATH=./data/seeds/zarqa.json
REDIS_URL=redis://localhost:6379/0
ARTIFACTS_DIR=./data/artifacts
```

### 0.7 `app/core/config.py` (full)

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "dev"
    REPO_BACKEND: str = "memory"            # "memory" | "postgres"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_CHAT_MODEL: str = "gemma4:26B"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_REQUEST_TIMEOUT: int = 120
    TIMESFM_CHECKPOINT: str = "google/timesfm-2.0-500m-pytorch"
    TIMESFM_BACKEND: str = "cpu"
    SEED_PATH: str = "./data/seeds/zarqa.json"
    REDIS_URL: str = "redis://localhost:6379/0"
    ARTIFACTS_DIR: str = "./data/artifacts"
    # DATABASE_URL: str | None = None       # uncomment when DB is connected

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 0.8 `app/llm/client.py` (full) — the ONLY place models are constructed

```python
from functools import lru_cache
from langchain_ollama import ChatOllama, OllamaEmbeddings
from app.core.config import get_settings

@lru_cache
def build_chat(json_mode: bool = False) -> ChatOllama:
    s = get_settings()
    return ChatOllama(
        model=s.OLLAMA_CHAT_MODEL,
        base_url=s.OLLAMA_BASE_URL,
        temperature=0.2,
        timeout=s.OLLAMA_REQUEST_TIMEOUT,
        format="json" if json_mode else "",
    )

@lru_cache
def build_embeddings() -> OllamaEmbeddings:
    s = get_settings()
    return OllamaEmbeddings(model=s.OLLAMA_EMBED_MODEL, base_url=s.OLLAMA_BASE_URL)
```

### 0.9 `app/llm/json_mode.py` (full) — safe structured output from gemma

```python
import json
from typing import TypeVar
from pydantic import BaseModel, ValidationError
from app.llm.client import build_chat

T = TypeVar("T", bound=BaseModel)

def ask_json(system: str, user: str, schema: type[T]) -> T | None:
    """Call gemma in JSON mode, parse & validate against `schema`.
    Returns None on any failure so callers can fall back to engine output."""
    llm = build_chat(json_mode=True)
    msg = llm.invoke([("system", system), ("human", user)])
    try:
        data = json.loads(msg.content)
        return schema.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        return None
```

### 0.10 `scripts/check_env.py` (full) — the Phase-0 acceptance gate

```python
import json, sys
from app.core.config import get_settings
from app.llm.client import build_chat, build_embeddings

def main() -> int:
    s = get_settings()
    print("APP_ENV:", s.APP_ENV, "| REPO_BACKEND:", s.REPO_BACKEND)
    # 1) gemma chat
    out = build_chat().invoke([("human", "Reply with one word: OK")]).content
    print("gemma4 chat:", out.strip()[:40])
    assert "OK" in out.upper(), "gemma4:26B did not respond"
    # 2) embeddings dim
    dim = len(build_embeddings().embed_query("test"))
    print("embed dim:", dim)
    assert dim == 768, f"expected 768-dim, got {dim}"
    # 3) seed loads
    seed = json.load(open(s.SEED_PATH))
    print("seed nodes:", len(seed["nodes"]), "edges:", len(seed["edges"]),
          "signals:", len(seed["signals"]))
    assert len(seed["nodes"]) >= 9 and len(seed["edges"]) >= 7
    print("ENV OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 0.11 `data/seeds/zarqa.json` (full — exact IDs/weights from Technical Spec §0.3 & §1.4)

```json
{
  "incident": {
    "id": "INC-ZARQA-2026-05", "title": "Zarqa-North water cascade",
    "primary_location": "JO-AZ-N", "status": "open", "risk_index": 84
  },
  "locations": [
    {"id": "JO-AZ-N", "name": "Zarqa North", "level": "district", "parent": "JO-AZ"},
    {"id": "JO-AZ", "name": "Zarqa Governorate", "level": "governorate", "parent": "JO"}
  ],
  "nodes": [
    {"id": "PIPE-ZN-44", "type": "Asset", "kind": "pipe", "label": "Trunk main PIPE-ZN-44", "location_ref": "JO-AZ-N", "geo": [36.0876, 32.0728], "attrs": {"diameter_mm": 600, "install_year": 1998, "material": "ductile_iron", "last_inspection": "overdue"}},
    {"id": "PS-12", "type": "Asset", "kind": "pump", "label": "Pumping station PS-12", "location_ref": "JO-AZ-N", "attrs": {"inlet_pressure_bar": 1.1, "outlet_flow_lps": 12.0}},
    {"id": "R-3", "type": "Asset", "kind": "reservoir", "label": "Reservoir R-3", "location_ref": "JO-AZ-N", "attrs": {}},
    {"id": "WATER-ZN", "type": "Service", "kind": "water_distribution", "label": "Water distribution Zarqa-N", "location_ref": "JO-AZ-N", "attrs": {"criticality": 0.9}},
    {"id": "HOSP-ZN-1", "type": "Asset", "kind": "hospital", "label": "Zarqa General Hospital", "location_ref": "JO-AZ-N", "attrs": {"beds": 180}},
    {"id": "DP-5", "type": "Asset", "kind": "distribution_point", "label": "Tanker point DP-5", "location_ref": "JO-AZ-N", "attrs": {}},
    {"id": "JUNC-7", "type": "Asset", "kind": "road", "label": "Road junction JUNC-7", "location_ref": "JO-AZ-N", "attrs": {}},
    {"id": "POP-ZN", "type": "PopulationSegment", "kind": "population", "label": "Population Zarqa-N", "location_ref": "JO-AZ-N", "attrs": {"size": 180000}},
    {"id": "COMMS-911", "type": "Service", "kind": "psap", "label": "PSAP 911", "location_ref": "JO-AZ-N", "attrs": {}}
  ],
  "edges": [
    {"src": "PIPE-ZN-44", "dst": "PS-12",     "rel": "feeds",        "w": 0.95, "lag_s": 0},
    {"src": "PS-12",      "dst": "R-3",        "rel": "supplies",     "w": 0.90, "lag_s": 300},
    {"src": "R-3",        "dst": "WATER-ZN",   "rel": "provides",     "w": 1.00, "lag_s": 300},
    {"src": "WATER-ZN",   "dst": "POP-ZN",     "rel": "serves",       "w": 1.00, "lag_s": 0},
    {"src": "WATER-ZN",   "dst": "HOSP-ZN-1",  "rel": "depends_on",   "w": 0.60, "lag_s": 1800},
    {"src": "WATER-ZN",   "dst": "DP-5",       "rel": "activated_by", "w": 0.70, "lag_s": 1500},
    {"src": "DP-5",       "dst": "JUNC-7",     "rel": "impacted_by",  "w": 0.40, "lag_s": 2400},
    {"src": "POP-ZN",     "dst": "COMMS-911",  "rel": "load_from",    "w": 0.50, "lag_s": 2400}
  ],
  "signals": [
    {"id": "S1", "t_offset_s": 0,    "source": "WAJ-SCADA", "observes": "PS-12",     "metric": "inlet_pressure_bar", "value": 1.1, "baseline": 6.2, "severity_raw": "high"},
    {"id": "S2", "t_offset_s": 480,  "source": "WAJ",       "observes": "WATER-ZN",  "metric": "reservoir_level",    "value": 0.3, "baseline": 1.0, "severity_raw": "high"},
    {"id": "S3", "t_offset_s": 2100, "source": "MoH",       "observes": "HOSP-ZN-1", "metric": "ed_occupancy",       "value": 0.94,"baseline": 0.70,"severity_raw": "med"},
    {"id": "S4", "t_offset_s": 2400, "source": "Traffic",   "observes": "JUNC-7",    "metric": "congestion",         "value": 0.8, "baseline": 0.3, "severity_raw": "low"},
    {"id": "S5", "t_offset_s": 2700, "source": "PSAP-911",  "observes": "COMMS-911", "metric": "call_volume",        "value": 420, "baseline": 100, "severity_raw": "high"},
    {"id": "S6", "t_offset_s": 1200, "source": "Social",    "observes": "national",  "metric": "sentiment",          "value": 0.7, "baseline": 0.4, "severity_raw": "low", "unrelated": true}
  ],
  "ground_truth": {
    "root_cause": "PIPE-ZN-44",
    "exclude_from_incident": ["S6"],
    "intervention": "isolate+bypass+tanker",
    "risk_before": 84, "risk_after": 22
  }
}
```

> **`t_offset_s`** is seconds after the incident's `T+0`. The replayer (Phase 3) adds these to a chosen wall-clock start so the Step-1 feed streams in order. `S6` carries `"unrelated": true` — the correlation engine MUST exclude it (it shares no edge into `JO-AZ-N`).

### ✅ CHECK Phase 0

```bash
source .venv/bin/activate
python scripts/check_env.py
# Expect: "gemma4 chat: OK", "embed dim: 768", "seed nodes: 9 edges: 8 signals: 6", "ENV OK"
```

---

## Phase 1 — Engine core (pure, no infra). This is the highest-value phase.

All files under `app/engine/` and tests under `tests/unit/`. **No imports from `app.api`, `app.repositories`, `app.llm`, redis, or ollama anywhere in `engine/`.**

### 1.1 `app/engine/types.py` (full)

```python
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Node:
    id: str
    type: str            # Asset|Service|Location|PopulationSegment|...
    kind: str            # pipe|pump|hospital|...
    label: str = ""
    location_ref: str | None = None
    attrs: dict = field(default_factory=dict)

@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    rel: str
    w: float
    lag_s: float

@dataclass(frozen=True)
class Signal:
    id: str
    observes: str
    metric: str
    value: float
    baseline: float
    t_offset_s: float
    severity_raw: str = "low"

@dataclass
class CausalPath:
    path: list[str]      # symptom ... cause (upstream order)
    path_weight: float
    path_lag: float

@dataclass
class RankedCause:
    node_id: str
    score: float
    covers: int
    is_apex: bool = False

@dataclass
class RootCauseResult:
    likely_cause: str
    confidence: float
    hypotheses: list[RankedCause]
    supporting: list[str] = field(default_factory=list)
    conflicting: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
```

### 1.2 `app/engine/graph/store.py` (full) — adjacency over rustworkx-style maps

Keep it a plain Python adjacency map (rustworkx optional for speed later); the spec's traversals only need `inEdges`/`outEdges`.

```python
from app.engine.types import Node, Edge

class CDG:
    """Crisis Dependency Graph — directed, weighted, typed (Tech Spec §1.1)."""
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self._out: dict[str, list[Edge]] = {}
        self._in: dict[str, list[Edge]] = {}

    def add_node(self, n: Node) -> None:
        self.nodes[n.id] = n
        self._out.setdefault(n.id, []); self._in.setdefault(n.id, [])

    def add_edge(self, e: Edge) -> None:
        assert 0.0 <= e.w <= 1.0 and e.lag_s >= 0, "R1: bad edge weight/lag"
        self._out.setdefault(e.src, []).append(e)
        self._in.setdefault(e.dst, []).append(e)

    def out_edges(self, nid: str) -> list[Edge]: return self._out.get(nid, [])
    def in_edges(self, nid: str) -> list[Edge]:  return self._in.get(nid, [])

    @classmethod
    def from_seed(cls, nodes: list[dict], edges: list[dict]) -> "CDG":
        g = cls()
        for n in nodes:
            g.add_node(Node(id=n["id"], type=n["type"], kind=n["kind"],
                            label=n.get("label",""), location_ref=n.get("location_ref"),
                            attrs=n.get("attrs", {})))
        for e in edges:
            g.add_edge(Edge(src=e["src"], dst=e["dst"], rel=e["rel"],
                            w=e["w"], lag_s=e["lag_s"]))
        return g
```

### 1.3 `app/engine/graph/traversal.py` (full) — implements Tech Spec §1.3 verbatim

```python
import heapq
from app.engine.graph.store import CDG
from app.engine.types import CausalPath

def k_shortest_causal_paths(g: CDG, symptom: str, candidate: str,
                            K: int = 1, max_hops: int = 6, min_pw: float = 0.05):
    """Walk UPSTREAM from symptom toward candidate (Tech Spec §1.3 pseudocode).
    Returns CausalPath list, non-increasing path_weight (R2)."""
    heap = [(-1.0, 0.0, [symptom])]
    out: list[CausalPath] = []
    best_at: dict[str, float] = {}
    while heap and len(out) < K:
        neg_pw, lag, path = heapq.heappop(heap)
        pw, node = -neg_pw, path[-1]
        if node == candidate:
            out.append(CausalPath(path=path, path_weight=pw, path_lag=lag)); continue
        if len(path) - 1 >= max_hops:
            continue
        for e in g.in_edges(node):              # u --rel--> node : u is upstream cause
            if e.src in path:                   # simple paths only
                continue
            npw = pw * e.w
            if npw < min_pw:                    # prune (weight only shrinks)
                continue
            if npw <= best_at.get(e.src, 0.0):  # cycle-damping
                continue
            best_at[e.src] = npw
            heapq.heappush(heap, (-npw, lag + e.lag_s, path + [e.src]))
    return out

def ancestors(g: CDG, n: str, max_hops: int = 6, min_pw: float = 0.05) -> set[str]:
    """All upstream nodes reachable within max_hops with path weight >= min_pw."""
    seen: set[str] = set()
    heap = [(-1.0, [n])]
    while heap:
        neg_pw, path = heapq.heappop(heap)
        pw, node = -neg_pw, path[-1]
        if len(path) - 1 >= max_hops:
            continue
        for e in g.in_edges(node):
            npw = pw * e.w
            if npw < min_pw or e.src in path:
                continue
            if e.src not in seen:
                seen.add(e.src)
            heapq.heappush(heap, (-npw, path + [e.src]))
    return seen
```

### 1.4 `app/engine/rootcause/layer_a.py` (full) — implements Tech Spec §4.1 scoring

```python
from statistics import mean
from app.engine.graph.store import CDG
from app.engine.graph.traversal import ancestors, k_shortest_causal_paths
from app.engine.types import Signal, RankedCause, RootCauseResult

W_COV, W_PATH, W_TEMP, W_CORR = 0.30, 0.25, 0.20, 0.25   # §4.1 defaults (config)
TAU = 0.5                                                  # ±50% temporal tolerance

def _temporal_ok(expected_lag: float, t_cause: float, t_symptom: float) -> int:
    observed = t_symptom - t_cause
    if observed < 0:
        return 0
    return 1 if abs(observed - expected_lag) <= TAU * max(expected_lag, 1) else 0

def rank_root_causes(g: CDG, signals: list[Signal]) -> RootCauseResult:
    sigma = [(s.observes, s.t_offset_s, s) for s in signals]
    candidates: set[str] = set()
    paths: dict[tuple[str, str], object] = {}      # (cause, symptom) -> CausalPath
    for (sym, _t, _s) in sigma:
        for c in ancestors(g, sym):
            candidates.add(c)
            kp = k_shortest_causal_paths(g, sym, c, K=1)
            if kp:
                paths[(c, sym)] = kp[0]
    # direct corroboration: a signal whose `observes` is the candidate or its direct child
    def corroboration(c: str) -> float:
        for s in signals:
            if s.observes == c:
                return 1.0
            if any(e.src == c for e in g.in_edges(s.observes)):
                return 0.8
        return 0.0

    ranked: list[RankedCause] = []
    for c in candidates:
        reached = [(sym, t) for (sym, t, _s) in sigma if (c, sym) in paths]
        if not reached:
            continue
        cov = len(reached) / len(sigma)
        path_strength = mean(paths[(c, sym)].path_weight for sym, _ in reached)
        temp = mean(_temporal_ok(paths[(c, sym)].path_lag, 0.0, t) for sym, t in reached)
        corr = corroboration(c)
        score = W_COV*cov + W_PATH*path_strength + W_TEMP*temp + W_CORR*corr
        ranked.append(RankedCause(node_id=c, score=round(score, 3), covers=len(reached)))
    ranked.sort(key=lambda r: -r.score)
    if ranked:
        ranked[0].is_apex = True
    conf = _confidence(ranked)
    return RootCauseResult(
        likely_cause=ranked[0].node_id if ranked else "",
        confidence=conf, hypotheses=ranked,
        supporting=[f"path strength {ranked[0].score}" ] if ranked else [],
        conflicting=["loudest signal resolves to a downstream symptom, not the cause"],
        missing=["acoustic/leak sensor on apex (none deployed)"],
    )

def _confidence(ranked: list[RankedCause]) -> float:
    if not ranked:
        return 0.0
    if len(ranked) == 1:
        return round(ranked[0].score, 2)
    margin = ranked[0].score - ranked[1].score
    # tighter margin → lower confidence (§4.3); blend top score with separation
    return round(min(0.95, ranked[0].score * (0.6 + 0.4 * min(margin / 0.15, 1.0))), 2)
```

### 1.5 Other engine modules (signatures + responsibility — fill bodies to match the spec sections)

| File | Signature | Responsibility |
|---|---|---|
| `engine/anomaly/batch.py` | `zscore(values, baseline) -> float` ; `flag_anomalies(signals) -> list[str]` | PyOD/z-score; flag S1 pressure & S5 call-volume |
| `engine/correlation/stitch.py` | `stitch(signals, g) -> Incident` | spatial+temporal+dim scores; **exclude any signal with `unrelated` or no edge into the locality** (drops S6) |
| `engine/resolution/resolver.py` | `resolve(raw) -> node_id` | map free-text/source to a CDG node id; Splink later, exact-match dict now |
| `engine/risk/base_risk.py` | `base_risk(node, signals) -> float` | per-node r(n) from severity/criticality (§5.2) |
| `engine/risk/propagation.py` | `propagate(g, sources, prov) -> dict[str,float]` | `descendants`-based cascade (§5.3) |
| `engine/risk/index.py` | `national_index(risks) -> dict` | aggregate to {national, by_location}, factor attribution (§5.6) |
| `engine/optimization/intervention.py` | `rank_interventions(library, incident) -> list` | OR-Tools or weighted rank; isolate+bypass+tanker #1 |
| `engine/simulation/adapter.py` | `class SimAdapter(Protocol): def run(scenario)->SimResult` | the sim boundary |
| `engine/simulation/runner.py` | `run_before_after(adapter, scenario) -> SimResult` | risk delta harness |

### 1.6 `app/engine/prediction/timesfm_forecaster.py` (full) — TimesFM with a safe fallback

```python
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from app.core.config import get_settings

@dataclass
class Forecast:
    point: list[float]
    lower: list[float]
    upper: list[float]
    backend: str

@lru_cache
def _load_timesfm():
    """Load the TimesFM checkpoint once (singleton). Returns the model or None."""
    s = get_settings()
    try:
        import timesfm
        tfm = timesfm.TimesFm(
            hparams=timesfm.TimesFmHparams(
                backend=s.TIMESFM_BACKEND, per_core_batch_size=32,
                horizon_len=128, context_len=512,
            ),
            checkpoint=timesfm.TimesFmCheckpoint(
                huggingface_repo_id=s.TIMESFM_CHECKPOINT),
        )
        return tfm
    except Exception as exc:                       # version drift / no checkpoint
        print(f"[timesfm] load failed, using naive fallback: {exc}")
        return None

def forecast(series: list[float], horizon: int = 24) -> Forecast:
    """Forecast `horizon` steps ahead. Uses TimesFM if available, else naive drift."""
    tfm = _load_timesfm()
    if tfm is not None:
        try:
            point, quant = tfm.forecast([series], freq=[0])
            p = list(point[0][:horizon])
            # quant[...] layout is version-specific; guard it
            lo = [v * 0.85 for v in p]; hi = [v * 1.15 for v in p]
            return Forecast(point=p, lower=lo, upper=hi, backend="timesfm")
        except Exception as exc:
            print(f"[timesfm] forecast failed, fallback: {exc}")
    # naive fallback: last value + linear drift of last step
    last = series[-1] if series else 0.0
    drift = (series[-1] - series[-2]) if len(series) >= 2 else 0.0
    p = [last + drift * (i + 1) for i in range(horizon)]
    return Forecast(point=p, lower=[v*0.8 for v in p], upper=[v*1.2 for v in p],
                    backend="naive")
```

> **TimesFM API note for the executor:** the `TimesFm(...)`/`forecast(...)` call shape differs between timesfm 1.x and 2.x. After install, run `python -c "import timesfm; help(timesfm.TimesFm)"` and adjust the `_load_timesfm` constructor to match the installed version. **Do not block on this** — the naive fallback keeps Phases 4–5 working; revisit once the rest is green.

### 1.7 `tests/unit/` — anchored to the spec's worked numbers

```python
# tests/unit/conftest.py
import json, pytest
from app.engine.graph.store import CDG

@pytest.fixture
def seed():
    return json.load(open("data/seeds/zarqa.json"))

@pytest.fixture
def cdg(seed):
    return CDG.from_seed(seed["nodes"], seed["edges"])
```

```python
# tests/unit/test_traversal.py — Tech Spec §1.4 worked trace
from app.engine.graph.traversal import k_shortest_causal_paths

def test_hospital_to_pipe_path_weight(cdg):
    paths = k_shortest_causal_paths(cdg, "HOSP-ZN-1", "PIPE-ZN-44", K=1)
    assert paths, "no causal path found"
    assert round(paths[0].path_weight, 3) == 0.513   # spec §1.4
```

```python
# tests/unit/test_rootcause.py — Tech Spec §4.1 worked matrix
from app.engine.rootcause.layer_a import rank_root_causes
from app.engine.types import Signal

def test_apex_is_pipe_not_911(cdg, seed):
    sigs = [Signal(id=s["id"], observes=s["observes"], metric=s["metric"],
                   value=s["value"], baseline=s["baseline"], t_offset_s=s["t_offset_s"],
                   severity_raw=s["severity_raw"])
            for s in seed["signals"] if not s.get("unrelated")]
    res = rank_root_causes(cdg, sigs)
    assert res.likely_cause == "PIPE-ZN-44"
    ids = [h.node_id for h in res.hypotheses]
    assert ids.index("PIPE-ZN-44") < ids.index("COMMS-911")   # loud != causal
```

### ✅ CHECK Phase 1

```bash
pytest tests/unit -q
# Expect: test_hospital_to_pipe_path_weight PASSED, test_apex_is_pipe_not_911 PASSED
```

---

## Phase 2 — Repositories (memory) + services + REST read paths

### 2.1 `app/repositories/base.py` (Protocols — the contract both backends honor)

```python
from typing import Protocol
from app.engine.types import Node, Edge, Signal

class GraphRepo(Protocol):
    def get_nodes(self) -> list[Node]: ...
    def get_edges(self) -> list[Edge]: ...
    def upstream_apex(self, symptom: str) -> str: ...

class SignalRepo(Protocol):
    def list(self, since: float | None = None) -> list[Signal]: ...
    def add(self, sig: Signal) -> None: ...

class IncidentRepo(Protocol):
    def get(self, incident_id: str) -> dict | None: ...
    def list(self) -> list[dict]: ...

# ... RootCauseRepo, InterventionRepo, SimulationRepo, DecisionRepo,
#     EmbeddingRepo, SourceRepo, WizardRepo — same shape

class RepoBundle(Protocol):
    graph: GraphRepo
    signals: SignalRepo
    incidents: IncidentRepo
    # rootcauses, interventions, simulations, decisions, embeddings, sources, wizard
```

### 2.2 `app/repositories/memory/store.py` + `seed_loader.py`

```python
# store.py
from app.engine.graph.store import CDG
from app.engine.types import Signal

class MemoryStore:
    def __init__(self):
        self.cdg: CDG | None = None
        self.signals: list[Signal] = []
        self.incidents: dict[str, dict] = {}
        self.root_causes: dict[str, dict] = {}
        self.interventions: dict[str, list] = {}
        self.simulations: dict[str, dict] = {}
        self.decisions: dict[str, dict] = {}
        self.wizard: dict[str, dict] = {}
        self.sources: dict[str, dict] = {}
```

```python
# seed_loader.py
import json
from app.engine.graph.store import CDG
from app.engine.types import Signal
from app.repositories.memory.store import MemoryStore

def load_seed(path: str) -> MemoryStore:
    data = json.load(open(path))
    s = MemoryStore()
    s.cdg = CDG.from_seed(data["nodes"], data["edges"])
    s.signals = [Signal(id=x["id"], observes=x["observes"], metric=x["metric"],
                        value=x["value"], baseline=x["baseline"],
                        t_offset_s=x["t_offset_s"], severity_raw=x["severity_raw"])
                 for x in data["signals"] if not x.get("unrelated")]
    inc = data["incident"]; s.incidents[inc["id"]] = inc
    return s
```

Then `memory/graph.py`, `memory/signals.py`, `memory/incidents.py` etc. are thin classes implementing the `base.py` Protocols over one shared `MemoryStore`. `memory/graph.py.upstream_apex` calls the engine: `rank_root_causes(store.cdg, store.signals).likely_cause`.

### 2.3 `app/repositories/factory.py`

```python
from app.core.config import get_settings

def get_repos():
    s = get_settings()
    if s.REPO_BACKEND == "memory":
        from app.repositories.memory.seed_loader import load_seed
        from app.repositories.memory.bundle import MemoryBundle
        return MemoryBundle(load_seed(s.SEED_PATH))
    if s.REPO_BACKEND == "postgres":
        raise NotImplementedError("DB deferred — implement repositories/postgres/*")
    raise ValueError(s.REPO_BACKEND)
```

`repositories/postgres/*` files: each method body is `raise NotImplementedError`. Create them so the package imports, but do not implement until the DB is connected.

### 2.4 Services + API (read paths)

- `services/incident_service.py` — `get_graph(incident_id)` returns `{nodes:[...], edges:[...]}` shaped for React Flow; `get_root_cause(incident_id)` calls `rank_root_causes`; `risk_service.national_index()`.
- `app/main.py` — `create_app()`: build FastAPI, attach routers, store `repos = get_repos()` on `app.state`, register RFC-7807 handlers, lifespan starts/stops Redis + WS relay (Phase 3).
- `app/api/v1/incidents.py` — `GET /api/v1/incidents`, `/{id}`, `/{id}/graph`, `/{id}/root-cause` reading via `app.state.repos`. Mirror `MVP.md §3.2`.
- `app/api/v1/risk.py`, `app/api/v1/signals.py` — `GET /risk`, `GET /signals`.

### ✅ CHECK Phase 2

```bash
uvicorn app.main:app --reload --port 8000 &
sleep 3
curl -s localhost:8000/api/v1/incidents/INC-ZARQA-2026-05/root-cause | python3 -m json.tool
# Expect JSON with "likely_cause": "PIPE-ZN-44"
curl -s localhost:8000/api/v1/incidents/INC-ZARQA-2026-05/graph | python3 -c "import sys,json;d=json.load(sys.stdin);print('nodes',len(d['nodes']),'edges',len(d['edges']))"
```

---

## Phase 3 — Sources + ingestion + WebSocket

- `sources/base.py` — `class SourceConnector(Protocol): discover_schema(); poll() -> list[dict]; normalize(raw) -> Signal`.
- `sources/synthetic/{scada,psap_911,hospital,traffic,weather}.py` — each yields raw envelopes for its metric. `weather.py` is the **advanced external signal** (used in Phase 6).
- `sources/registry.py` + `services/source_service.py` — onboarding state machine `registered→…→active`, persisted in `store.sources`.
- `app/api/v1/signals.py` — `POST /signals` → `services/ingestion.py` (validate → resolve → `store.signals.add` → publish `signals/signal.new` to Redis).
- `app/bus/{redis,pubsub}.py` — async redis client + `publish(channel, event, data)` / `subscribe(pattern)`.
- `app/api/ws/{router,hub,relay}.py` — `/ws?token=…`; `relay` subscribes Redis `case:*`, `signals`, `risk` and fans frames to subscribed sockets.
- `scripts/replay_signals.py` — read seed signals, sort by `t_offset_s`, POST them on a timer so Step-1 streams in order.

### ✅ CHECK Phase 3

```bash
# terminal A: uvicorn running; terminal B:
python scripts/replay_signals.py --speed 60   # 60x: whole incident in ~45s
# Use a WS client (wscat) on ws://localhost:8000/ws?token=dev to see signal.new frames
```

---

## Phase 4 — Swarm + Arq (Ollama-driven)

### 4.1 `app/swarm/state.py`

```python
from pydantic import BaseModel, Field

class CaseState(BaseModel):
    case_id: str
    signals: list[dict] = Field(default_factory=list)
    incident: dict | None = None
    root_cause: dict | None = None
    risk: dict | None = None
    solutions: list[dict] = Field(default_factory=list)
    sim: dict | None = None
    recommendation: dict | None = None
    decision: dict | None = None
    trace: list[dict] = Field(default_factory=list)
```

### 4.2 `app/swarm/nodes/rootcause.py` (example node — engine computes, gemma narrates)

```python
from app.swarm.state import CaseState
from app.engine.rootcause.layer_a import rank_root_causes
from app.llm.json_mode import ask_json
from app.swarm.emit import emit
from pydantic import BaseModel

class _Narr(BaseModel):
    summary: str

def rootcause_node(state: CaseState, *, repos) -> CaseState:
    g = repos.graph.cdg
    sigs = repos.signals.list()
    res = rank_root_causes(g, sigs)                 # NUMERIC TRUTH from engine
    narr = ask_json(                                # gemma only narrates
        system="You are a crisis analyst. Return JSON {\"summary\": str}. "
               "Explain in 2 sentences why the apex is the cause and the loud "
               "signal is only a symptom. Do not invent numbers.",
        user=f"apex={res.likely_cause} conf={res.confidence} "
             f"hypotheses={[(h.node_id,h.score) for h in res.hypotheses]}",
        schema=_Narr)
    state.root_cause = {
        "apex": res.likely_cause, "confidence": res.confidence,
        "hypotheses": [h.__dict__ for h in res.hypotheses],
        "summary": narr.summary if narr else "Apex identified by causal scoring.",
    }
    emit(state.case_id, "rootcause", "done", state.root_cause)
    return state
```

Other nodes (`ingest, resolve, correlate, risk, generate, validate, recommend, learn`) follow the same shape: read via repos → call engine → optional gemma narration → write to `state` → `emit`. **Numbers always from engine, never from gemma.**

### 4.3 `app/swarm/graph.py`

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.swarm.state import CaseState
from app.swarm import nodes

def build_graph(repos):
    g = StateGraph(CaseState)
    order = ["ingest","resolve","correlate","rootcause","risk",
             "generate","validate","recommend","learn"]
    for name in order:
        g.add_node(name, lambda s, n=name: getattr(nodes, n)(s, repos=repos))
    g.add_edge(START, "ingest")
    for a, b in zip(order, order[1:]):
        g.add_edge(a, b)
    g.add_edge("learn", END)
    return g.compile(checkpointer=MemorySaver())   # Postgres checkpointer later
```

### 4.4 `app/workers/{arq_worker,tasks,events}.py` — `run_case_loop(ctx, case_id)` builds the graph and streams it; `app/api/v1/incidents.py` adds `POST /incidents/{id}/run` → enqueue.

### ✅ CHECK Phase 4

```bash
arq app.workers.arq_worker.WorkerSettings &     # needs Redis up
curl -s -X POST localhost:8000/api/v1/incidents/INC-ZARQA-2026-05/run
# Watch WS frames advance ingest→…→rootcause(apex=PIPE-ZN-44)→…
python -m scripts.run_demo            # headless full loop, asserts apex==PIPE-ZN-44
```

---

## Phase 5 — Solutions + simulation + decision gate

- `packs/water/interventions.py` — library: `isolate`, `bypass(ZN-12)`, `tanker(n)`; costs + ETA.
- `packs/water/sim_adapter.py` — implements `SimAdapter`; for now a deterministic before/after model (risk 84→22) keyed off the chosen intervention; wire real WNTR/EPANET later behind the same interface.
- `services/simulation_service.py` + `workers/tasks.run_simulation` — produce `{risk_before, risk_after, series[]}`, write artifact JSON to `./data/artifacts/<run_id>.json`.
- `app/api/v1/{solutions,simulations,decisions}.py` — `POST /solutions:generate`, `POST /simulations`, `POST /decisions`, `POST /decisions/{id}:authorize` (role `commander`; **409 if `sim_id` stale**).
- `services/decision_service.py` — writes the decision + audit bundle to `./data/artifacts`.

### ✅ CHECK Phase 5 — the MVP acceptance test (`MVP.md §1.4`)

```bash
python -m scripts.run_demo --full
# Asserts: root_cause==PIPE-ZN-44; risk_after<0.30*100 and <0.5*risk_before;
#          decision status==authorized; artifact written to data/artifacts/
```

---

## Phase 6 — Dynamic onboarding + advanced signal + cleanup

- Onboard `sources/synthetic/weather.py` **at runtime** via `POST /api/v1/sources` → register → map → validate → activate; show the national risk index and a re-sim shift after it goes active (scope §6 minimum demonstration).
- `workers/tasks.cleanup_sim_run(run_id)` — drop all `sim`-provenance data for a run (in memory: filter lists by `run_id`). Scenario expiration = a periodic Arq cron purging expired runs.

### ✅ CHECK Phase 6

```bash
curl -s -X POST localhost:8000/api/v1/sources -d @weather_source.json
# activate, then re-run risk; national index must change; cleanup removes sim rows
```

---

## Phase 7 — DB cutover (LATER, only when the user connects Postgres)

Do nothing here until told. When the DB is ready: implement `repositories/postgres/*` against the `base.py` Protocols, fill `app/db/` + Alembic `0001–0004` (extensions → core → signals hypertable → AGE graph, per `MVP.md §4`), swap `MemorySaver`→Postgres checkpointer and artifacts→MinIO, set `REPO_BACKEND=postgres`, run `alembic upgrade head` + seed import. **All Phase 1–6 tests must pass unchanged** — that is the proof the deferral was done right.

---

## Quick reference — daily run

```bash
cd crisis/backend && source .venv/bin/activate
# Ollama already running (gemma4:26B, nomic-embed-text). Redis for Phases 3+:
redis-server &                      # or docker run -p 6379:6379 redis:7
uvicorn app.main:app --reload --port 8000 &
arq app.workers.arq_worker.WorkerSettings &
python scripts/check_env.py         # sanity
pytest -q                           # all green
```

## Anti-patterns to avoid (for the executor)

- ❌ Importing `repositories`, `ollama`, or `redis` inside `app/engine/**`. The engine is pure.
- ❌ Letting gemma produce the apex/risk/forecast numbers. Engine computes; gemma only writes prose.
- ❌ Writing SQL or Alembic migrations now. DB is deferred to Phase 7.
- ❌ Hard-coding `gemma4:26B` or the base URL in node files. Always go through `app/llm` + `Settings`.
- ❌ Blocking the build on TimesFM API quirks. The naive fallback keeps the loop working; fix TimesFM after green.
- ❌ Skipping a CHECK block. Each phase must pass its check before the next begins.
```
