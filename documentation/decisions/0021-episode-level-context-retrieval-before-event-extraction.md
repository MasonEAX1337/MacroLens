# Decision

Use **episode-level context retrieval** for clustered anomalies before building a richer event-extraction layer.

## Context

MacroLens had become stronger at explaining:

- what else moved

than at explaining:

- what likely happened in the real world

The main technical reason was simple:

- contextual retrieval was centered on an anomaly timestamp
- clustered monthly and weekly anomalies often belong to broader multi-day or multi-week episodes
- explanation generation therefore kept leaning on correlations because contextual evidence was too sparse or too poorly timed

## Alternatives Considered

### 1. Keep anomaly-centered retrieval and only tune keywords more

Rejected.

That would improve some coverage but would not fix the core mismatch for clustered slow-series episodes.

### 2. Build full event extraction first

Rejected for now.

That would be a larger and less inspectable step before fixing the more basic retrieval window problem.

### 3. Episode-level retrieval for non-trivial clusters, anomaly-level retrieval for isolated signals

Chosen.

This is the smallest change that improves real-world context without rewriting the provider model or inventing a new evidence layer prematurely.

## Reasoning

The first-principles issue was not that MacroLens had zero contextual evidence.
It was that the context lookup target was too narrow.

For slow macro series, a single anomaly timestamp is often the wrong retrieval anchor.
The correct intermediate object is the stored episode window.

So the chosen design is:

- isolated signals:
  - retrieve around the anomaly timestamp
- single-dataset waves and cross-dataset episodes:
  - retrieve around the episode span

This preserves current architecture while making the context layer more aligned with how the rest of the product already reasons about events.

## Consequences

### Positive

- clustered anomalies can retrieve better context without changing the schema
- explanations can lead with more plausible real-world context
- the UI can distinguish likely drivers from supporting market relationships more honestly

### Negative

- wider retrieval windows can increase noise if ranking remains weak
- the likely-driver layer is still title-first until event extraction improves
- episode-level retrieval can still underperform when cluster quality is weak

### Follow-up

The next step after this decision is not another broad retrieval rewrite.
It is:

- event/theme extraction
- better ranking for likely drivers
- live validation on real clustered monthly and weekly anomalies
