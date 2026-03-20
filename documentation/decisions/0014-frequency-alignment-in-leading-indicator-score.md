# Decision

Include frequency alignment as an explicit component in the leading-indicator ranking.

## Context

The leading-indicator score already included:

- cluster coverage
- average absolute correlation strength
- sign consistency

That improved honesty, but a real weakness remained:

- the score had no notion of how comparable the source and target frequencies were

This made some daily-to-monthly relationships look cleaner than they deserved, especially when their absolute correlations were large but their support was still relatively sparse.

## Alternatives Considered

- keep frequency out of the score and rely only on UI disclosure
- filter out all mixed-frequency pairs entirely
- include a small frequency-alignment term while still exposing the pair in the UI

## Reasoning

From first principles, frequency mismatch is not binary.

Examples:

- `monthly -> monthly` is strongly comparable
- `weekly -> monthly` is often still analytically useful
- `daily -> monthly` is more fragile because many daily observations can line up with a slower monthly event window by chance

So the right policy is:

- do not treat mixed-frequency pairs as invalid
- do not treat them as equal either

The chosen compromise was:

- keep coverage as the strongest term
- keep absolute strength and sign consistency as the main evidence terms
- add a smaller frequency-alignment term
- surface the actual frequency pair in the UI so the penalty is inspectable

## Consequences

Positive:

- daily-to-monthly leaders are discounted instead of silently overrated
- weekly-to-monthly leaders remain viable when they have real repeated support
- the ranking becomes more transparent about temporal comparability

Negative:

- the current alignment map is heuristic rather than learned
- low-cluster-count leaders can still look too clean if all other terms are strong
- some useful mixed-frequency relationships may rank slightly lower than before

Follow-on work:

- evaluate whether the frequency-alignment term should vary by dataset class, not only by frequency gap
- evaluate whether low target-cluster counts need an explicit confidence penalty
- decide whether the UI should highlight one-cluster leaders as structurally weak even when their score is high
