# Decision

Treat GDELT as a recent-context provider rather than a universal historical news layer.

## Context

MacroLens now has enough anomalies that a full evidence refresh is a real operational workflow, not just a development convenience.

The first coordinated refresh after change-point backfill exposed a problem:

- live GDELT retrieval across the full historical anomaly set was slow
- decades-old anomalies produced weak or empty live coverage
- transport failures could abort a long refresh

At the same time, the product already had a second contextual-evidence path:

- curated `macro_timeline` entries for selected household historical regimes

## Alternatives Considered

- continue querying GDELT for every anomaly in the database
- remove live news retrieval from coordinated refreshes entirely
- add a second live news provider immediately
- restrict live retrieval to recent anomalies and use curated historical fallback where available

## Reasoning

The core problem was not lack of a news provider in the abstract. The problem was using one provider for jobs it does poorly.

From first principles:

- live article search is best for recent event-level context
- curated historical context is better for older regime narratives
- a refresh workflow must be bounded and resumable or it is not trustworthy operationally

So the right intermediate decision was:

- keep GDELT for recent anomalies
- stop treating it as the answer for decades-old anomalies
- preserve curated macro-timeline evidence for selected historical household cases
- degrade older uncovered anomalies honestly into limited coverage

## Consequences

Positive:

- coordinated refreshes are more practical to run
- live retrieval is focused on anomalies where it is most likely to add value
- transport failures in one request no longer invalidate the whole refresh
- the system is more honest about historical coverage limits

Negative:

- some older anomalies will now deliberately have no live article retrieval attempt
- historical contextual coverage remains sparse until the curated timeline is expanded or another provider is added

Follow-on work:

- expand curated historical timeline coverage
- consider a second provider for historical or domain-specific retrieval
- make recent-only live retrieval semantics explicit in the UI and docs
