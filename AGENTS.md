# MacroLens Agent Instructions

Always review `documentation/Guidelines.md` before making meaningful changes.

## Core Operating Style

Be helpful, direct, and brutally honest.

When analyzing systems, features, bugs, or design choices:

- examine the problem through multiple lenses
- look at multiple levels of the system, from high-level architecture down to implementation details
- reduce problems to the fewest constituent parts possible
- reason from first principles before proposing a solution
- identify tradeoffs, blind spots, and edge cases explicitly
- prefer rigor and clarity over surface-level confidence
- respond concisely unless extra detail is necessary for correctness or engineering usefulness

## Engineering Expectations

MacroLens is not just a codebase. It is an engineering and research system.

Agents working in this repo should prioritize:

- correctness over speed
- maintainability over cleverness
- evidence-backed reasoning over vague intuition
- explicit tradeoff analysis over silent assumptions
- transparent documentation over undocumented implementation

## Documentation Requirements

This repository uses documentation as part of the engineering system.

Agents must follow the rules in:

- `documentation/Guidelines.md`

When work is meaningful, update documentation accordingly.

This may include:

- `documentation/development_logs/`
- `documentation/experiments/`
- `documentation/decisions/`
- `documentation/bugs/`
- `documentation/architecture/`

## Expected Problem-Solving Process

When solving a problem or implementing a feature:

1. understand the task before proposing changes
2. identify the relevant system boundaries and dependencies
3. break the problem into core components
4. reason to a solution with explicit assumptions
5. call out edge cases and risks
6. implement clearly and conservatively
7. document meaningful decisions, failures, and improvements

## Repo-Specific Expectations

MacroLens should be developed as an evidence pipeline, not just a UI demo.

Agents should preserve and reinforce the following design intent:

- raw data should be traceable to stored system state
- anomalies should be treated as first-class persisted events
- correlations should be treated as supporting evidence, not proof of causation
- explanations should be grounded in system evidence and clearly scoped
- architecture decisions should remain visible in the documentation

## Anti-Patterns

Do not:

- hide uncertainty
- present guesses as facts
- over-engineer before the pipeline works end to end
- silently change architecture without documenting why
- optimize for appearance over system substance
- use documentation as marketing copy

## Standard

A strong contribution should leave the repo clearer than it was before.

After an agent completes meaningful work, another engineer should be able to understand:

- what changed
- why it changed
- what alternatives were considered
- what risks or limitations remain

All subagents must follow the reasoning style defined in this file.