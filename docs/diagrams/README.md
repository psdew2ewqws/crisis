# AEGIS Workflow Diagrams

Visual companion to [`../SYSTEM_WORKFLOW_MAP.md`](../SYSTEM_WORKFLOW_MAP.md). Each diagram exists in
three forms so you can drop it anywhere:

| You want to… | Use |
|---|---|
| Put it in a slide / take a screenshot | the **`.png`** (3× resolution, ~2.3k–4.4k px wide) |
| Embed in a PDF / print / scale infinitely | the **`.svg`** (vector, stays crisp) |
| Hand someone the whole set as one document | **`AEGIS-Workflow-Diagrams.pdf`** (8 pages: cover + 7) |
| Browse / re-export | open **`index.html`** in a browser → ⌘P → *Save as PDF* |

## The 7 diagrams

| # | Source | Shows |
|---|---|---|
| 01 | `01-system-map.mmd` | Browser → FastAPI → optional engines → voc360 |
| 02 | `02-app-composition.mmd` | `main.py` mounting routers behind try/except |
| 03 | `03-deer-graph-flow.mmd` | the streamed connect→ingest→graph→rootcause→recommend pipeline |
| 04 | `04-v3-reasoning.mmd` | forecast / whys / validate / ask / suggest engines |
| 05 | `05-debate-sequence.mmd` | multi-agent debate sequence |
| 06 | `06-run-analysis-sequence.mmd` | live NDJSON "Run Analysis" streaming |
| 07 | `07-operator-journey.mmd` | the master operator workflow |

## Editing / re-rendering

The `.mmd` files are [Mermaid](https://mermaid.live) source — edit them (or paste into
mermaid.live), then regenerate every output with:

```bash
./render.sh
```

`render.sh` reuses a cached Playwright Chromium so it won't download its own. Config lives in
`mermaid-config.json` (dark theme) and `puppeteer.json` (Chromium path — adjust if yours differs).
