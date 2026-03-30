# Decision

Use `hybrid` news-context retrieval by default and allow curated macro-timeline entries to match against the full episode dataset set, not only the anomaly's primary dataset.

## Context

Episode-level retrieval improved context structure but did not solve context coverage.

Live validation showed:

- March 2022 and October 2008 anomalies still often had no real-world context
- many older anomalies were outside the configured GDELT age window
- the existing curated timeline path was too narrow because it mainly covered household series and matched only on the anomaly's primary dataset

That left the system with a recurring failure mode:

- explanations fell back to correlations because contextual evidence was absent even for well-known macro episodes

## Alternatives Considered

### Keep `gdelt` as the default and expand query templates only

Rejected.

This would still leave older anomalies without context because the age guard would continue blocking GDELT for much of the history.

### Remove the GDELT age guard and rely on live retrieval for all history

Rejected.

This would increase refresh cost, worsen rate-limit exposure, and still would not solve weak historical query quality.

### Add a second live provider immediately

Rejected for now.

This would expand complexity before the current evidence model had exhausted the simpler option of curated fallback plus better matching.

## Reasoning

The smallest defensible fix was:

1. keep recent live retrieval
2. widen curated fallback coverage
3. let curated historical context match on the episode, not only the anomaly symbol

That follows the structure of the evidence graph better.

A broad geopolitical or crisis event can be relevant to:

- oil
- rates
- housing
- equities

at the same time.

Matching timeline entries only to the anomaly's primary dataset was too narrow for that reality.

Switching the default provider mode to `hybrid` also keeps the behavior honest:

- recent anomalies can still benefit from live reporting
- older or structurally weak retrieval cases can still surface curated historical context

## Consequences

Positive:

- better historical coverage without a new provider
- better coverage for cross-dataset episodes
- more explanations can lead with real-world context instead of only correlation structure

Negative:

- curated coverage is still sparse and selective
- provider ordering can over-favor broad historical backdrop if the curated set grows carelessly
- some anomalies remain empty because no curated entry exists yet

Follow-up work:

- add semantic reranking over context candidates
- expand curated historical entries where live validation still shows empty context
- keep documenting where curated context helps and where it remains missing
