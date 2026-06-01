# V2 — Real Pipeline, Console Pages & LLM Reasoning

AEGIS connects a real Voice-of-Customer database (**voc360**, PostgreSQL 16, read-only)
to a graph-based crisis brain: every citizen **signal** is wired into a dependency
graph, the RIL pipeline surfaces **root-cause clusters**, and the system drafts a
**validated solution**. V2 makes that chain *genuinely connected* end-to-end on real
data and builds out the operator console on top of it.

Three tracks:

| Track | What it delivers |
|-------|------------------|
| **T1 — Real Pipeline** | Recover the broken `segment ↔ signal` join **by text** so the graph truly chains `signal → segment → cluster → service`. Replace keyword-guessed cluster links with **real recovered edges** and surface a **signal count per cluster**. |
| **T2 — Console Pages** | Build the remaining sidebar pages on **real voc360** — Signals, Root Cause, Solutions, Simulation, Decisions — and make the Dashboard KPIs / chart / table reflect real voc360 instead of the Zarqa demo fixtures. |
| **T3 — LLM Reasoning + Valid Solution** | Translate Arabic cluster/service labels to English (**build-time map**); add a **valid-solution engine** (cause → countermeasure → feasibility → expected impact); add an **optional LLM narration node** to the Deer Graph flow with a grounded deterministic fallback. |

Constraints that shape every track: **no OpenAI/Anthropic key** in env (so no re-embedding
and no cloud LLM), **voc360 is READ-ONLY** (only `plpgsql`; no `pgvector` / `pg_trgm`),
and the embedding/centroid vectors are 1536-dim OpenAI vectors we cannot regenerate.
Everything below works without an API key.

---

## Real voc360 numbers (the data these tracks run on)

| Layer | Table | Rows |
|-------|-------|------|
| Signal / data-source | `the_data` | **22,882** |
| — distinct services | `the_data.service_id` | ~150+ (top: Sanad 15.8k, Amman Bus 2k) |
| — distinct sources | `the_data.source_type` | app_review 18.6k, social_media_sentiment 1.6k, … |
| Extracted problem segments | `ril_text_segments` | **2,001** |
| Segment → cluster membership | `ril_cluster_members` | **903** |
| Root-cause clusters | `ril_problem_clusters` | **21** (20 with members) |

Top clusters by `member_count`: **551, 69, 64, 55, 52, 23, 18, 9, 9, 9, 8, 7, …** —
e.g. `رسوم الخدمة المستعجلة` (urgent-service fees, 551), `تأخير دعم صندوق المعونة`
(National-Aid-Fund delays), `الباص السريع` (the BRT bus), `منصة تكافل` (the Takaful platform).

---

# T1 — Real Pipeline (text-recovery join)

## The problem

The RIL pipeline (`ril_text_segments` → `ril_cluster_members` → `ril_problem_clusters`)
ran on a **separate snapshot**, so `ril_text_segments.record_id` **does not join** to
`the_data.record_id`. Before V2 the graph faked the cluster → service link with an
Arabic-keyword heuristic (`_match_service`), so the root-cause layer was only *loosely*
attached to the live service graph.

## The insight (verified live against voc360)

Each `ril_text_segments.segment_text` is a **substring of a real `the_data.text /
text_clean` row** — the segment was *extracted from* that signal. So the join is
recoverable **by text**, with **no embeddings and no API**:

```
the_data.text / text_clean  ──(segment is a substring)──▶  ril_text_segments.segment_text
        │                                                          │
  service_id, governorate                                   ril_cluster_members
                                                                   │
                                                          ril_problem_clusters (cluster_id)
```

Recovered edge: **`Service(svc::<service_id>) ──root_cause──▶ Cluster(cl::<cluster_id[:8]>)`**,
weight = number of recovered signals bridging that (service, cluster) pair.

## What changed

**New module `backend/app/cluster_link.py`** — recovers the link map and caches it.

- `_compute()` — one query pulls every `(cluster_id, segment_text)` from
  `ril_cluster_members ⋈ ril_text_segments` (filtered `length(segment_text) > 12`);
  a second pulls every `(coalesce(text_clean,text), service_id, governorate)` from
  `the_data WHERE service_id IS NOT NULL`. For each segment it takes the first
  `the_data` row whose text **contains** the segment's leading 50 chars, tallying
  `Counter`s per cluster for services, governorates, and a raw signal count.
- `links(refresh=False) -> dict` — module-cached map; reads `backend/data/cluster_links.json`
  if present, else computes and writes it. O(1) at request time.
- `cluster_services(cluster_id) -> list[(service_id, count)]` — recovered services for a cluster.
- `cluster_signals(cluster_id) -> int` — recovered signal count for a cluster.
- `service_cluster_edges(min_weight=2) -> list[(service_id, cluster_id, weight)]`.

