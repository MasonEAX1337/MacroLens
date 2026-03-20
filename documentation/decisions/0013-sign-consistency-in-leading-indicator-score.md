# Decision

Include sign consistency as an explicit component in the leading-indicator ranking.

## Context

The first leading-indicator implementation ranked datasets using:

- cluster coverage
- average absolute correlation strength

That was directionally useful, but it hid an important weakness:

- some repeated leading relationships flipped sign across different clustered episodes

That meant a dataset could rank highly even when its directional relationship with the target series was unstable.

## Alternatives Considered

- keep the original score and expose sign behavior only in a later debug view
- expose sign behavior in the UI but do not include it in the score
- include sign consistency directly in the score and surface it in the UI

## Reasoning

From first principles, a leading-indicator ranking is trying to capture repeated structure.

If a relationship repeats often but changes sign unpredictably, then:

- it may still be interesting
- but it is less stable as an indicator

So sign behavior should not be hidden.

At the same time, sign consistency should not dominate the score, because:

- some economically meaningful relationships are nonlinear or regime-dependent
- over-penalizing sign changes would discard potentially useful signals too aggressively

The chosen compromise was:

- keep cluster coverage as the strongest term
- keep average absolute strength as the second term
- add sign consistency as a smaller but explicit term

## Consequences

Positive:

- mixed-sign leaders are penalized instead of being overrated
- the UI becomes more scientifically legible
- users can judge whether a top-ranked leader is directionally stable

Negative:

- one-cluster leaders still get perfect sign consistency by construction
- regime-dependent leaders may rank lower even when they are still worth studying

Follow-on work:

- test whether single-cluster leaders need a stronger coverage penalty
- evaluate whether sign consistency should be weighted differently by dataset frequency
- add click-through paths from a ranked leader to its supporting clusters
