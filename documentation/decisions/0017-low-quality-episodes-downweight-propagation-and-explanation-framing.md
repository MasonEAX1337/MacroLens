# Decision

Use persisted episode quality to conservatively down-weight propagation strength and explanation framing.

## Context

MacroLens now persists `quality_band` on each anomaly cluster.

Without using that field anywhere meaningful, the system would still have a core honesty problem:

- a weak isolated episode could still produce a propagation edge that looked too mature
- explanations could still speak as if every anomaly lived inside a broad macro episode

That would make episode metadata decorative instead of operational.

## Alternatives Considered

### Do not use episode quality downstream yet

Rejected.

That would leave propagation and explanation framing blind to the new event-quality information.

### Use episode quality as a hard filter

Rejected for now.

That would hide useful but weak evidence instead of surfacing it honestly.

### Apply a strong numerical penalty

Rejected.

The live event graph is still uneven enough that harsh penalties would likely overcorrect.

## Reasoning

The irreducible goal is honesty, not cleverness.

So the current downstream use is intentionally narrow:

- propagation score includes an `episode_quality` component
- that component uses the weaker of the source and target episode quality
- explanation framing becomes more cautious when `cluster_quality_band` is `low`

Current propagation weights are:

- `high` -> `1.00`
- `medium` -> `0.90`
- `low` -> `0.80`

These are not trying to be statistically calibrated.
They are trying to stop weak episodes from looking too strong.

## Consequences

Positive:

- propagation edges are less flattering when either side of the path sits on weak episode footing
- explanations are more explicit when the episode context is narrow
- episode quality now affects product behavior, not just inspection labels

Negative:

- the penalty is still heuristic
- the live database must have the upgraded `anomaly_clusters` schema applied before these fields work outside tests
- the current rule does not yet prevent edge formation; it only makes weak paths look weaker

Follow-up:

- inspect real low-quality episodes after the schema is re-applied and evidence is recomputed
- decide whether low-quality episodes should also reduce leading-indicator maturity or only investigation framing
