# MacroLens Development Plan

## Objective

Turn MacroLens from a working vertical slice into a credible, defensible MVP that can survive technical scrutiny.

The difference matters.

A working demo proves assembly.
A credible MVP proves judgment.

## Current Status

As of March 12, 2026, the project has completed the first major system loop:

- datasets can be ingested into PostgreSQL
- anomalies can be detected and persisted
- correlations can be computed and persisted
- news context can be retrieved and persisted
- explanations can be generated and persisted
- the frontend can visualize timeseries and anomaly detail against the live API

### Implemented datasets

- Bitcoin
- CPI
- Federal Funds Rate
- WTI oil
- S&P 500

### Implemented interface

- dataset selection
- multi-dataset 3D constellation view
- timeseries chart
- anomaly markers
- event detail panel
- correlation display
- news context display
- explanation display
- explanation regeneration from the event panel

### Important truth

The system is functionally coherent, but it is not yet finished.

The two biggest gaps are:

1. the hosted-provider path is usable, but not yet compared rigorously enough to justify a default change
2. contextual retrieval quality is still noisier than the rest of the evidence pipeline
3. the new multi-dataset visual layer is useful, but it introduced a frontend performance cost that should be managed intentionally

One important milestone has now been cleared:

- the project supports five meaningful datasets, including S&P 500
- the hosted explanation path has been validated on live anomalies strongly enough to continue development without blocking on prompt work
- the system now has both structured and contextual evidence classes

## First-Principles Breakdown

MacroLens reduces to five systems:

1. data acquisition
2. evidence storage
3. event detection
4. contextual retrieval
5. relationship and interpretation
6. user investigation

The first pass of all five now exists.

The next stage is quality:

- better evidence
- better explanation
- better interaction

## What Has Been Completed

### Phase 1: Foundation

Completed.

- repo structure created
- backend and frontend scaffolds created
- local environment shape defined

### Phase 2: Database Schema

Completed.

- PostgreSQL schema written
- core tables created
- indexes added
- ingestion traceability added through `ingestion_runs`

### Phase 3: Ingestion

Completed for current datasets.

- CoinGecko integration implemented
- FRED integration implemented
- timestamp normalization implemented
- full-refresh write strategy implemented for current sources
- first-pass news retrieval implemented through GDELT

### Phase 4: Anomaly Detection

Completed for MVP.

- rolling z-score detection implemented
- frequency-aware defaults added
- clustered anomaly collapse implemented
- anomaly metadata persisted

### Phase 5: Correlation Engine

Completed for MVP.

- bounded event windows implemented
- percent-change transformation implemented
- lag-aware correlation search implemented
- correlation persistence implemented

### Phase 6: Explanation Engine

Completed in staged form.

- provider abstraction implemented
- rules-based provider implemented
- OpenAI-backed provider path implemented
- Gemini-backed provider path implemented
- fallback behavior implemented
- explanation persistence implemented

This phase is technically complete for the system loop, but not complete for product ambition or operational confidence.

### Phase 7: API Layer

Completed for current scope.

- dataset list endpoint
- timeseries endpoint
- anomaly list endpoint
- anomaly detail endpoint
- CORS support for the frontend

### Phase 8: Frontend Experience

Completed for MVP baseline.

- live chart rendering
- anomaly markers
- event panel
- correlation list
- explanation rendering

## What Was Learned

### 1. Data normalization is not incidental

The CoinGecko timestamp duplication bug proved a simple but important point:

if timestamps are not normalized correctly, the whole reasoning chain becomes subtly wrong.

This is not cosmetic. It affects:

- chart integrity
- anomaly scoring
- correlation windows
- explanation credibility

### 2. Full-refresh ingestion is the correct current strategy

For the current source model, full refresh is better than naive append-only updates.

Why:

- source pulls represent current truth snapshots
- stale rows are more dangerous than reinsert cost
- current scale is small enough that full refresh is operationally cheap

This may change later, but it is the right call now.

### 3. Correlation must be treated as supporting evidence only