**`backend/data/cluster_links.json` shape** (one entry per cluster):
```json
{
  "b39d06f6-a146-43d1-b921-f7e33d34b7b9": {
    "services": [["نقل_عام", 309], ["طرق_وبنية_تحتية", 184], ["general", 6], ["Takaful", 6]],
    "governorates": [["عمان", 3], ["العقبة", 1]],
    "signals": 551
  }
}
```

**`graph_builder.build_graph()` now prefers real edges.** After each cluster node is
added it calls `cluster_link.cluster_services(cluster_id)`; if recovery returned
anything it emits real `kind="root_cause"` edges `svc::<service_id> → cl::<cluster_id[:8]>`
(creating the service node if the cluster pointed at a service outside the top-16) and
sets `node["signals"]` from `cluster_link.cluster_signals(...)`. The **keyword
`_match_service` heuristic is now fallback-only** — used only when `cluster_link` is
unavailable or a cluster recovered zero signals. `cluster_link` is imported behind a
`try/except` (`_HAS_LINK`), so the graph still builds if the cache and DB are both gone.

## Verified result (current `cluster_links.json`)

- **20 clusters hit**, **903 signals recovered** (every cluster member linked back to a real signal).
- Top cluster `b39d06f6…` (551 members) recovers to `نقل_عام` (309) and `طرق_وبنية_تحتية` (184) — i.e. it really is a **public-transit / roads-and-infrastructure** problem, recovered from the data rather than guessed from keywords.

## How to run T1

```bash
cd backend
cp .env.example .env          # set VOC_DSN (read-only voc360 DSN)
# rebuild the cache (read-only; writes backend/data/cluster_links.json):
./.venv/bin/python -c "from app import cluster_link; cluster_link.links(refresh=True)"
```

`GET /api/graph` then returns `root_cause` edges sourced from real recovered links, and
cluster nodes carry a `signals` count. If the DB is unreachable, the committed
`cluster_links.json` keeps the graph fully connected offline.

---

# T2 — Console Pages on real voc360

The console (React 18 + TS · Vite · Tailwind · reactflow · recharts) ships sidebar pages
that, before V2, rendered the **Zarqa demo fixtures** (`frontend/src/lib/data.ts`). T2
rebuilds them on **real voc360** and adds the missing pages. The sidebar already lists
the targets: **Dashboard · Signals · Incident Graph · Root Cause · Solutions · Simulation · Decisions**.

## New backend endpoints (`backend/app/main.py`)

All read-only, grounded in `the_data` / `ril_problem_clusters`, Arabic-safe (`ensure_ascii=False`).

| Endpoint | Purpose | Response (shape) |
|----------|---------|------------------|
| `GET /api/kpis` | Real Dashboard KPIs | `{total, negative_pct, critical, top_service, deltas}` |
| `GET /api/signal_volume?range=` | Dashboard chart | `[{t, v}]` series from `observed_at` / `date` |
| `GET /api/signals` | Signals page (paged + filtered) | `{rows:[…], total}` — filters: `page,size,service,severity,source,sentiment,q` |
| `GET /api/solutions` | Solutions page (T3 engine) | per-cluster valid solutions (see T3) |
| `GET /api/decisions` · `POST /api/decisions` | Decisions log | in-memory decision log (read + append) |
| `POST /api/narrate` | LLM/grounded narration (T3) | `{text, engine}` |

Existing endpoints are unchanged: `/api/health`, `/api/stats`, `/api/cases`,
`/api/graph`, `/api/rootcause`, `/api/flow/run`, `/api/simulate`.

## Frontend pages

`App.tsx` switches views via `Sidebar.onNavigate(label)`. `GRAPH_VIEWS` (`Incident
Graph`, `Root Cause`) render `<LiveGraph/>`; the other labels now map to dedicated pages:

- **Dashboard** — KPI cards from `/api/kpis`, signal-volume chart from `/api/signal_volume`,
  and a real signals table from `/api/signals` (replaces the static `kpis` / `signalVolume`
  / `signals` fixtures in `lib/data.ts`).
- **Signals** — paginated, filterable table over `the_data` (`/api/signals`): service,
  severity, source, sentiment, and free-text `q`.
- **Root Cause** — ranked `ril_problem_clusters` with Arabic label + English gloss (T3),
  member count, severity, score, sample evidence segments, and now the recovered **signal
  count** and **linked services** from T1.
- **Solutions** — the valid-solution cards from `/api/solutions` (T3 engine).
- **Simulation** — the Mesa before/after A/B from `/api/simulate` (already real).
- **Decisions** — an operator decision log backed by `/api/decisions` (in-memory).

The API client (`frontend/src/lib/voc.ts`) gains typed helpers for each new endpoint
alongside the existing `getGraph` / `getRootCause` / `getStats` / `runFlow` / `getSimulate`.

## How to run T2

