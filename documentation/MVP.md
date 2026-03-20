# MacroLens MVP

## Purpose

MacroLens is an open source system for investigating unusual economic events in time series data.

It does not try to be a full macroeconomic intelligence platform. The MVP is a narrower claim:

given a dataset, the system should ingest the data, detect abnormal movements, compare those movements against adjacent datasets, and present a concise explanation workflow to the user.

## Product Thesis

Raw charts are not enough.

A user may notice that Bitcoin dropped, oil spiked, or inflation climbed, but the real questions are:

- was this move actually unusual
- what else moved around the same time
- what evidence exists for a plausible explanation

MacroLens exists to compress that reasoning path into a single interface.

## MVP Scope

The MVP includes:

- ingestion of a small, recognizable set of macro and market datasets
- PostgreSQL as the central evidence store
- anomaly detection on normalized time series data
- persisted clustering of nearby anomalies into macro events
- lag-aware correlation discovery around anomaly windows
- propagation timelines between macro-event clusters
- article-context retrieval around anomaly windows
- explanation generation from stored system evidence
- a frontend investigation interface with chart markers and event details

The MVP excludes:

- user accounts
- alerting and notification workflows
- forecasting and predictive models
- causal inference
- institutional-grade news retrieval and ranking
- streaming or real-time processing

## Current State Snapshot

As of March 12, 2026, the repository contains a working end-to-end vertical slice.

### What is implemented

- PostgreSQL schema with datasets, points, anomalies, anomaly clusters, correlations, news context, explanations, and ingestion runs
- data ingestion for Bitcoin, CPI, Federal Funds Rate, WTI oil, and S&P 500
- data ingestion for a first household macro cluster: U.S. house prices, 30-year mortgage rates, and real disposable personal income per capita
- rolling z-score anomaly detection with frequency-aware defaults
- `change_point` anomaly detection for structural shifts
- lag-aware correlation scoring on percent changes
- persisted article-context retrieval through GDELT
- explanation generation through a provider abstraction
- FastAPI endpoints for datasets, timeseries, anomalies, and anomaly detail
- React frontend that renders charts, anomaly markers, correlations, cited news context, and explanations
- React frontend that also shows the macro-event cluster surrounding the selected anomaly
- React frontend that now also shows suggested downstream propagation paths

### What is not fully implemented yet

- the current default explanation provider is still rules-based
- OpenAI-backed and Gemini-backed provider paths now exist and have been validated on live anomalies, but are not yet treated as production-ready defaults
- frontend now supports range and anomaly filtering plus explanation regeneration, but still lacks dataset-comparison controls
- the current news layer is keyword-based retrieval, so ranking quality and timing interpretation are still limited

This distinction matters. The repo now proves the system shape, but not every promised enhancement.

## Current Dataset Coverage

### Implemented

- Bitcoin price via CoinGecko
- CPI via FRED
- Federal Funds Rate via FRED
- WTI oil price via FRED
- S&P 500 index via FRED
- Case-Shiller U.S. National Home Price Index via FRED
- 30-Year Fixed Rate Mortgage Average in the United States via FRED
- Real Disposable Personal Income Per Capita via FRED

## Core User Flow

1. The user opens the app.
2. The user selects a dataset.
3. The system renders the dataset history.
4. Detected anomalies appear as event markers.
5. The user selects an anomaly.
6. The system shows:
   - anomaly metadata
   - macro-event cluster membership
   - suggested downstream propagation paths
   - correlated datasets
   - cited news context
   - generated explanation text
   - evidence-backed limitations of interpretation

## System Flow

```text
Source APIs
  -> normalization
  -> PostgreSQL
  -> anomaly detection
  -> correlation engine
  -> news context retrieval
  -> explanation generation
  -> FastAPI
  -> React investigation UI
```

## Architecture Principle

MacroLens is only credible if the output chain is evidence-first.

That means:

1. data must be normalized before storage
2. anomalies must be stored, not inferred live in the UI
3. correlations must be persisted as evidence, not recomputed ad hoc for every click
4. contextual article evidence must be stored separately from statistical relationships
5. explanations must be downstream of stored facts

If any of those steps are skipped, the product becomes presentation without reasoning.

## Data Model

### `datasets`

Stores dataset identity and metadata.

Key fields:

- `id`
- `name`
- `symbol`
- `source`
- `description`
- `frequency`

### `data_points`

Stores normalized observations.

Key fields:

- `dataset_id`
- `timestamp`
- `value`

### `anomalies`

Stores detected unusual events.

Key fields:

- `dataset_id`
- `timestamp`
- `severity_score`
- `direction`
- `detection_method`
- `metadata`

### `correlations`

Stores strongest related datasets around a given anomaly.

