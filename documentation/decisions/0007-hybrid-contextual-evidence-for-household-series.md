# Decision

Add a curated `macro_timeline` provider alongside GDELT for household macro anomalies.

## Context

MacroLens already had a persisted news-context layer backed by GDELT article retrieval.

That worked reasonably for fast-moving market series, but it broke down on slower household datasets such as:

- U.S. house prices
- 30-year mortgage rates
- real disposable personal income per capita

The problem was not storage or API shape.
The problem was provider fit.

Broad household topics often do not produce clean, anomaly-aligned headline retrieval, especially for older historical regimes.

## Alternatives Considered

- keep tuning GDELT queries only
- add another paid or keyed live news API immediately
- drop news context for household series entirely
- add a curated historical context provider inside the existing evidence boundary

## Reasoning

Further GDELT tuning had already hit diminishing returns.

Adding another live provider might help later, but it would increase integration cost before proving the real need.

Dropping context for household series would leave a visible product hole.

The best current tradeoff is a hybrid approach:

- use GDELT for live article retrieval
- use `macro_timeline` for curated household macro regimes where broad historical context is more appropriate than keyword search

This keeps the evidence model honest:

- live search remains live search
- curated context is explicit and inspectable
- explanations can cite both while still distinguishing direct structured evidence from broader background

## Consequences

- the news-context engine is now multi-provider rather than single-provider
- household anomalies can surface useful context even when GDELT returns nothing relevant
- hosted explanation prompts need guardrails so curated timeline entries do not overshadow stronger structured evidence
- the curated timeline will require ongoing maintenance and should stay intentionally sparse rather than pretending to be comprehensive