```bash
# backend (serves the new endpoints)
cd backend && ./.venv/bin/uvicorn app.main:app --reload --port 8000
# frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```

---

# T3 — LLM Reasoning + Valid Solution

## 3a. Build-time Arabic → English translation

voc360 labels (`canonical_label_ar`, `service_id`) are Arabic, and there is **no LLM key**
to translate at runtime. So the agents translate them **at build time** into a static map.

- **`frontend/src/lib/labels.ts`** — exports `LABELS: Record<string,string>` (the `{ar:en}`
  map) plus a `t(s)` helper that returns the English label if known, else the original
  string. Proper nouns are kept/transliterated; complaint labels get a short English gist
  (≤ 8 words). Used across the Root Cause / Solutions / graph views so the operator sees
  English while the underlying Arabic is preserved.
- Cluster rows already carry `canonical_label_en` where present; `t()` fills the gaps.

## 3b. Valid-solution engine — `backend/app/solution.py`

Turns a ranked root cause into an **actionable, feasibility-rated countermeasure**, grounded
in the cluster theme — no LLM required.

- Maps the cluster's Arabic theme (keyword → countermeasure) and combines it with the
  `rootcause` ranking (`member_count × (0.5 + severity_avg)`).
- Per cluster it returns:
  ```
  {
    cluster_id, label_ar, label_en, members, severity_avg,
    actions: [{ agency, action, expected_impact, feasibility, timeframe }],
    confidence,
    recommendation
  }
  ```
  `expected_impact` and `feasibility` are derived deterministically from member volume,
  severity, and the countermeasure class, so the same input always yields the same plan.
- Served at `GET /api/solutions` and rendered on the **Solutions** page; optionally enriched
  by the LLM narrator (3c) when a local model is available.

## 3c. Optional LLM narration — `backend/app/llm.py`

A **local-only** model client with a **grounded deterministic fallback** — no API key, no
hard pip dependency (stdlib `urllib` only, import-safe).

- Env: `LLM_BASE_URL` (default `http://localhost:11434`) and `LLM_MODEL` (default e.g.
  `qwen2.5:7b`) — an **Ollama / OpenAI-compatible** server on localhost.
- `narrate(prompt, context) -> str` POSTs to the local server (`/api/chat` or
  `/v1/chat/completions`) with a **short timeout**. If the server is unreachable, it falls
  back to a **deterministic grounded summary** built from `context` (the real root cause,
  member count, severity, and recovered services) — so the narration is always faithful
  to the data, never hallucinated, and never blocks.
- Exposed at `POST /api/narrate`, returning `{text, engine}` where `engine` is `"llm"` or
  `"grounded"`.

## 3d. Deer Graph narration node

The Deer Graph flow (`backend/app/deer_flow.py`, a LangGraph `StateGraph` with a pure-Python
fallback runner) gains an **optional narration node** after `recommend`: it calls
`llm.narrate(...)` with the grounded case context and streams the result as a `narrate`
FlowEvent stage. Because `narrate()` always returns (LLM **or** grounded fallback), the
flow's streamed cadence — `connect → ingest → graph → rootcause → recommend → narrate` —
holds whether or not a local model is running.

## How to run T3

```bash
# optional: a local model for richer narration (otherwise grounded fallback is used)
ollama serve &
ollama pull qwen2.5:7b
export LLM_BASE_URL=http://localhost:11434 LLM_MODEL=qwen2.5:7b

# solutions + narration are served by the same backend:
cd backend && ./.venv/bin/uvicorn app.main:app --reload --port 8000
curl -s localhost:8000/api/solutions | head
curl -s -X POST localhost:8000/api/narrate -d '{}' | head
```

With **no** local model running, `/api/narrate` and the deer-flow narration node return
`engine:"grounded"` — fully functional, fully grounded in real voc360.

---

## End-to-end summary

```
voc360 (read-only)
   │  the_data 22,882 signals
   ▼
T1  text-recovery join  →  signal → segment → cluster → service   (903 signals, 20 clusters)
   │  cluster_link.py + backend/data/cluster_links.json
   ▼
graph_builder  →  real root_cause edges + per-cluster signal counts
   │
   ├─ T2 console pages  (/api/kpis, /api/signal_volume, /api/signals, /api/solutions, /api/decisions)
   │     Dashboard · Signals · Root Cause · Solutions · Simulation · Decisions  — all real voc360
   │
   └─ T3 reasoning
         labels.ts        Arabic → English (build-time map + t())
         solution.py      cause → countermeasure → feasibility → expected impact  (/api/solutions)
         llm.py           narrate() — local Ollama OR grounded fallback           (/api/narrate)
         deer_flow.py     optional narration node (connect→…→recommend→narrate)
```

No API key anywhere. voc360 stays read-only. Every number above is real voc360 data, and
the graph is genuinely connected — signals → segments → clusters → services → solution.
