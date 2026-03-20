# Decision

Aggregate leading indicators at the target-cluster level instead of counting every target anomaly independently.

## Context

MacroLens already stored:

- anomalies
- anomaly clusters
- lag-aware correlations

That made a new dataset-level feature possible:

- repeated leading-indicator discovery

The central design question was what the aggregation unit should be.

## Alternatives Considered

- aggregate directly over every target anomaly
- aggregate over every correlation row
- aggregate over target clusters, keeping one strongest support per related dataset per cluster

## Reasoning

The first-principles problem is overcounting.

One macro episode can produce multiple anomalies in the same target dataset, especially after adding a second detector or when a dense period creates both point and structural events.

If every anomaly counted independently, the leading-indicator score would inflate repeated support inside one episode and confuse it with repeated support across episodes.

So the current design uses:

- target cluster as the episode unit
- one strongest leading support per related dataset inside that cluster

That makes the output closer to:

- repeated pattern across episodes

instead of:

- repeated rows inside one episode

## Consequences

Positive:

- ranking is less noisy
- dense clusters do not dominate the score unfairly
- the feature aligns with the broader event-centric product model
- each ranked leader can now expose the concrete supporting episodes behind the summary
- those supporting episodes can now carry enough cluster context to be inspected before navigation

Negative:

- the score can undercount if clustering is too coarse
- cluster quality now directly affects leading-indicator quality
- the feature still inherits all mixed-frequency correlation limitations

Follow-on work:

- evaluate whether sign consistency should become part of the score
- allow click-through into the supporting clusters from the UI
- compare top-ranked leaders against hand-checked macro episodes