Key fields:

- `anomaly_id`
- `related_dataset_id`
- `correlation_score`
- `lag_days`
- `method`

### `anomaly_clusters`

Stores grouped macro events built from nearby anomalies.

Key fields:

- `start_timestamp`
- `end_timestamp`
- `anchor_timestamp`
- `anomaly_count`
- `dataset_count`
- `peak_severity_score`

### `explanations`

Stores generated explanation outputs plus evidence metadata.

Key fields:

- `anomaly_id`
- `provider`
- `model`
- `generated_text`
- `evidence`

### `news_context`

Stores article citations retrieved around an anomaly window.

Key fields:

- `anomaly_id`
- `provider`
- `article_url`
- `title`
- `published_at`
- `search_query`
- `relevance_rank`

## Detection Strategy

The MVP anomaly detector uses rolling z-score logic.

The system now also includes a second detector:

- `change_point`

### Why this was chosen

- simple to implement
- transparent to explain
- good enough for clear spikes and crashes

### Why it is still imperfect

- trending series can distort baselines
- seasonal series can produce false positives
- low-frequency macro series need different thresholds than daily market series

The current implementation partly addresses this by using frequency-aware defaults and collapsing adjacent flagged points into one event.

### Change-point detector

The new change-point path uses `ruptures` to detect structural shifts rather than only local outliers.

This matters because MacroLens should eventually reason over:

- sharp spikes
- regime breaks
- sustained level transitions

The first implementation uses frequency-aware defaults and stores `change_point` as a separate `detection_method` rather than replacing `z_score`.

## Propagation Strategy

The MVP now includes a first propagation layer.

It does not attempt causal inference.

Instead it:

1. starts from a persisted anomaly cluster
2. looks at downstream lagged correlations from anomalies inside that cluster
3. matches those lagged relationships to later anomalies in the related datasets
4. groups those later anomalies by their target clusters
5. surfaces the result as a suggested propagation timeline

This is intentionally conservative.

The system is saying:

- these later clustered events are plausibly connected by stored lagged evidence

It is not saying:

- this cluster caused that cluster

## Correlation Strategy

The correlation engine does not compare raw levels blindly.

Instead it:

1. selects an event window around the anomaly
2. transforms series into percent changes
3. searches positive and negative lags
4. filters out weak or low-overlap relationships
5. persists only the strongest relationships

This is stronger than same-day raw-value correlation, but it is still correlation, not causation.

## Explanation Strategy

The explanation layer is intentionally separated from the detection and correlation layers.

That separation exists for one reason:

the explainer should interpret evidence, not invent it.

### Current implementation

- provider abstraction is implemented
- default provider is rules-based
- explanation text references anomaly severity, direction, and strongest correlations
- explanation output explicitly warns that correlation is not proof

### Planned upgrade

- continue comparative validation of OpenAI and Gemini provider paths
- improve prompt templating over structured evidence
- improve event context retrieval quality
- support higher-quality regeneration when evidence changes

## Frontend Experience

The frontend is designed around one investigation loop:

chart first, evidence second, explanation third

### Current UI capabilities

- dataset selector
- date-window filter
- severity filter
- direction filter
- timeseries chart
- chart brush for local zooming
- anomaly markers
- anomaly list
- detail panel with macro-event clusters, correlations, cited news context, explanations, and evidence provenance
- propagation timeline section with follow-on cluster navigation
- explanation regeneration trigger inside the event panel

### Missing but valuable next enhancements

- explicit raw evidence view
- cross-dataset comparison mode

## MVP Success Criteria

The MVP is successful if a user can:

1. load an implemented dataset
2. see detected anomalies on a chart
3. open an anomaly and inspect correlated datasets
4. read an explanation grounded in stored system evidence

## Current Assessment

The project is close to MVP-complete in system shape, but not yet complete against the original idealized PRD.

### Why it is strong already

- the vertical slice is real
- the evidence chain is persisted
- the UI is connected to live backend data
- the codebase is documented like an engineering project rather than a demo

### Why it is not finished yet

- the explainer now supports live hosted providers, but trust still depends on prompt discipline and evaluation
- the news layer now exists, but retrieval quality still needs improvement
- anomaly clustering now exists, but it is still a time-window grouping rule rather than a richer causal-event model
- propagation timelines now exist, but they are still derived from lagged evidence rather than causal proof
- some UX depth is still missing

## Hard Truths

- A chart alone is not impressive.
- Correlations without guardrails are dangerous.
- Headlines without provenance are just another form of noise.
- Explanations without grounded evidence are theater.
- A rules-based explanation layer is honest but not the final differentiator.

The next wave of value comes from making the evidence richer without making the system less trustworthy.
