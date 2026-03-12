# Anomaly Engine

## Purpose

The anomaly engine identifies unusual movements within a single dataset and persists them as events.

This matters because the rest of the product is event-centric. Without anomaly records, there is nothing coherent for the user to investigate.

## Current Implementation

The current engine uses rolling z-score detection.

### Implemented logic

1. load ordered series from PostgreSQL
2. choose configuration based on dataset frequency
3. compute rolling mean
4. compute rolling standard deviation
5. compute z-score
6. flag threshold breaches
7. collapse adjacent flagged points into a single strongest event
8. replace previously stored z-score anomalies for that dataset

## Frequency-Aware Defaults

The engine currently uses different defaults for:

- daily series
- weekly series
- monthly series

This is important because a single global threshold is a lazy assumption in economic data.

## Why Rolling Z-Score Was the Right First Choice

- transparent
- fast
- easy to test
- easy to persist with explanation metadata

It is not the most sophisticated option, but it is the most defensible first option.

## Metadata Stored Per Anomaly

The current implementation stores:

- z-score
- window size
- threshold
- rolling mean
- rolling standard deviation
- observed value

This is a strong design choice because it preserves the detector’s reasoning rather than only its verdict.

## What the Engine Does Well

- sharp spikes
- sharp crashes
- abrupt movements in daily datasets

## What the Engine Does Poorly

- trend-heavy series
- seasonal macro series
- slow regime changes
- anomalies that manifest as volatility clusters rather than single-point deviations

## Real Blind Spot

The engine currently replaces stored z-score anomalies on rerun.

This is correct for deterministic refresh behavior, but it also means anomaly identity is not yet historically stable across method changes.

That is acceptable for MVP, but not ideal for long-term provenance.

## Next Improvements

### Highest-value

- add dataset-specific configs
- add change-point detection experiment path
- store anomaly versioning if methods evolve

### Lower priority

- multi-method ensemble scoring
- seasonal decomposition before scoring
- volatility regime classifiers

## Standard Going Forward

The anomaly engine should remain explainable even as it becomes more advanced.

If a human cannot understand why a point was marked abnormal, the output becomes harder to trust, not easier.
