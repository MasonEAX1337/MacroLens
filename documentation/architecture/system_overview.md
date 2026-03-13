# System Overview

## Purpose

MacroLens is an evidence pipeline plus investigation interface for unusual economic events.

It is not a forecasting engine and not a causal inference system.

Its job is narrower:

ingest data, detect unusual movements, find related datasets, and present an explanation workflow that a human can inspect quickly.

## Current Architecture

```text
CoinGecko / FRED
    -> provider clients
    -> normalization
    -> PostgreSQL
    -> anomaly detection
    -> correlation engine
    -> news context retrieval
    -> explanation generation
    -> FastAPI
    -> React frontend
```

## Runtime Flow

### 1. Ingestion

Provider-specific clients fetch source data.

That data is normalized before it reaches the database. This includes:

- timestamp normalization
- numeric conversion
- dataset metadata synchronization
- current full-refresh replacement for implemented sources

### 2. Storage

PostgreSQL is the canonical store.

All downstream steps operate against stored rows, not only in-memory fetch results. This is important because it makes the evidence chain inspectable and repeatable.

### 3. Anomaly Detection

Stored series are processed with rolling z-score logic using frequency-aware defaults.

Clustered flagged points are collapsed so that one event is represented as one anomaly when possible.

### 4. Correlation Discovery

For each anomaly, the system:

- builds an event window
- transforms values into percent changes
- searches positive and negative lags
- stores strongest relationships

### 5. News Context Retrieval

For each anomaly, the system can retrieve article citations around the event window and store them in PostgreSQL.

This is deliberately a separate evidence layer from correlations. News is contextual evidence, not another series to correlate numerically.

### 6. Explanation Generation

The explanation layer reads stored anomaly, correlation, and news-context evidence and generates persisted explanation text.

The current implementation uses a provider abstraction with rules-based, OpenAI, and Gemini-backed generation paths. That keeps the architecture stable while explanation quality continues to be tuned.

### 7. Delivery

FastAPI exposes the evidence model through event-centric endpoints.

React consumes those endpoints and renders:

- dataset selection
- timeseries chart
- anomaly markers
- event detail panel
- correlations
- stored news context
- explanations

## Implemented Boundaries

### In scope right now

- historical data ingestion
- persisted anomaly computation
- persisted correlation computation
- persisted explanation generation
- interactive investigation UI

### Explicitly out of scope right now

- real-time feeds
- causal modeling
- macroeconomic forecasting
- user-specific workflows

## Why This Architecture Works

The core strength of the architecture is that it is evidence-first.

Every visible UI element is downstream of persisted system state:

- the chart is backed by `data_points`
- the anomaly markers are backed by `anomalies`
- the related datasets are backed by `correlations`
- the cited articles are backed by `news_context`
- the explanation is backed by `explanations`

That makes the system easier to reason about, test, and improve.

## Real Risks Exposed During Implementation

### Timestamp normalization risk

The CoinGecko integration initially created duplicate same-day rows with different timestamps.

That bug proved a central architectural truth:

time normalization is not a peripheral concern in time-series systems. It is foundational.

### Correlation interpretation risk

Lag-aware correlation improves usefulness but does not remove the risk of spurious relationships.

The architecture must continue treating correlations as supporting evidence, not explanation certainty.

### Context retrieval risk

News retrieval increases explanatory power, but it introduces a new failure mode:

irrelevant headlines can look authoritative if ranking quality is weak.

That means provenance display and query quality now matter as much as transport.

## Current Maturity Assessment

MacroLens has crossed the line from scaffold to working system.

It has not yet crossed the line from working system to mature product.

The next phase is about improving the quality of interpretation, not merely adding more modules.
