# Crisis-Solving Brain — Backend

**FastAPI + LangGraph + In-Memory Repos** | Zarqa Water Cascade MVP

## Quick Start

```bash
cd crisis/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Verify environment
python scripts/check_env.py

# Run unit tests
pytest tests/unit -v

# Run full MVP acceptance test (headless)
python scripts/run_demo.py --full

# Start API server
uvicorn app.main:app --reload --port 8000
```

## API Endpoints (17 total)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/incidents` | List incidents |
| GET | `/api/v1/incidents/{id}` | Get incident |
| GET | `/api/v1/incidents/{id}/graph` | Incident dependency graph (React Flow) |
| GET | `/api/v1/incidents/{id}/root-cause` | Root-cause analysis |
| POST | `/api/v1/incidents/{id}/run` | Run full 9-step loop |
| GET | `/api/v1/signals` | List signals |
| POST | `/api/v1/signals` | Ingest new signal |
| GET | `/api/v1/risk` | National risk index |
| GET | `/api/v1/solutions/{id}` | List ranked solutions |
| POST | `/api/v1/solutions/{id}/generate` | Generate candidate solutions |
| POST | `/api/v1/simulations` | Run before/after simulation |
| GET | `/api/v1/simulations/{id}` | Get simulation result |
| POST | `/api/v1/decisions` | Authorize a decision (human gate) |
| GET | `/api/v1/decisions/{id}` | Get decision |
| GET | `/api/v1/sources` | List registered sources |
| POST | `/api/v1/sources` | Register a new source |
| POST | `/api/v1/sources/{id}/activate` | Activate a source |
| DELETE | `/api/v1/sources/{id}` | Remove a source |

## Architecture

```
app/
├── core/          # Config, settings
├── llm/           # Ollama client (gemma4:26B, nomic-embed-text)
├── engine/        # Pure algorithms (graph, rootcause, risk, anomaly, sim)
├── swarm/         # LangGraph 9-step loop (ingest→...→learn)
├── packs/         # Domain Packs (water/)
├── sources/       # Source connectors (SCADA, 911, hospital, traffic, weather)
├── repositories/  # Data access (memory/ active, postgres/ deferred)
├── services/      # Application layer
├── api/           # REST + WebSocket
└── main.py        # FastAPI app factory
```

## Key Design Decisions

1. **Engine is pure** — `app/engine/` has zero I/O, no imports from repos/API/LLM
2. **DB is deferred** — In-memory repos seeded from `data/seeds/zarqa.json`; flip `REPO_BACKEND=postgres` later
3. **LLM is local Ollama** — `gemma4:26B` for chat, `nomic-embed-text` for embeddings
4. **Numbers from engine, prose from LLM** — The root-cause apex (PIPE-ZN-44) is computed, not hallucinated

## MVP Acceptance

```
✓ Root cause: PIPE-ZN-44 (not the loud 911 surge)
✓ Simulation: risk 84 → 22 (validated fix)
✓ Decision: authorized by commander
✓ Audit artifact: persisted to data/artifacts/
```
