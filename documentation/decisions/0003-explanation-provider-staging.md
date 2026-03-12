# ADR 0003: Explanation Provider Staging

## Decision

Introduce a provider abstraction for explanations and ship a rules-based provider before integrating a live hosted LLM.

## Context

MacroLens needs explanation generation to complete the product loop, but integrating a live LLM too early would have mixed several concerns at once:

- system architecture
- provider reliability
- prompt design
- output quality
- cost and credential setup

That would have made it harder to know whether failures were architectural or provider-specific.

## Alternatives Considered

- integrate OpenAI immediately
- integrate Anthropic immediately
- postpone explanation generation entirely until live LLM integration is ready

## Reasoning

- a provider abstraction keeps generation concerns isolated from the rest of the pipeline
- a rules-based provider makes the end-to-end loop testable and persistent immediately
- explanation storage, retrieval, and UI rendering can be validated before introducing model behavior variability
- live LLM integration becomes an upgrade to a stable boundary rather than a redesign

## Consequences

- current explanation quality is limited and obviously transitional
- the architecture is stronger than if live LLM integration had been rushed
- the next phase can focus specifically on prompt quality and provider behavior instead of rebuilding storage and API boundaries
