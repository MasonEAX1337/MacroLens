# MacroLens

MacroLens is an AI-powered economic event explorer.

It ingests economic and market datasets, detects unusual events in those datasets, finds related movements in other series, and presents an explanation workflow through a web UI.

The core idea is simple:

most charting tools show you that something moved.
MacroLens tries to help you investigate why it might have moved.

## System Pipeline

```mermaid
flowchart TD
    A["Data Sources"] --> B["Ingestion Clients"]
    B --> C["PostgreSQL"]
    C --> D["Anomaly Detection"]
    C --> E["Correlation Engine"]
    C --> F["Explanation Engine"]
    D --> G["FastAPI"]
    E --> G
    F --> G
    G --> H["React UI"]
```

## Project Motivation

MacroLens was built as a systems project around a question most charting tools do not try to answer: not just what moved in economic data, but what evidence might help explain why it moved.

The project also intentionally explores a modern development workflow that combines traditional engineering with AI-assisted coding. The goal is not to treat AI as a code generator, but to use it inside a disciplined engineering process that still includes system design, explicit data pipelines, reproducible experiments, architectural decision records, structured debugging, and documentation.

The repository therefore emphasizes not only the final implementation, but also the reasoning process behind it. Development logs, experiment records, decision records, and bug investigations are part of the project by design.

## What MacroLens Does

For each supported dataset, MacroLens can:

- ingest historical data from external sources
- normalize and store it in PostgreSQL
- detect anomalies with rolling z-score logic
- group nearby anomalies into persisted macro-event clusters
- compute lag-aware correlations against other datasets
- retrieve article context around anomaly windows
- generate explanation text from stored evidence
- trace suggested downstream propagation paths from one macro-event cluster to later clusters
- expose all of that through an API and frontend investigation interface

## What Makes This Project Interesting

This is not just a chart viewer.

The system is built as an evidence pipeline:

1. raw data is fetched from source APIs
2. normalized data is stored in PostgreSQL
3. anomalies are persisted as first-class events
4. nearby anomalies are grouped into persisted macro-event clusters
5. downstream propagation links are derived from persisted lagged relationships and later anomaly matches
6. correlations are persisted as supporting evidence
7. article context is persisted as cited event evidence
8. explanations are generated from stored system state
9. the frontend lets a user inspect the result

That makes the repo more than a frontend demo. The backend reasoning chain is the actual product.

## Current Project Status

MacroLens currently has a working end-to-end MVP slice.

### Implemented

- FastAPI backend
- PostgreSQL schema
- CoinGecko ingestion for Bitcoin
- FRED ingestion for CPI, Federal Funds Rate, WTI oil, S&P 500, and household macro series
- rolling z-score anomaly detection
- lag-aware correlation discovery on percent changes
- persisted anomaly clustering into macro-event groups
- cluster-to-cluster propagation timeline generation
- stored news-context retrieval through GDELT
- explanation generation through a provider abstraction
- React frontend connected to the live API

### Current explanation model

The current default explanation provider is `rules_based`.

MacroLens now also includes `openai` and `gemini` provider paths behind the same provider abstraction.

That means:

- the default local workflow remains deterministic and cheap
- a live hosted model can be enabled through environment variables
- the system keeps the rules-based provider as fallback

The hosted-provider paths are implemented and have been validated on live anomalies, but they should still be treated as staged integrations rather than production-ready defaults. Prompt quality, comparative evaluation, and failure-handling polish are still part of the next phase.

### Current news context model

MacroLens now uses a hybrid contextual-evidence approach.

That layer:

- retrieves live article citations around an anomaly window
- stores those articles separately from correlations
- adds curated macro-timeline context for household series when live retrieval is weak
- exposes both through the anomaly detail API
- allows the explainer to use cited context instead of relying only on market-to-market relationships

The current providers are:

- `gdelt` for live historical article search
- `macro_timeline` for curated historical regime context on slower household series

The current ranking pass also applies:

- dataset-aware keyword queries
- title-based relevance filtering
- duplicate suppression
- timing-aware ranking around the anomaly date
- provider ordering that surfaces curated historical context ahead of weaker live retrieval when appropriate

### Not complete yet

- comparison mode across datasets
- production deployment workflow

## Current Datasets

Implemented datasets:

- Bitcoin Price
- Consumer Price Index
- Federal Funds Rate
- WTI Oil Price
- S&P 500 Index
- Case-Shiller U.S. National Home Price Index
- 30-Year Fixed Rate Mortgage Average in the United States
- Real Disposable Personal Income Per Capita

## High-Level Architecture

