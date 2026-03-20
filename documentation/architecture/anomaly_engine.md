# Anomaly Engine

## Purpose

The anomaly engine identifies unusual movements within a single dataset and persists them as events.

This matters because the rest of the product is event-centric. Without anomaly records, there is nothing coherent for the user to investigate.

The engine now has two downstream responsibilities:

- persist anomalies as first-class evidence
- provide the event substrate for clustering, propagation, correlations, news context, and explanations

## Current Implementation

The engine now uses two detection methods:

- `z_score`
- `change_point`

### Implemented logic

1. load ordered series from PostgreSQL
2. choose configuration based on dataset frequency
3. run rolling z-score detection for point anomalies
4. run `ruptures`-based binary segmentation for structural shifts
5. collapse adjacent flagged points into single representative events
6. replace previously stored anomalies for each detection-method partition

## Frequency-Aware Defaults

The engine currently uses different defaults for:

- daily series
- weekly series
- monthly series

This is important because a single global threshold is a lazy assumption in economic data.

For change-point detection, the current defaults are intentionally pragmatic:

- `binseg` algorithm
- `l2` cost model
- frequency-aware penalties
- frequency-aware minimum segment sizes
- frequency-aware smoothing windows
- frequency-aware severity thresholds

The design goal is not theoretical elegance. The design goal is a second detector that is:

- fast enough to backfill the live corpus
- explainable enough to inspect
- conservative enough to avoid fake regime shifts everywhere

## Why Rolling Z-Score Was the Right First Choice

- transparent
- fast
- easy to test
- easy to persist with explanation metadata

It is not the most sophisticated option, but it is the most defensible first option.

## Metadata Stored Per Anomaly

For `z_score`, the current implementation stores:

- z-score
- window size
- threshold
- rolling mean
- rolling standard deviation
- observed value

For `change_point`, the current implementation also stores:

- algorithm
- event type
- penalty
- min segment size
- jump
- smoothing window
- before mean
- after mean
- delta mean
- overall series standard deviation
- observed value

This is a strong design choice because it preserves the detector's reasoning rather than only its verdict.

## What the Engine Does Well

- sharp spikes
- sharp crashes
- abrupt movements in daily datasets
- first-pass structural level shifts

## What the Engine Does Poorly

- trend-heavy series
- seasonal macro series
- slow regime changes without clean level shifts
- anomalies that manifest as volatility clusters rather than single-point deviations

## Real Blind Spot

The engine currently replaces stored anomalies per detection method on rerun.

This is correct for deterministic refresh behavior, but it also means anomaly identity is not yet historically stable across method changes or config tuning.

That is acceptable for MVP, but not ideal for long-term provenance.

## Operational Notes

The first live change-point backfill revealed an important constraint:

- a theoretically heavier detector is useless if it cannot finish on the real corpus

That is why the current implementation uses a faster binary-segmentation configuration instead of a more expensive default.

The right standard here is:

- good enough to surface plausible regime shifts
- cheap enough to rerun coherently with the rest of the evidence graph

## Next Improvements

### Highest-value

- add dataset-specific configs where generic frequency defaults are too blunt
- compare `z_score` and `change_point` output against downstream usefulness, not just anomaly count
- add richer event typing beyond the current first-pass `level_shift` and `volatility_shift`
- connect anomaly clusters more deeply into event-chain and leading-indicator views

### Lower priority

- multi-method ensemble scoring
- seasonal decomposition before scoring
- volatility regime classifiers

## Standard Going Forward

The anomaly engine should remain explainable even as it becomes more advanced.

If a human cannot understand why a point was marked abnormal, the output becomes harder to trust, not easier.
