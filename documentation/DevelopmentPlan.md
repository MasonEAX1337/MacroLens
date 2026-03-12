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
- explanations can be generated and persisted
- the frontend can visualize timeseries and anomaly detail against the live API

### Implemented datasets

- Bitcoin
- CPI
- Federal Funds Rate
- WTI oil

### Implemented interface

- dataset selection
- timeseries chart
- anomaly markers
- event detail panel
- correlation display
- explanation display

### Important truth

The system is functionally coherent, but it is not yet finished.

The two biggest gaps are:

1. the explanation layer is still rules-based
2. the dataset set is still thinner than the original product vision

## First-Principles Breakdown

MacroLens reduces to five systems:

1. data acquisition
2. evidence storage
3. event detection
4. relationship and interpretation
5. user investigation

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

Completed in provisional form.

- provider abstraction implemented
- rules-based provider implemented
- explanation persistence implemented

This phase is technically complete for the system loop, but not complete for product ambition.

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

### Priority 1: Replace the rules-based explanation provider with a live LLM provider

This is the highest leverage next step because it upgrades the most product-visible part of the system.

#### Why this matters

- the current rules-based output proves architecture but not differentiation
- a grounded LLM explainer is closer to the actual product thesis
- the provider boundary already exists, so the remaining work is targeted

#### Required work

1. implement OpenAI or Anthropic provider class
2. build structured prompt templates
3. restrict output to supplied evidence
4. store provider/model metadata
5. support regeneration on demand

#### Risks

- hallucination
- generic language
- false certainty from weak correlations

#### Guardrails

- keep the rules-based provider as fallback
- include uncertainty instructions in prompts
- keep evidence payloads explicit and inspectable

### Priority 2: Add one more high-recognition market dataset

The obvious candidate is S&P 500.

#### Why this matters

- it was part of the original product framing
- it increases the credibility of cross-market analysis
- it produces more intuitive event narratives for users

#### Required work

1. choose stable source
2. add ingestion client
3. normalize timestamps and frequency assumptions
4. rerun pipeline
5. validate new correlations

### Priority 3: Improve the frontend investigation workflow

The current UI works, but it is still a first-pass operator console rather than a polished investigation tool.

#### Highest-value improvements

- chart zoom or brush selection
- anomaly severity filtering
- date-range filtering
- better visual distinction between positive and negative events
- explanation regeneration control
- evidence provenance display

#### Why this matters

If the user cannot interrogate the evidence easily, the intelligence value of the backend is partially wasted.

### Priority 4: Add backend integration tests against the live database

Current tests are useful but still too centered on unit behavior.

#### Additions needed

- API integration tests with seeded DB state
- ingestion smoke tests against test database
- anomaly persistence validation
- correlation persistence validation
- explanation persistence validation

### Priority 5: Add scheduled pipeline execution

The MVP currently runs through manual commands.

That is acceptable during buildout, but the next operational step is predictable refresh behavior.

#### Recommended MVP approach

- simple scheduler
- daily or twice-daily refresh
- ingestion run logging review

Do not overbuild orchestration yet.

## Recommended Build Order From Here

1. implement live LLM provider integration
2. add S&P 500 ingestion
3. improve frontend interaction depth
4. add DB-backed integration tests
5. add scheduler and refresh workflow

This order keeps the work aligned with the product thesis.

## Concrete Next Sprint Plan

### Sprint Goal

Upgrade MacroLens from a working vertical slice to a more believable intelligence product.

### Sprint Deliverables

1. live explanation provider
2. one additional major dataset
3. chart interaction improvements
4. backend integration tests

### Suggested Task Breakdown

#### Backend

- create `OpenAIExplanationProvider` or equivalent
- add prompt builder module
- add explanation regeneration endpoint or command
- add dataset definition for S&P 500

#### Frontend

- add chart brush/zoom
- add anomaly list filtering
- add explicit evidence/provenance section
- add empty/error state refinement

#### Testing

- create DB seed fixture
- add API integration suite
- add explanation provider tests

## Definition of MVP Completion

MacroLens can be called MVP-complete when all of the following are true:

1. at least five meaningful datasets are supported
2. the explanation layer can run through a live LLM provider
3. the frontend supports interactive event investigation beyond static selection
4. the backend has integration-level verification, not only unit tests
5. the product can be refreshed repeatably with a documented operational workflow

## Hard Truths

- The architecture is now real enough that the next mistakes will be judgment mistakes, not scaffolding mistakes.
- Adding more code is no longer the main challenge. Choosing what not to add is.
- The strongest thing in the repo right now is the evidence pipeline.
- The weakest thing in the repo right now is that the final explanation layer still stops short of the intended intelligence experience.

The next phase should deepen trust, not broaden complexity.
