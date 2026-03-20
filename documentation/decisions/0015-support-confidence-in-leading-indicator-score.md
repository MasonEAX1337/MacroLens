# Decision

Include absolute support confidence as an explicit component in the leading-indicator ranking.

## Context

The leading-indicator score already included:

- cluster coverage
- average absolute correlation strength
- sign consistency
- frequency alignment

That made the ranking more honest, but a real weakness remained:

- one-cluster leaders could still look overly complete when target-cluster count was small

This happened because cluster coverage is relative.

Example:

- a leader supported by `1 of 1` target clusters gets `100%` coverage
- that does not mean the relationship is mature
- it only means the target series currently has one clustered episode in view

## Alternatives Considered

- keep the score unchanged and rely only on UI wording
- hard-filter one-cluster leaders out of the ranking
- include an explicit absolute-support term while keeping one-cluster leaders visible

## Reasoning

From first principles, repeated structure requires absolute repetition.

Coverage answers:

- how much of the target event graph was covered

It does not answer:

- how many distinct episodes actually produced that support

So the score needs both:

- a relative term
- an absolute term

The chosen compromise was:

- keep sparse leaders visible
- add a conservative support-confidence term
- weight it strongly enough that one-cluster leaders no longer look fully mature
- still allow a sparse leader to remain interesting if every other evidence term is strong
- keep the first implementation stepwise rather than continuous

Why stepwise for now:

- the current anomaly graph is still too small and uneven to justify a smooth confidence curve
- a continuous function would look more precise than the evidence base really supports
- the product needs a stable, interpretable default more than another round of heuristic fitting

## Consequences

Positive:

- one-cluster leaders are no longer silently overrated
- repeated leaders separate more clearly from sparse leaders
- the UI becomes more honest about how much repeated evidence exists

Negative:

- the current support-confidence curve is heuristic rather than learned
- low-event datasets can still produce rankings where every candidate remains sparse
- sparse but genuinely important relationships may rank lower than before

Follow-on work:

- evaluate whether low target-cluster-count datasets need an additional dataset-level confidence note
- freeze the current stepwise curve until broader episode-quality work reveals a concrete failure case
- evaluate whether the UI should visually bucket leaders into sparse, emerging, and repeated regimes