```text
CoinGecko / FRED
    -> ingestion clients
    -> normalization
    -> PostgreSQL
    -> anomaly detection
    -> correlation engine
    -> news context retrieval
    -> explanation engine
    -> FastAPI
    -> React frontend
```

## Repository Structure

```text
MacroLens/
  documentation/   product, architecture, decisions, bugs, experiments, logs
  backend/         FastAPI app, services, provider clients, tests
  frontend/        React app
  database/        PostgreSQL schema
  scripts/         ingestion entry points
  docker-compose.yml
  .env.example
```

## Prerequisites

You should have the following installed:

- Python 3.13 or compatible
- Node.js and npm
- Docker Desktop or another way to run PostgreSQL

## Environment Setup

Copy the environment template:

```powershell
Copy-Item .env.example .env
```

Important variables in `.env`:

- `DATABASE_URL`: PostgreSQL connection string
- `FRED_API_KEY`: required for FRED datasets
- `CORS_ALLOWED_ORIGINS`: frontend origins allowed to call the API
- `EXPLANATION_PROVIDER`: `rules_based`, `openai`, or `gemini`
- `EXPLANATION_FALLBACK_PROVIDER`: fallback provider if the primary provider fails
- `EXPLANATION_MODEL`: provider/model label stored with generated explanations
- `OPENAI_MODEL`: model used when `EXPLANATION_PROVIDER=openai`
- `OPENAI_API_KEY`: required when using the OpenAI provider
- `GEMINI_MODEL`: model used when `EXPLANATION_PROVIDER=gemini`
- `GEMINI_API_KEY`: required when using the Gemini provider
- `NEWS_CONTEXT_PROVIDER`: current news provider mode, supports `gdelt`, `macro_timeline`, or `hybrid`
- `NEWS_CONTEXT_WINDOW_DAYS`: retrieval window around anomaly timestamps
- `NEWS_CONTEXT_MAX_ARTICLES`: max stored articles per anomaly
- `ANOMALY_CLUSTER_WINDOW_DAYS`: max gap in days between adjacent anomalies inside the same cluster

## Local Setup

### 1. Create the Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
```

Important:

run the backend through the virtual environment. Do not use a global `uvicorn` install unless your venv is activated.

### 2. Start PostgreSQL

If you are using the included Docker Compose file:

```powershell
docker compose up -d db
```

### 3. Apply the schema

If you are using the compose-managed container from this repo:

```powershell
docker exec -i macrolens-db psql -U postgres -d macrolens < database\schema.sql
```

If your container has a different name, adjust the container name accordingly.

### 4. Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

## Running the Project

### Start the backend

From the repo root:

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --app-dir backend
```

Backend URLs:

- API root: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Load data into PostgreSQL

From the repo root:

```powershell
.\.venv\Scripts\python scripts\ingest\run_ingestion.py --dataset bitcoin --dataset cpi --dataset fed_funds --dataset wti --dataset sp500 --dataset house_price_us --dataset mortgage_30y --dataset income_real_per_capita
```

What this command does:

- fetches source data
- refreshes stored rows for each selected dataset
- runs anomaly detection
- recomputes anomaly clusters
- runs correlation computation
- fetches and stores news context
- runs explanation generation

Available dataset flags:

- `bitcoin`
- `cpi`
- `fed_funds`
- `wti`
- `sp500`
- `house_price_us`
- `mortgage_30y`
- `income_real_per_capita`

Optional ingestion flags:

- `--skip-anomaly-detection`
- `--skip-clustering`
- `--skip-correlation`
- `--skip-news-context`
- `--skip-explanations`

### Recompute anomaly clusters without re-ingesting data

If you want to refresh macro-event clusters from the current anomaly table:

```powershell
.\.venv\Scripts\python scripts\clusters\recompute_clusters.py
```

### Fetch news context without re-ingesting data

If you want to backfill or refresh article context for stored anomalies:

```powershell
.\.venv\Scripts\python scripts\news\fetch_news_context.py
```

To fetch only one anomaly:

```powershell
.\.venv\Scripts\python scripts\news\fetch_news_context.py --anomaly-id 91
```

### Regenerate explanations without re-ingesting data

If you change explanation provider settings and want to regenerate explanation text from existing stored anomalies:

```powershell
.\.venv\Scripts\python scripts\explanations\generate_explanations.py
```

To regenerate only one anomaly:

```powershell
.\.venv\Scripts\python scripts\explanations\generate_explanations.py --anomaly-id 91
```

### View stored explanations from PostgreSQL

To inspect explanations without raw API output:

