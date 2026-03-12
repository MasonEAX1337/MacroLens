# ADR 0001: Database Choice

## Decision

Use PostgreSQL as the primary database for the MVP.

## Context

MacroLens needs a reliable system of record for dataset metadata, time series values, anomalies, correlations, and generated explanations.

## Alternatives Considered

- SQLite
- MongoDB
- TimescaleDB as the default

## Reasoning

- PostgreSQL gives strong relational modeling for event and explanation joins
- it is easy to run locally and production-grade enough for growth
- TimescaleDB can be added later if time-series performance becomes a real bottleneck
- SQLite is too limiting for the intended shape of the project
- MongoDB weakens relational clarity for anomaly and correlation workflows

## Consequences

- the schema must be designed carefully around timestamp access patterns
- time-series optimization is deferred until justified by usage