The current system can produce non-trivial correlations, but those outputs can still mislead if framed carelessly.

That means the product and UI should continue to:

- avoid causal wording
- surface lag information clearly
- treat explanation output as informed interpretation, not factual certainty

### 4. The explanation abstraction was worth doing early

Using a provider interface before integrating a live LLM kept the architecture honest.

That choice created three benefits:

- the pipeline became end-to-end testable immediately
- explanation persistence shape was defined early
- LLM integration can now be added without rewriting the system boundary

## Next Development Priorities

The next phase should focus on value density, not surface area.

### Priority 1: Compare and harden hosted explanation providers

The explanation path is now usable, which changes the task. The problem is no longer basic integration. The problem is comparative judgment.

#### Required work

1. run side-by-side evaluations of OpenAI and Gemini on the same anomaly set
2. define an explanation quality rubric
3. measure fallback behavior under missing-key and HTTP-failure conditions
4. decide whether a hosted provider should become the default
5. surface provider provenance more clearly in the UI

#### Main risk

The danger is no longer that the provider fails to respond. The danger is that it responds fluently while overstating evidence.

### Priority 2: Improve news-context retrieval quality

The first news layer proves the evidence model, but it does not yet prove retrieval quality.

#### Highest-value improvements

- better dataset-specific query templates
- duplicate suppression across domains
- better time-window interpretation in the UI and explainer
- optional domain filtering or source weighting

#### Main risk

Weak article ranking can make the product feel smarter while actually making it less trustworthy.

### Priority 3: Continue deepening the frontend investigation workflow

The frontend is now materially better than the original MVP shell, but it still stops short of full investigative usefulness.

#### Highest-value improvements

- richer comparison semantics in the constellation view
- clearer selected-range feedback around the chart brush
- anomaly clustering or bucketing for dense daily series
- clearer evidence-provider comparison in the event panel

### Priority 4: Add scheduled pipeline execution

The MVP currently runs through manual commands.

That is acceptable during buildout, but the next operational step is predictable refresh behavior.

#### Recommended MVP approach

- simple scheduler
- daily or twice-daily refresh
- ingestion run logging review

Do not overbuild orchestration yet.

## Recommended Build Order From Here

1. compare and harden hosted provider behavior
2. improve news-context retrieval quality
3. continue frontend investigation improvements
4. add scheduler and refresh workflow

This order keeps the work aligned with the product thesis.

## Concrete Next Sprint Plan

### Sprint Goal

Upgrade MacroLens from a working vertical slice to a more believable intelligence product.

### Sprint Deliverables

1. hosted-provider comparison pass
2. news-context quality improvements
3. targeted frontend follow-up work
4. operational refresh workflow

### Suggested Task Breakdown

#### Evaluation

- compare Gemini and OpenAI outputs on the same anomaly sample
- document provider selection criteria
- decide whether the rules-based provider should remain the default

#### Retrieval

- tighten dataset-specific GDELT queries
- document rate-limit behavior and retry policy
- inspect retrieved articles for relevance drift

#### Frontend

- add selected-range feedback around the chart brush
- optimize and deepen the 3D constellation view
- make provider comparison clearer inside the event panel

## Definition of MVP Completion

MacroLens can be called MVP-complete when all of the following are true:

1. at least five meaningful datasets are supported
2. the explanation layer can run through a live LLM provider with acceptable grounding and fallback behavior
3. the frontend supports interactive event investigation beyond static selection
4. the backend has integration-level verification, not only unit tests
5. the product can retrieve and display contextual evidence with acceptable relevance quality
6. the product can be refreshed repeatably with a documented operational workflow

## Hard Truths

- The architecture is now real enough that the next mistakes will be judgment mistakes, not scaffolding mistakes.
- Adding more code is no longer the main challenge. Choosing what not to add is.
- The strongest thing in the repo right now is the evidence pipeline.
- The weakest thing in the repo right now is no longer the UI shell. It is the combination of limited integration-grade verification and noisy contextual retrieval.

The next phase should deepen trust, not broaden complexity.
