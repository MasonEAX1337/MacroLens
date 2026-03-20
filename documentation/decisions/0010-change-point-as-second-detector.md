# Decision

Add `change_point` detection alongside `z_score` rather than replacing the existing detector.

## Context

MacroLens originally used only rolling z-score detection.

That was strong for:

- sharp spikes
- crashes
- local outliers

But it was weaker for:

- sustained level changes
- regime transitions
- structural shifts in slower macro series

The system needed a second detector, not a renamed version of the first one.

## Alternatives Considered

- keep only z-score detection
- replace z-score completely with change-point detection
- add change-point detection as a second stored method

## Reasoning

Keeping only z-score would leave the event model too narrow.

Replacing z-score outright would remove a simple and defensible detector that still works well for point anomalies.

The strongest current choice is to store both:

- `z_score` for point anomalies
- `change_point` for structural shifts

This preserves the existing system while widening the event model.

## Consequences

- anomaly storage now contains multiple method partitions for the same dataset
- clustering, propagation, and later investigation logic can operate over both point anomalies and regime anomalies
- live backfill must be coordinated carefully because re-detecting anomalies changes IDs and invalidates downstream evidence unless correlations, clusters, news context, and explanations are refreshed consistently
