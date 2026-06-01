# Jordan Crisis Management Simulation Engine — Recommended GitHub Repositories

*Curated, license-vetted open-source stack mapped to the platform architecture. Star counts and licenses verified via live GitHub data, 2026-05-31.*

**Legend** — Readiness: **[DROP-IN]** usable almost as-is · **[FRAMEWORK]** build on it · **[REFERENCE]** study, don't link.
License: ✅ permissive (MIT/Apache/BSD — safe for production transition) · ⚠️ copyleft/source-available (GPL/AGPL/EPL/BSL — flag before linking into a closed sovereign product).

---

## Water Security (flagship domain — Zarqa cascade)

| # | Use | Repo | URL | ★ | License | Tag |
|---|---|---|---|---|---|---|
| 1 | Hydraulics: pipe burst, pump outage, pressure-dependent demand | USEPA/WNTR | https://github.com/USEPA/WNTR | 433 | BSD-3 ✅ | [DROP-IN] |
| 2 | Canonical hydraulic + water-quality solver | OpenWaterAnalytics/EPANET | https://github.com/OpenWaterAnalytics/EPANET | 388 | MIT ✅ | [FRAMEWORK] |
| 3 | Scenario/event generator on EPANET | WaterFutures/EPyT-Flow | https://github.com/WaterFutures/EPyT-Flow | 40 | MIT ✅ | [DROP-IN] |
| 4 | Object-oriented EPANET wrapper | Vitens/epynet | https://github.com/Vitens/epynet | 44 | Apache-2.0 ✅ | [FRAMEWORK] |
| 5 | Reservoir allocation / time-to-depletion | pywr/pywr | https://github.com/pywr/pywr | 183 | GPL-3.0 ⚠️ | [REFERENCE] |
| 6 | Resource-network framework (mirrors CDG) | UMWRG/pynsim | https://github.com/UMWRG/pynsim | 50 | GPL-3.0 ⚠️ | [REFERENCE] |

## Public Health

| # | Use | Repo | URL | ★ | License | Tag |
|---|---|---|---|---|---|---|
| 7 | Disease outbreak (agent-based) | starsimhub/covasim | https://github.com/starsimhub/covasim | 287 | MIT ✅ | [DROP-IN] |
| 8 | Hospital / ICU / ventilator demand | CodeForPhilly/chime | https://github.com/CodeForPhilly/chime | 211 | MIT ✅ | [DROP-IN] |
| 9 | Epidemics directly on a graph | springer-math/EoN | https://github.com/springer-math/Mathematics-of-Epidemics-on-Networks | 165 | MIT ✅ | [FRAMEWORK] |
| 10 | Medicine shortage / multi-echelon inventory | hubbs5/or-gym | https://github.com/hubbs5/or-gym | 445 | MIT ✅ | [FRAMEWORK] |
| 11 | ER triage queue / surge (SimPy patterns) | health-data-science-OR/simpy-streamlit | https://github.com/health-data-science-OR/simpy-streamlit-tutorial | 11 | MIT ✅ | [REFERENCE] |

## Supply Chain & Transportation

| # | Use | Repo | URL | ★ | License | Tag |
|---|---|---|---|---|---|---|
| 12 | Traffic / congestion cascade (pure-Python) | toruseo/UXsim | https://github.com/toruseo/UXsim | 242 | MIT ✅ | [FRAMEWORK] |
| 13 | Traffic (high-fidelity, TraCI control) | eclipse-sumo/sumo | https://github.com/eclipse-sumo/sumo | 4.0k | EPL-2.0 ⚠️ | [FRAMEWORK] |
| 14 | Routing / resource allocation | google/or-tools | https://github.com/google/or-tools | 13.5k | Apache-2.0 ✅ | [FRAMEWORK] |
| 15 | Vehicle routing (lightweight) | PyVRP/PyVRP | https://github.com/PyVRP/PyVRP | 640 | MIT ✅ | [FRAMEWORK] |
| 16 | Discrete-event / time-to-stockout | salabim/salabim | https://github.com/salabim/salabim | 393 | MIT ✅ | [FRAMEWORK] |
| 17 | Supply-chain disruption (blueprint) | ccolon/disrupt-sc | https://github.com/ccolon/disrupt-sc | 14 | GPL-3.0 ⚠️ | [REFERENCE] |

