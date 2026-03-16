# Decision

Build the first multi-event timeline on top of persisted clusters and label it as propagation rather than causality.

## Context

MacroLens already had:

- persisted anomalies
- persisted correlations
- persisted event clusters

That made the next obvious product step a multi-event timeline.

The real question was not whether to build one.
The real question was how to frame it honestly.

## Alternatives Considered

- call it a causal timeline
- derive timelines directly from single anomalies
- build the first timeline on top of persisted clusters and name it propagation

## Reasoning

Calling the feature causal would overstate what the system knows.

The current evidence model supports:

- lagged statistical relationships
- later anomaly matches
- event sequencing

It does not support:

- validated causal inference

Building the feature directly on isolated anomalies would also be too brittle.
That would make the system more likely to turn point noise into narrative.

The strongest current choice is:

- derive edges from clustered events
- limit the first pass to downstream links
- attach a conservative evidence-strength score
- name the feature `Propagation Timeline`

## Consequences

- anomaly detail now includes suggested downstream cluster edges
- users can click through from one event cluster to the next
- the feature improves the product materially without pretending to prove causation
- the next quality step is score decomposition, not graph complexity
