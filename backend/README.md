# AEGIS Deer Graph — Backend

A FastAPI service that connects to the **voc360** Voice-of-Customer database (read-only) and runs the live **data source → graph → root cause** flow.

## Run

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env          # fill in VOC_DSN (never commit the real .env)
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | voc360 connectivity |
| GET | `/api/stats` | row counts (signals, services, clusters…) |
| GET | `/api/cases` | selectable cases (services + top root causes) |
| GET | `/api/graph?case=` | the live dependency graph (nodes + edges) |
| GET | `/api/rootcause?limit=` | ranked RIL problem clusters + recommendation |
| POST | `/api/flow/run?case=` | the Deer Graph flow, streamed as NDJSON stages |
| POST | `/api/simulate?case=` | sentiment-propagation simulation (before/after) |

## Layout

```
app/
├── main.py           # FastAPI app + endpoints + the streamed flow
├── db.py             # read-only psycopg connection to voc360
├── graph_builder.py  # Source → Service → Governorate + RIL root-cause clusters
└── rootcause.py      # rank ril_problem_clusters by member_count × severity
```

The graph is built entirely from real tables: `the_data` (signals) and
`ril_problem_clusters` / `ril_cluster_members` / `ril_text_segments` (the RIL
root-cause clustering pipeline). See `../docs/VOC360_SCHEMA.md`.

> Security: the service enforces a read-only session and reads its DSN from
> `VOC_DSN` (in `.env`, which is git-ignored). No credentials live in code.
