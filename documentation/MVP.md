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
- lag-aware correlation discovery around anomaly windows
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

- PostgreSQL schema with datasets, points, anomalies, correlations, explanations, and ingestion runs
- data ingestion for Bitcoin, CPI, Federal Funds Rate, and WTI oil
- rolling z-score anomaly detection with frequency-aware defaults
- lag-aware correlation scoring on percent changes
- explanation generation through a provider abstraction
- FastAPI endpoints for datasets, timeseries, anomalies, and anomaly detail
- React frontend that renders charts, anomaly markers, correlations, and explanations

### What is not fully implemented yet

- no live LLM provider is connected yet
- the current explanation provider is rules-based, not OpenAI/Anthropic/local model backed
- the S&P 500 dataset listed in the original plan is not implemented yet
- frontend zooming and richer filtering are not implemented yet
- explanation generation does not yet use external historical context or news evidence

This distinction matters. The repo now proves the system shape, but not every promised enhancement.

## Current Dataset Coverage

### Implemented

- Bitcoin price via CoinGecko
- CPI via FRED
- Federal Funds Rate via FRED
- WTI oil price via FRED

### Planned but not yet implemented

- S&P 500 index

## Core User Flow

1. The user opens the app.
2. The user selects a dataset.
3. The system renders the dataset history.
4. Detected anomalies appear as event markers.
5. The user selects an anomaly.
6. The system shows:
   - anomaly metadata
   - correlated datasets
   - generated explanation text
   - evidence-backed limitations of interpretation

## System Flow

```text
Source APIs
  -> normalization
  -> PostgreSQL
  -> anomaly detection
  -> correlation engine
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
4. explanations must be downstream of stored facts

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

### `explanations`

Stores generated explanation outputs plus evidence metadata.

Key fields:

- `anomaly_id`
- `provider`
- `model`
- `generated_text`
- `evidence`

## Detection Strategy

The MVP anomaly detector uses rolling z-score logic.

### Why this was chosen

- simple to implement
- transparent to explain
- good enough for clear spikes and crashes

### Why it is still imperfect

- trending series can distort baselines
- seasonal series can produce false positives
- low-frequency macro series need different thresholds than daily market series

The current implementation partly addresses this by using frequency-aware defaults and collapsing adjacent flagged points into one event.

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

- connect a live LLM provider
- add prompt templating over structured evidence
- add event context retrieval
- support regeneration when evidence changes

## Frontend Experience

The frontend is designed around one investigation loop:

chart first, evidence second, explanation third

### Current UI capabilities

- dataset selector
- timeseries chart
- anomaly markers
- anomaly list
- detail panel with correlations and explanations

### Missing but valuable next enhancements

- brush/zoom on chart
- date-range filtering
- severity filtering
- explanation regeneration trigger
- explanation evidence view

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

- the explainer is not yet backed by a live LLM
- the initial dataset set is still incomplete
- some UX depth is still missing

## Hard Truths

- A chart alone is not impressive.
- Correlations without guardrails are dangerous.
- Explanations without grounded evidence are theater.
- A rules-based explanation layer is honest but not the final differentiator.

The next wave of value comes from making the evidence richer without making the system less trustworthy.
