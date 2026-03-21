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

## Dataset-Specific Overrides

Frequency defaults were the right first abstraction, but live anomaly-density review showed they were too blunt for some series.

The engine now supports dataset-symbol overrides on top of the frequency baseline.

Current first-pass overrides:

- `CPIAUCSL`
  - lower z-score threshold from `2.5` to `2.2`
  - lower change-point penalty from `3.0` to `2.2`
  - run change-point detection on percent change rather than raw level
- `CSUSHPISA`
  - lower z-score threshold from `2.5` to `2.15`
  - lower change-point penalty from `3.0` to `1.8`
  - run change-point detection on percent change rather than raw level
- `MORTGAGE30US`
  - lower weekly change-point penalty from `2.5` to `2.0`
- `BTC`
  - lower daily change-point penalty from `5.0` to `4.0`
- `DCOILWTICO`
  - lower daily change-point penalty from `5.0` to `3.0`
- `SP500`
  - lower daily change-point penalty from `5.0` to `3.5`

The logic is deliberately narrow.

This is not a free-for-all tuning layer. It is a targeted response to a real problem:

- CPI and house prices were under-supplying events badly enough to starve the episode graph
- daily change-point detection on market series was so conservative that it added almost no structural evidence

The override standard is:

- increase real event supply where the baseline is clearly too strict
- avoid global loosening that would add noise everywhere else

One important boundary remains:

- z-score still runs on the raw stored series
- only the change-point detector can apply a dataset-specific transform layer

That keeps the architecture narrow and inspectable.

One important correction followed from live evaluation:

- local detector-time monthly floors were rejected as the active solution
- they improved local anomaly cleanliness but degraded global episode quality

The current design keeps the transformed monthly change-point path intact, then evaluates weak monthly events at the episode-filter stage during clustering.

That keeps:

- raw anomaly supply
- timestamps
- transformed detector metadata

while letting the episode layer decide whether a weak monthly anomaly should stay in the final cluster graph.

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
- transform
- before mean
- after mean
- delta mean
- overall series standard deviation
- observed value
- transformed value

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

The first dataset-specific detector pass also revealed a second constraint:

- anomaly supply matters more than detector purity if the rest of the system depends on clustered episodes

After the override pass, live anomaly totals shifted in the right direction for sparse monthly series:

- `CPIAUCSL`: `4 -> 11`
- `CSUSHPISA`: `1 -> 6`
- `MORTGAGE30US`: `12 -> 13`

That is not proof that the tuning is complete. It is evidence that the previous generic settings were too strict for at least some slow datasets.

## Next Improvements

### Highest-value

- compare `z_score` and `change_point` output against downstream usefulness, not just anomaly count
- audit per-dataset overrides against real cluster formation, not just raw anomaly count
- decide whether CPI and house prices still need alternate event definitions beyond lower thresholds and penalties
- add richer event typing beyond the current first-pass `level_shift` and `volatility_shift`
- connect anomaly clusters more deeply into event-chain and leading-indicator views

### Lower priority

- multi-method ensemble scoring
- seasonal decomposition before scoring
- volatility regime classifiers

## Standard Going Forward

The anomaly engine should remain explainable even as it becomes more advanced.

If a human cannot understand why a point was marked abnormal, the output becomes harder to trust, not easier.
