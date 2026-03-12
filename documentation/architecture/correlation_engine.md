# Correlation Engine

## Purpose

The correlation engine answers the next question after anomaly detection:

when this event happened, what else moved nearby in time?

It is the bridge between isolated anomaly detection and explanation generation.

## Current Implementation

The current engine computes lag-aware Pearson correlation on percent changes.

### Implemented process

1. load anomaly timestamp and source dataset
2. select a bounded event window around the anomaly
3. load candidate windows from all other datasets
4. convert values into percent changes
5. search across positive and negative lags
6. reject low-overlap results
7. keep strongest relationships above a minimum absolute threshold
8. persist top results to `correlations`

## Why Percent Change Was Chosen

Raw values are often misleading across differently scaled datasets.

Percent change is not perfect, but it is more defensible for first-pass comparison because it focuses on movement rather than absolute magnitude.

## Why Lag Search Was Necessary

Macro relationships are rarely synchronous.

Oil may move before inflation.
Rates may move after inflation.
Risk assets may react with delay.

Without lag search, the system would miss many relationships that a human would consider relevant.

## Current Guardrails

- self-correlation excluded
- frequency-aware correlation config
- minimum overlap required
- minimum absolute correlation threshold required
- only strongest results persisted

## Current Weaknesses

### 1. Mixed-frequency series are still imperfectly handled

The engine can operate across daily and monthly data, but the alignment is still coarse.

This is one of the biggest remaining analytical weaknesses in the MVP.

### 2. Correlation thresholding is heuristic

The current minimum thresholds are practical, not scientifically final.

They were chosen to keep the system from filling the UI with noise, not to claim statistical significance.

### 3. The engine still finds relationships, not causes

This cannot be emphasized enough.

The engine is evidence-producing, not proof-producing.

## Lessons From Implementation

The biggest pipeline insight was ordering:

correlations should be recomputed after a batch ingest, not immediately after each dataset load, because later datasets in the same batch must be available to earlier anomalies.

That adjustment was necessary to avoid incomplete evidence.

## Next Improvements

### Highest-value

- better mixed-frequency alignment strategy
- correlation confidence metadata
- dataset pairing exclusions when relationships are obviously meaningless

### Good second step

- rolling correlation visualization
- significance heuristics
- more explicit provenance in the API

## Design Standard

A good correlation engine should produce fewer, better relationships rather than many weak ones.

Noise is not helpful sophistication.