## Crisis Intelligence Core

| # | Use | Repo | URL | ★ | License | Tag |
|---|---|---|---|---|---|---|
| 18 | CDG graph substrate (k-shortest-path) | Qiskit/rustworkx | https://github.com/Qiskit/rustworkx | 1.7k | Apache-2.0 ✅ | [DROP-IN] |
| 19 | Graph (prototyping) | networkx/networkx | https://github.com/networkx/networkx | 17k | BSD-3 ✅ | [DROP-IN] |
| 20 | Embeddable graph DB | kuzudb/kuzu | https://github.com/kuzudb/kuzu | 3.9k | MIT ✅ | [FRAMEWORK] |
| 21 | Root cause / causal (do-calculus) | py-why/dowhy | https://github.com/py-why/dowhy | 8.1k | MIT ✅ | [FRAMEWORK] |
| 22 | Bayesian networks | pgmpy/pgmpy | https://github.com/pgmpy/pgmpy | 3.3k | MIT ✅ | [DROP-IN] |
| 23 | Causal discovery (learn CDG edges) | py-why/causal-learn | https://github.com/py-why/causal-learn | 1.6k | MIT ✅ | [DROP-IN] |
| 23b | RCA algorithms (Random-Walk / Bayesian / ε-diagnosis) — mine the math, don't link (built for IT metrics, needs historical telemetry, dormant since 2023) | salesforce/PyRCA | https://github.com/salesforce/PyRCA | 555 | BSD-3 ✅ | [REFERENCE] |
| 24 | Streaming anomaly detection | online-ml/river | https://github.com/online-ml/river | 5.8k | BSD-3 ✅ | [DROP-IN] |
| 25 | Batch anomaly detection | yzhao062/pyod | https://github.com/yzhao062/pyod | 9.9k | BSD-2 ✅ | [DROP-IN] |
| 26 | Forecasting + prediction intervals + backtest | Nixtla/statsforecast | https://github.com/Nixtla/statsforecast | 4.8k | Apache-2.0 ✅ | [DROP-IN] |
| 27 | Forecasting (breadth) | unit8co/darts | https://github.com/unit8co/darts | 9.4k | Apache-2.0 ✅ | [DROP-IN] |
| 28 | Stock-and-flow / time-to-depletion | SDXorg/pysd | https://github.com/SDXorg/pysd | 451 | MIT ✅ | [DROP-IN] |
| 29 | Agent-based simulation (citizen/panic) | projectmesa/mesa | https://github.com/projectmesa/mesa | 3.7k | Apache-2.0 ✅ | [FRAMEWORK] |

## Platform & Experience Layer

