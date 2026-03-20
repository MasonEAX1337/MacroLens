# Leading Indicator Discovery

## Purpose

The leading-indicator layer answers a dataset-level question:

which other series repeatedly move before this one across multiple event episodes?

This is different from a single-anomaly correlation view.

The goal is not to find the nicest-looking lag on one chart. The goal is to aggregate repeated leading relationships into a more stable research signal.

## Current Implementation

The current implementation is built on top of persisted anomalies, persisted correlations, and persisted anomaly clusters.

For a selected target dataset, the engine:

1. loads all anomalies for that dataset
2. maps each anomaly to its cluster, or uses the anomaly itself as a fallback event unit if clustering is missing
3. keeps only correlations where `lag_days < 0`
4. collapses duplicate relationships inside the same target cluster so one noisy episode does not count multiple times
5. aggregates surviving support by related dataset
6. measures directional stability across those repeated supports
7. ranks the results by a conservative consistency score

## Why Cluster-Level Aggregation Matters

Without clustering, a dense event window can produce multiple target anomalies that all reflect the same macro episode.

If each one counted independently, the system would overstate repetition.

So the current design deliberately counts:

- one strongest leading relationship per related dataset per target cluster

That gives the system a better event unit:

- repeated support across episodes
- not repeated support inside one episode

## Current Metrics

Each leading-indicator row exposes:

- `supporting_cluster_count`
- `target_cluster_count`
- `cluster_coverage`
- `related_dataset_frequency`
- `target_dataset_frequency`
- `average_lead_days`
- `average_correlation_score`
- `average_abs_correlation_score`
- `strongest_correlation_score`
- `sign_consistency`
- `dominant_direction`
- `frequency_alignment`
- `support_confidence`
- `consistency_score`
- `supporting_episodes`

The ranking is currently driven by:

- cluster coverage
- average absolute correlation strength
- sign consistency
- frequency alignment
- support confidence

This is intentionally simple. It is meant to be inspectable before it is made more sophisticated.

## What This Layer Does Well

- surfaces repeated leading relationships instead of one-off lag matches
- reduces overcounting from dense anomaly clusters
- gives the UI a dataset-level research view rather than only event-level inspection

## What This Layer Does Poorly

- mixed-frequency series can still produce plausible-looking but analytically weak leads
- high sign consistency still does not prove economic meaning
- a high-ranked leader is still not proof of causal importance

## Current Guardrails

- the panel is framed as leading signals, not causal drivers
- only leading relationships are included
- duplicate supports inside one target cluster are collapsed
- sign consistency is surfaced directly instead of being hidden inside the score
- frequency alignment is surfaced directly instead of being buried in the ranking
- absolute support confidence is surfaced directly so one-cluster leaders do not masquerade as repeated leaders
- the score remains transparent rather than buried in one unexplained label
- each ranked row now exposes click-through supporting episodes so the ranking can be audited against stored anomalies
- each supporting episode now includes compact cluster context:
  - cluster window
  - cluster size
  - target event method
  - target severity
  - strongest deduped matched lag and correlation
- each support row now also includes inline cluster-member previews so the user can inspect the episode composition before navigation
- the support browser now allows up to three supporting episodes to be compared side by side before navigation

## Next Improvements

- compare results against hand-checked macro episodes
- evaluate whether the current frequency-alignment heuristic is sufficient or whether some dataset pairs need stronger dataset-class penalties
- treat the current stepwise support-confidence curve as frozen until broader episode-quality work exposes a clear failure mode
- decide whether side-by-side support comparison needs sparklines or should remain metadata-first
