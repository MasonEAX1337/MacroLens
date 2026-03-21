# Decision

Move weak monthly anomaly filtering from the detector into a bridge-preserving episode-filter stage inside clustering.

## Context

MacroLens tested narrow detector-time transformed monthly filters for `CPIAUCSL` and `CSUSHPISA`.

That improved anomaly-level cleanliness, but it degraded the live episode graph:

- cross-dataset episodes fell
- isolated signals rose
- real episode structure was split

The repo therefore established an important system-level result:

- local anomaly quality does not equal global episode quality

Weak monthly anomalies were sometimes acting as bridge nodes in cross-dataset episodes.

## Alternatives Considered

### 1. Keep detector-time monthly floors

Pros:

- simple
- local
- easy to reason about

Cons:

- already failed on the live graph
- removes weak bridge anomalies before the episode layer can evaluate them

### 2. Tune detector-time thresholds again

Pros:

- still simple

Cons:

- repeats the same local-only assumption
- likely to keep trading isolated noise against episode fragmentation

### 3. Add a bridge-preserving episode filter after provisional clustering

Pros:

- preserves full anomaly supply long enough for episode structure to form
- suppresses only weak monthly anomalies that remain isolated or single-dataset
- keeps anomalies queryable and transparent

Cons:

- slightly more complex than a detector-time floor
- requires clustering to annotate anomaly metadata

## Reasoning

The failure mode was not timestamp misalignment.
It was graph fragmentation.

That means the suppression decision belongs at the episode layer, not the detector layer.

The narrowest defensible solution is:

- keep transformed monthly change-point detection
- build provisional clusters on the full anomaly set
- suppress only weak target monthly anomalies that are still isolated or single-dataset
- preserve weak anomalies when they participate in provisional cross-dataset episodes

This keeps the architecture conservative while respecting the graph-like behavior of the event system.

## Consequences

Positive:

- weak connector anomalies can survive when they matter
- suppressed anomalies remain visible and queryable
- the episode graph can improve without deleting evidence

Negative:

- clustering now has a small episode-filter responsibility
- the rule is still targeted to two datasets, not yet generalized
- future work may still need richer bridge logic if current suppression remains too blunt
