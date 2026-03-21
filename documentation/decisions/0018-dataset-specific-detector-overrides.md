# ADR 0018: Dataset-Specific Detector Overrides

## Status

Accepted

## Context

The anomaly engine originally used frequency-aware defaults only:

- daily
- weekly
- monthly

That was the right first abstraction, but live anomaly-density review showed a real weakness:

- CPI and house prices were barely producing anomalies
- daily market change-point detection was so conservative that it rarely contributed structural events

Because clustering, propagation, and leading-indicator logic all depend on anomaly supply, this was no longer just a detector issue. It was starving the whole episode graph.

## Decision

Add a narrow dataset-specific override layer on top of the frequency defaults.

Current override surface:

- z-score threshold per dataset
- change-point penalty per dataset

Current first-pass overrides:

- `CPIAUCSL`
- `CSUSHPISA`
- `MORTGAGE30US`
- `BTC`
- `DCOILWTICO`
- `SP500`

These overrides remain code-level configuration inside the anomaly engine rather than becoming a user-facing runtime settings surface.

## Why This Is The Right Choice

This change improves the right layer.

The observed problem was not:

- bad episode labels
- weak propagation scoring
- insufficient explanation wording

The observed problem was:

- uneven anomaly supply by dataset

Using narrow overrides is more defensible than loosening the monthly or daily defaults globally because it addresses the datasets that were clearly under-detected without raising noise everywhere else.

## Alternatives Considered

### 1. Loosen frequency defaults globally

Rejected.

That would have been the easiest change, but it would have turned a sparse-dataset problem into a whole-system noise problem.

### 2. Leave the detector untouched and only adjust clustering

Rejected.

Clustering cannot group events that were never detected in the first place.

### 3. Add a user-facing config layer now

Rejected for now.

That would expand surface area before the tuning model is mature enough to deserve it.

## Consequences

Positive:

- anomaly supply improved on weak monthly series
- the episode graph gained more raw material
- the change is localized and auditable

Negative:

- tuning is now partly dataset-specific, which increases maintenance burden
- these overrides are still first-pass heuristics, not final detector truths

## Follow-Up

- inspect whether the new anomalies improve real episode formation
- audit whether daily change-point penalties still under-detect structural breaks
- only expand the override layer when live evidence clearly justifies it
