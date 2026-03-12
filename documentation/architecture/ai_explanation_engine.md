# AI Explanation Engine

## Purpose

The explanation engine translates stored event evidence into a short narrative a user can interpret quickly.

It is the final interpreter in the system, not the source of truth.

## Current Implementation

The current implementation uses:

- a provider abstraction
- a rules-based provider
- persisted evidence payloads
- explanation storage in PostgreSQL

This is a deliberate interim design.

It makes the pipeline complete while keeping the boundary ready for a live LLM provider.

## Current Evidence Inputs

Each explanation is currently grounded in:

- dataset name
- anomaly date
- severity score
- move direction
- detection method
- stored correlations

## Why This Design Was Chosen

If a live LLM provider had been added first, three problems would have appeared immediately:

- harder testing
- weaker separation between evidence and generation
- less clarity about what the explanation engine is actually allowed to use

The provider abstraction solved that early.

## What the Current Rules-Based Provider Does Well

- produces deterministic output
- references stored evidence directly
- explicitly states uncertainty
- preserves the architecture for later LLM integration

## What It Does Poorly

- language is repetitive
- it lacks broader historical context
- it does not synthesize external knowledge
- it does not feel meaningfully intelligent yet

That is the honest limitation.

## Why This Is Still Valuable

The current provider proves the hardest architectural part:

the system can load context, generate an explanation, persist it, and surface it in the UI.

That is a real product step, even if the generation quality is still transitional.

## Next Upgrade Path

### Near-term goal

Implement a live LLM provider behind the existing abstraction.

### Required pieces

- structured prompt builder
- provider-specific client
- strong uncertainty instructions
- response persistence
- fallback to rules-based provider when unavailable

### Important principle

The LLM should be allowed to interpret evidence, not fabricate new evidence.

That means prompt design should continue to anchor on stored records first.

## Design Standard

An explanation is good if it is:

- concise
- evidence-based
- explicit about uncertainty
- easy to inspect against the underlying data

An explanation is bad if it sounds impressive while outrunning the evidence.