| # | Use | Repo | URL | ★ | License | Tag |
|---|---|---|---|---|---|---|
| 30 | Synthetic dirty data + ground truth | joke2k/faker | https://github.com/joke2k/faker | 19.3k | MIT ✅ | [DROP-IN] |
| 31 | Statistical synthetic data (internal only) | sdv-dev/SDV | https://github.com/sdv-dev/SDV | 3.5k | BSL-1.1 ⚠️ | [FRAMEWORK] |
| 32 | Streaming ingestion (event-time/dedup) | quixio/quix-streams | https://github.com/quixio/quix-streams | 1.6k | Apache-2.0 ✅ | [FRAMEWORK] |
| 33 | API layer | fastapi/fastapi | https://github.com/fastapi/fastapi | 98.7k | MIT ✅ | [FRAMEWORK] |
| 34 | Canonical model / validation | pydantic/pydantic | https://github.com/pydantic/pydantic | 27.9k | MIT ✅ | [DROP-IN] |
| 35 | Geometry / point-in-polygon | shapely/shapely | https://github.com/shapely/shapely | 4.4k | BSD-3 ✅ | [DROP-IN] |
| 36 | Admin-boundary joins | geopandas/geopandas | https://github.com/geopandas/geopandas | 5.1k | BSD-3 ✅ | [DROP-IN] |
| 37 | Hex spatial indexing | uber/h3-py | https://github.com/uber/h3-py | 1.0k | Apache-2.0 ✅ | [DROP-IN] |
| 38 | Cockpit UI (rapid) | streamlit/streamlit | https://github.com/streamlit/streamlit | 44.8k | Apache-2.0 ✅ | [FRAMEWORK] |
| 39 | GPU geo map layers | visgl/deck.gl | https://github.com/visgl/deck.gl | 14.2k | MIT ✅ | [DROP-IN] |
| 40 | Open map renderer (no token lock-in) | maplibre/maplibre-gl-js | https://github.com/maplibre/maplibre-gl-js | 10.7k | BSD-3 ✅ | [DROP-IN] |
| 41 | BI dashboards (heavyweight) | apache/superset | https://github.com/apache/superset | 73k | Apache-2.0 ✅ | [REFERENCE] |
| 42 | RAG grounding (cited answers) | deepset-ai/haystack | https://github.com/deepset-ai/haystack | 25.4k | Apache-2.0 ✅ | [FRAMEWORK] |
| 43 | RAG source-node citations | run-llama/llama_index | https://github.com/run-llama/llama_index | 49.8k | MIT ✅ | [FRAMEWORK] |
| 44 | Durable workflow + immutable audit | temporalio/temporal | https://github.com/temporalio/temporal | 20.7k | MIT ✅ | [FRAMEWORK] |
| 45 | Append-only event store | pyeventsourcing/eventsourcing | https://github.com/pyeventsourcing/eventsourcing | 1.7k | BSD-3 ✅ | [DROP-IN] |
| 46 | Decision-gate state machine | pytransitions/transitions | https://github.com/pytransitions/transitions | 6.5k | MIT ✅ | [DROP-IN] |
| 47 | EOC data-model reference | sahana/eden | https://github.com/sahana/eden | — | MIT ✅ | [REFERENCE] |

---

## Recommended shortlist (all permissive-licensed)

| Layer | Pick(s) | Closes gap |
|---|---|---|
| Water (flagship) | WNTR + EPANET + EPyT-Flow | real hydraulics = defensible numbers |
| Health | Covasim + EoN (+ CHIME) | validated epidemic/hospital dynamics |
| Supply / Traffic | UXsim + PyVRP + salabim | congestion & stockout |
| CDG core | rustworkx | §1 traversal primitives |
| Root cause | DoWhy + pgmpy | G08 |
| Anomaly / forecast | River + Nixtla statsforecast | G08 (uncertainty + backtest) |
| Stock-and-flow | PySD | G16 |
| Synthetic data | Faker (you own ground truth) | G02 oracle wall |
| API / model | FastAPI + Pydantic v2 | — |
| Geospatial | Shapely + GeoPandas + H3 | — |
| Cockpit | Streamlit + deck.gl / MapLibre | — |
| Conversational | Haystack | G26 grounding |
| Audit / decision | Temporal + transitions | G03 / G10 |

## License watch-outs (production-transition risk)

| Flag | Projects |
|---|---|
| GPL / AGPL — don't link into closed sovereign product | pywr, pynsim, disrupt-sc, MATSim, Neo4j, igraph, graph-tool, Ushahidi, DEEP, InaSAFE |
| EPL-2.0 — weak-copyleft, usable but flag | SUMO |
| BSL-1.1 — source-available, not OSS (internal use OK) | SDV family, Memgraph |
