# Decision

Use a narrow relationship-aware gate for wider cross-dataset cluster merges.

## Context

MacroLens clustering had already moved from one global time window to frequency-aware pair windows.

That improved honesty, but the clusterer was still making merge decisions from temporal adjacency alone.

This created a persistent risk:

- nearby monthly or mixed-frequency anomalies could still collapse into broad episodes even when the system had no evidence that the datasets were meaningfully related

At the same time, the system had recently increased event supply for CPI and house prices through transformed monthly change points.

That meant the next clustering step had to improve episode quality without undoing the new anomaly supply.

## Alternatives Considered

### 1. Keep pure proximity clustering

Pros:

- simplest possible behavior
- no dependency on prior relationship evidence

Cons:

- continues to over-credit time adjacency as episode evidence
- too flattering for mixed-frequency episode formation

### 2. Add dataset-diversity weighting only

Pros:

- easy to implement
- can change downstream ranking and labels

Cons:

- does not improve the actual merge decision
- mostly cosmetic at the clustering layer

### 3. Rewrite clustering into a full relationship-aware algorithm

Pros:

- more principled long-term model

Cons:

- too large for the current need
- would change persistence, downstream assumptions, and event semantics at once

### 4. Add a narrow relationship-aware merge gate

Pros:

- local change
- preserves current architecture
- directly improves weak merge decisions

Cons:

- depends on already-stored correlation coverage
- can split good new episodes in cold-start cases

## Reasoning

The real issue was not cluster labels.
It was that wider cross-dataset merges were still happening from time proximity alone.

The smallest defensible improvement is:

- keep proximity as the first gate
- only for wider cross-dataset merges, require existing relationship evidence between the incoming dataset and at least one dataset already in the cluster

This preserves:

- same-dataset waves
- tight same-window cross-dataset episodes

while making broad mixed-frequency episodes harder to manufacture.

## Consequences

Positive:

- fewer weak cross-dataset episodes created purely by wide mixed-frequency time windows
- logic remains inspectable and easy to test
- current persistence and downstream APIs remain intact

Negative:

- the gate depends on historical correlation coverage
- good episodes without prior relationship evidence may be split
- clustering still remains adjacency-based overall, not a full causal or graph model
