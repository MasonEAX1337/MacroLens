# Documentation Guidelines

## Purpose

This repository uses documentation as part of the engineering system, not as an afterthought.

The goal is to make the repo answer four questions clearly:

1. what are we building
2. how does it work
3. what was tried
4. why were decisions made

## Relationship to AGENTS.md

`AGENTS.md` defines how coding agents should reason and operate in this repository.

This file defines how project documentation should be structured, updated, and maintained.

Agents should use both:
- `AGENTS.md` for operating behavior
- `documentation/Guidelines.md` for documentation standards

## Documentation Layers

### Product documentation

Files in the root of `documentation/` define product scope and delivery intent.

Examples:

- `MVP.md`
- `DevelopmentPlan.md`

### Architecture documentation

Files in `documentation/architecture/` explain system structure, boundaries, and internal logic.

### Development logs

Files in `documentation/development_logs/` capture daily engineering progress.

### Experiment, decision, and bug records

These show technical reasoning:

- `documentation/experiments/`
- `documentation/decisions/`
- `documentation/bugs/`

### Research notes

Files in `documentation/research/` analyze real-world events using the system.

## Writing Rules

- prefer concrete language over vague summaries
- state assumptions explicitly
- separate facts from interpretation
- record failures, not just successes
- document tradeoffs, not just choices

## Required Sections

### Development log format

- Goal
- Work Completed
- Problems Encountered
- Solution
- Next Steps

### Experiment record format

- Experiment
- Goal
- Methods Tested
- Dataset
- Results
- Conclusion

### Decision record format

- Decision
- Context
- Alternatives Considered
- Reasoning
- Consequences

### Bug record format

- Bug
- Cause
- Fix
- Result

## Maintenance Rules

- update development logs on each meaningful work session
- add a decision record when a core technical choice is made
- add an experiment record when testing multiple approaches
- add a bug record when debugging reveals a real system weakness
- update architecture docs when the design materially changes

## Anti-Patterns

- do not use docs as marketing copy
- do not hide uncertainty
- do not retroactively clean up the history so much that the reasoning disappears
- do not create empty files with no operating value

## Standard

If a new engineer opened this repo, they should be able to answer:

- what MacroLens does
- how data moves through the system
- why PostgreSQL was chosen
- why z-score detection was chosen first
- what broke and how it was fixed

If the repo cannot answer those questions, the documentation is incomplete.
