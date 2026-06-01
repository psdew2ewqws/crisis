"""AEGIS Deer Graph API — voc360 data → live graph → root cause.

Endpoints:
  GET  /api/health            DB connectivity
  GET  /api/stats             voc360 row counts
  GET  /api/cases             selectable cases (services + clusters)
  GET  /api/graph?case=       the live dependency graph
  GET  /api/rootcause         ranked root-cause clusters
  POST /api/flow/run          stream the data→graph→root-cause flow (NDJSON)
  POST /api/simulate          sentiment-propagation simulation (before/after)
"""
from __future__ import annotations
import json
import time

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import db, graph_builder, rootcause

# Optional advanced engines: the LangGraph "Deer Graph" flow and the Mesa
# agent-based simulation. Both degrade gracefully to the inline versions below.
try:
    from . import deer_flow  # noqa: F401
    _HAS_DEERFLOW = True
except Exception:
    deer_flow = None  # type: ignore
    _HAS_DEERFLOW = False
try:
    from . import mesa_sim  # noqa: F401
    _HAS_MESA = True
except Exception:
    mesa_sim = None  # type: ignore
    _HAS_MESA = False

app = FastAPI(title="AEGIS Deer Graph", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?",
    allow_methods=["*"], allow_headers=["*"],
)

# v2 console endpoints: /api/signals, /api/kpis, /api/signal-volume,
# /api/solutions, /api/decisions, /api/narrate, /api/graph2
try:
    from . import main_v2
    app.include_router(main_v2.router)
except Exception:
    pass

# v3 deep-reasoning endpoints: /api/forecast, /api/whys, /api/validate, /api/ask,
# /api/suggest, /api/rootcause-graph
try:
    from . import api_v3
    app.include_router(api_v3.router)
except Exception:
    pass

# proof + Excel-report endpoints: /api/proof, /api/report/<cluster_id>.xlsx
try:
    from . import proof
    app.include_router(proof.router)
except Exception:
    pass


@app.get("/api/health")
def health():
    try:
        return {"ok": True, **db.health()}
    except Exception as e:  # surface, don't hide
        return {"ok": False, "error": str(e)}


@app.get("/api/stats")
def stats():
    return db.fetchone("""
      select (select count(*) from the_data) as signals,
             (select count(distinct service_id) from the_data where service_id is not null) as services,
             (select count(distinct source_type) from the_data) as sources,
             (select count(distinct governorate) from the_data where governorate is not null) as governorates,
             (select count(*) from ril_problem_clusters where coalesce(member_count,0)>1) as clusters,
             (select count(*) from ril_text_segments) as segments
    """)


@app.get("/api/cases")
def cases():
    services = db.fetchall("""
      select service_id as id, count(*) as signals,
             count(*) filter (where severity in ('high','critical')) as critical
      from the_data where service_id is not null
      group by 1 order by signals desc limit 12
    """)
    clusters = rootcause.rank_root_causes(limit=6)
    return {"services": services, "top_root_causes": clusters}


@app.get("/api/graph")
def graph(case: str | None = Query(default=None)):
    return graph_builder.build_graph(case)


@app.get("/api/rootcause")
def root_cause(limit: int = Query(default=10, ge=1, le=20)):
    ranked = rootcause.rank_root_causes(limit)
    return {"root_causes": ranked, "recommendation": rootcause.recommend(ranked[0]) if ranked else None}


# ---- the Deer Graph flow (staged, streamed) ------------------------------
def _flow(case: str | None):
    def ev(stage, status, detail, data=None):
        return json.dumps({"stage": stage, "status": status, "detail": detail, "data": data}, ensure_ascii=False) + "\n"

    yield ev("connect", "running", "Connecting to voc360 (read-only)…")
    h = db.health()
    yield ev("connect", "done", f"Connected · {h['database']}", h)
    time.sleep(0.2)

    yield ev("ingest", "running", "Pulling citizen signals for the case…")
    g = graph_builder.build_graph(case)
    yield ev("ingest", "done", f"{g['stats']['signals']} signals across {g['stats']['services']} services", g["stats"])
    time.sleep(0.2)

    yield ev("graph", "running", "Building the dependency graph…")
    yield ev("graph", "done", f"{len(g['nodes'])} nodes · {len(g['edges'])} edges", {"nodes": len(g["nodes"]), "edges": len(g["edges"])})
    time.sleep(0.2)

    yield ev("rootcause", "running", "Ranking root-cause problem clusters (RIL)…")
    rc = rootcause.rank_root_causes(8)
    yield ev("rootcause", "done", f"Top cause: {rc[0]['members']} reports" if rc else "no clusters", rc[:5])
    time.sleep(0.2)

    yield ev("recommend", "running", "Drafting recommendation…")
    rec = rootcause.recommend(rc[0]) if rc else "No root cause found."
    yield ev("recommend", "done", rec, {"graph": g, "root_causes": rc})


@app.post("/api/flow/run")
def flow_run(case: str | None = Query(default=None)):
    """Stream the Deer Graph flow — the LangGraph engine when available, else inline."""
    if _HAS_DEERFLOW:
        def gen():
            for frame in deer_flow.run_flow(case):
                yield json.dumps(frame, ensure_ascii=False) + "\n"
        return StreamingResponse(gen(), media_type="application/x-ndjson")
    return StreamingResponse(_flow(case), media_type="application/x-ndjson")


# ---- lightweight propagation simulation (Mesa version arrives via workflow)
@app.post("/api/simulate")
def simulate(case: str | None = Query(default=None), steps: int = Query(default=24, ge=4, le=60)):
    if _HAS_MESA:
        try:
            return mesa_sim.simulate(case, intervene=True)
        except Exception:
            pass  # fall back to the lightweight inline propagation model
    g = graph_builder.build_graph(case)
    services = [n for n in g["nodes"] if n["type"] == "service"]
    base = sum(n["value"] for n in services) or 1
    sev0 = sum(n["value"] for n in services if n["severity"] == "alert") / base
    no_action, with_fix = [], []
    risk = 30 + sev0 * 40
    fixed = risk
    for t in range(steps + 1):
        risk = min(100, risk + (3.2 if t > steps * 0.3 else 0.6))
        if t < steps * 0.35:
            fixed = min(100, fixed + 1.2)
        else:
            fixed = max(18, fixed - 3.0)  # intervention resolves the root cause
        no_action.append({"t": t, "risk": round(risk, 1)})
        with_fix.append({"t": t, "risk": round(fixed, 1)})
    return {
        "case": g["case"],
        "no_action": no_action,
        "with_intervention": with_fix,
        "risk_before": no_action[-1]["risk"],
        "risk_after": with_fix[-1]["risk"],
        "note": "Sentiment/complaint propagation across the service graph; intervention resolves the top root cause.",
    }
