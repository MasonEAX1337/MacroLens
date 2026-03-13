# Decision

Store retrieved article context in a dedicated `news_context` table instead of trying to encode it inside correlations or explanations.

## Context

MacroLens originally relied on one evidence class: structured time-series relationships.

That was enough to detect anomalies and compare datasets, but not enough to support real-world event interpretation.

Adding a news layer was necessary, but the system needed to keep a clean distinction between:

- statistical evidence
- contextual evidence

## Alternatives Considered

- store article titles inside `explanations.evidence`
- store article references inside `correlations.metadata`
- fetch news on demand in the API without persistence

## Reasoning

A dedicated table was the correct choice because:

- article citations are first-class evidence, not explanation implementation detail
- news retrieval provenance should remain inspectable independently of the explainer
- on-demand fetching would weaken reproducibility and make the UI depend on live external calls
- mixing articles into correlation storage would blur the boundary between numeric relationships and contextual retrieval

## Consequences

- the schema grows by one more evidence table
- ingestion and regeneration workflows gain an additional step
- the UI can now display citations directly
- retrieval quality becomes a visible product concern instead of being hidden inside the explainer