```powershell
.\.venv\Scripts\python scripts\explanations\view_explanations.py --anomaly-id 91
```

To compare only Gemini-generated explanations:

```powershell
.\.venv\Scripts\python scripts\explanations\view_explanations.py --provider gemini --limit 5
```

### Start the frontend

From the repo root:

```powershell
npm run dev --prefix frontend
```

Frontend URL:

- [http://localhost:5173](http://localhost:5173)

The Vite config proxies `/api` requests to `http://127.0.0.1:8000`.

## Typical Local Workflow

1. start PostgreSQL
2. start the backend
3. run ingestion
4. start the frontend
5. open the UI and inspect datasets and anomalies

## API Endpoints

Current core endpoints:

- `GET /api/v1/datasets`
- `GET /api/v1/datasets/{id}/timeseries`
- `GET /api/v1/datasets/{id}/anomalies`
- `GET /api/v1/anomalies/{id}`
- `POST /api/v1/anomalies/{id}/regenerate-explanation`

The anomaly detail endpoint returns:

- anomaly metadata
- macro-event cluster membership
- suggested downstream propagation edges
- correlated datasets
- stored news context
- news-context availability status
- generated explanations

## Frontend Experience

The current frontend supports:

- dataset selection
- date-window filtering
- minimum-severity filtering
- direction filtering
- multi-dataset 3D constellation view
- live timeseries rendering
- chart brush for local zooming
- anomaly markers on the chart
- anomaly selection from the chart or event list
- anomaly selection from the 3D constellation
- macro-event cluster inspection for the selected anomaly
- propagation timeline cards with click-through investigation
- evidence provenance in the event panel
- cited news context in the event panel
- curated macro-timeline context for selected household anomalies
- explicit news-context status notes when the provider could not supply trustworthy citations
- article timing badges in the event panel
- explanation regeneration from the event panel
- detail panel with correlations and explanations

The current design intent is:

chart first, evidence second, explanation third

The 3D constellation adds a second layer:

macro field first, dataset investigation second, explanation third

## Running Tests

### Backend tests

From the repo root:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python -m pytest backend\tests -q
```

This suite now includes Postgres-backed API integration tests. If PostgreSQL is not available locally, the integration subset will skip cleanly.

### Frontend production build

From the repo root:

```powershell
npm run build --prefix frontend
```

## Documentation

The repository documentation is part of the engineering system, not an afterthought.

See the [documentation](documentation/) folder for:

- product docs
- architecture docs
- development logs
- experiment records
- decision records
- bug investigations
- research notes

Useful entry points:

- [MVP.md](documentation/MVP.md)
- [DevelopmentPlan.md](documentation/DevelopmentPlan.md)
- [system_overview.md](documentation/architecture/system_overview.md)
- [event_clustering.md](documentation/architecture/event_clustering.md)
- [propagation_timeline.md](documentation/architecture/propagation_timeline.md)
- [news_context_engine.md](documentation/architecture/news_context_engine.md)

## Current Limitations

- explanations are rules-based by default even though OpenAI-backed and Gemini-backed provider paths now exist
- correlations are useful but should not be interpreted as causal proof
- anomaly clustering is time-proximity based today, so a cluster is a useful event envelope rather than proof of shared causation
- propagation timelines are conservative downstream suggestions, not causal proof
- live news retrieval is still keyword-based, so relevance quality is still uneven
- household macro anomalies now fall back to curated macro-timeline context for selected historical regimes, but that timeline is intentionally sparse rather than comprehensive
- mixed-frequency analysis is still coarse
- monthly and weekly household macro series are useful, but they will naturally produce fewer clean event explanations than daily market series
- current ingestion uses full refresh for implemented sources
- the new Three.js constellation view is visually stronger, but it increases frontend bundle weight and should be optimized if kept as a permanent default surface
- there is no production deployment path yet

## What To Build Next

The next highest-value steps are:

1. evaluate OpenAI and Gemini explanation quality more systematically
2. add explicit evidence-strength decomposition for propagation edges and explanations
3. expand curated macro-timeline coverage beyond the first household regimes
4. improve article ranking and filtering quality for live news retrieval
5. experiment with change-point detection alongside z-score
6. optimize and deepen the new multi-dataset constellation view
7. add a documented refresh and deployment workflow

## Why This Repo Is Structured This Way

The goal is to show system thinking, not just code volume.

MacroLens is meant to demonstrate:

- data pipeline design
- anomaly detection reasoning
- cross-dataset analysis
- evidence-backed explanation generation
- engineering documentation discipline

That combination is the point of the project.
