# ADR 0004: OpenAI as the First Live Explanation Provider

## Decision

Use OpenAI as the first live hosted explanation provider behind the existing explanation-provider abstraction.

## Context

MacroLens already had a rules-based provider and a provider abstraction. The next step was to add a real hosted model without collapsing the evidence boundary or making the explanation layer opaque.

The first live provider needed to satisfy a few practical constraints:

- easy HTTP integration
- strong general-purpose language performance
- ability to keep the prompt grounded in supplied evidence
- minimal architectural disruption

## Alternatives Considered

- Anthropic as the first live provider
- local model inference as the first live provider
- delaying live provider integration until after more frontend polish

## Reasoning

- OpenAI was a pragmatic first hosted provider for a narrow explanation task
- the Responses API fits the current architecture cleanly through `httpx`
- adding a live provider now exposes quality problems earlier, which is useful
- the fallback provider keeps the system usable when the hosted path fails

## Consequences

- the system now supports live hosted explanation generation without changing the persistence model
- explanation quality is still not guaranteed and must be validated on real anomalies
- the rules-based provider remains valuable as a fallback and as a deterministic baseline
