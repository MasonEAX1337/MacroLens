# ADR 0005: Multi-Provider Explanation Support

## Decision

Support multiple live explanation providers behind the same explanation abstraction, starting with OpenAI and Gemini while retaining the rules-based fallback.

## Context

Once one live provider exists, the next temptation is to fork explanation logic per provider. That would make the architecture drift toward provider-specific behavior and weaken the evidence boundary.

MacroLens needs provider flexibility, but it also needs explanation generation to remain one system with one evidence contract.

## Alternatives Considered

- keep only a single hosted provider
- add Gemini as a separate code path outside the abstraction
- defer Gemini support until after more frontend work

## Reasoning

- provider competition is useful for cost and quality comparison
- the abstraction already existed, so adding Gemini through that boundary is the disciplined path
- keeping the same context-loading and persistence flow reduces architectural drift
- rules-based fallback remains important for reliability and deterministic testing

## Consequences

- the system can now compare hosted providers without changing the database or API model
- prompt quality and fallback behavior now matter even more because multiple providers can diverge in style and confidence
- the next evaluation task is no longer "can MacroLens call a model" but "which provider produces the most trustworthy explanations for this evidence shape"
