# Database Design

## Purpose

The database is the product memory of MacroLens.

If a chart point, anomaly marker, correlation row, or explanation cannot be traced back to stored records, the system is not trustworthy.

## Design Standard

The schema is built around one product question:

given a selected anomaly, can the system retrieve the event, its source dataset, related datasets, and generated explanations efficiently and deterministically.

## Implemented Tables

### `datasets`

Stores dataset metadata and frequency.

Current role:

- identity for each supported series
- source ownership
- frequency-driven logic for downstream analysis

Important fields:

- `name`
- `symbol`
- `source`
- `description`
- `frequency`

### `data_points`

Stores normalized observations.

Important fields:

- `dataset_id`
- `timestamp`
- `value`

Key constraint:

- unique `(dataset_id, timestamp)`

This prevents duplicate timestamps from silently polluting analysis after normalization is correct.

### `anomalies`

Stores detected events.

Important fields:

- `dataset_id`
- `timestamp`
- `severity_score`
- `direction`
- `detection_method`
- `metadata`

Why `metadata` matters:

the detector should not only say that an anomaly exists; it should preserve enough context to explain how that judgment was made.

### `correlations`

Stores strongest related datasets for an anomaly.

Important fields:

- `anomaly_id`
- `related_dataset_id`
- `correlation_score`
- `lag_days`
- `method`

Why this table matters:

it converts relationship analysis from a volatile on-demand calculation into persisted evidence that the API and UI can consume consistently.

### `explanations`

Stores generated outputs plus evidence metadata.

Important fields:

- `anomaly_id`
- `provider`
- `model`
- `generated_text`
- `evidence`

This table matters because explanation output is not just content. It is a versioned interpretation of stored evidence.

### `ingestion_runs`

Stores execution trace for imports.

Important fields:

- `source`
- `dataset_key`
- `status`
- `message`
- `started_at`
- `finished_at`

This is operationally important because data systems fail quietly if they are not instrumented at the ingestion layer.

## Implemented Indexing

- `data_points(dataset_id, timestamp DESC)`
- `anomalies(dataset_id, timestamp DESC)`
- `correlations(anomaly_id)`
- `explanations(anomaly_id, created_at DESC)`

These indexes map directly to API access patterns.

## Data Integrity Lessons

### 1. Unique constraints are necessary but not sufficient

The CoinGecko timestamp bug showed that uniqueness cannot protect against bad normalization if two bad timestamps are still technically unique.

The deeper protection comes from:

- normalization before insert
- correct source-specific handling
- thoughtful refresh behavior

### 2. Full refresh is currently the right ingestion strategy

For the implemented sources, replacing a dataset’s rows during refresh is safer than leaving stale data behind.

Why:

- the dataset sizes are still manageable
- source payloads are effectively snapshots
- stale rows create downstream analytical errors

### 3. Frequency belongs in the data model

The anomaly and correlation engines need to reason differently about daily and monthly series.

That is why `frequency` belongs on `datasets`, not only in code assumptions.

## Current Gaps

- no separate source raw-record table exists yet
- no revision history exists for time-series changes
- no explicit job table exists for anomaly/correlation/explanation pipeline stages

These are not MVP blockers, but they are natural next steps if the system becomes operationally heavier.

## Design Constraint Going Forward

Every new feature should preserve one property:

the user-visible explanation must remain traceable to stored evidence rows.
