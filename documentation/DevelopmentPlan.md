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
- nearby anomalies can be grouped into persisted macro-event clusters
- news context can be retrieved and persisted
- explanations can be generated and persisted
- the frontend can visualize timeseries and anomaly detail against the live API

### Implemented datasets

- Bitcoin
- CPI
- Federal Funds Rate
- WTI oil
- S&P 500
- U.S. house prices
- 30-year mortgage rate
- real disposable personal income per capita

### Implemented interface

- dataset selection
- multi-dataset 3D constellation view
- timeseries chart
- leading-indicator panel
- side-by-side supporting-episode comparison inside each leading-indicator row
- anomaly markers
- event detail panel
- macro-event cluster panel
- propagation timeline panel
- correlation display
- news context display
- explanation display
- explanation regeneration from the event panel

### Important truth

The system is functionally coherent, but it is not yet finished.

The two biggest gaps are:

1. the hosted-provider path is usable, but not yet compared rigorously enough to justify a default change
2. change-point detection is now live, but it still needs deeper comparative evaluation and tuning
3. contextual retrieval now has a hybrid path, but curated macro-timeline coverage is still sparse

One important milestone has now been cleared:

- the project supports a first household macro cluster in addition to the original market and policy series
- the hosted explanation path has been validated on live anomalies strongly enough to continue development without blocking on prompt work
- the system now has both structured and contextual evidence classes

## First-Principles Breakdown

MacroLens reduces to eight systems:

1. data acquisition
2. evidence storage
3. event detection
4. event grouping
5. contextual retrieval
6. relationship aggregation
7. interpretation
8. user investigation

The first pass of all eight now exists.

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
- `ruptures`-based binary segmentation implemented as a second detector
- frequency-aware defaults added
- clustered anomaly collapse implemented
- anomaly metadata persisted
- live backfill completed through the new evidence-refresh workflow

### Phase 5: Correlation Engine

Completed for MVP.

- bounded event windows implemented
- percent-change transformation implemented
- lag-aware correlation search implemented
- correlation persistence implemented
- clustered leading-indicator aggregation implemented on top of persisted correlation evidence

### Phase 6: Explanation Engine

Completed in staged form.

- provider abstraction implemented
- rules-based provider implemented
- OpenAI-backed provider path implemented
- Gemini-backed provider path implemented
- fallback behavior implemented
- explanation persistence implemented

This phase is technically complete for the system loop, but not complete for product ambition or operational confidence.

### Phase 9: Evidence Refresh Workflow

Completed for current scope.

- coordinated evidence refresh implemented from stored data
- downstream stages can now be resumed independently when a long refresh is interrupted
- historical live-news retrieval is capped to a recent window so refresh time stays bounded

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

### Priority 2: Deepen hybrid contextual evidence

The first news layer proved the evidence model.
The new macro-timeline layer fixed a real household gap.
The remaining problem is now coverage quality rather than architecture.

#### Highest-value improvements

- expand curated macro-timeline coverage for additional policy and household regimes
- improve live-retrieval quality where GDELT is still noisy
- decide where curated historical context should replace live retrieval entirely for older regimes
- better time-window interpretation in the UI and explainer
- optional domain filtering or source weighting for live retrieval

#### Main risk

Weak contextual evidence can make the product feel smarter while actually making it less trustworthy.

### Priority 3: Validate and improve change-point detection

The second detector now exists in code and has been backfilled into the live evidence graph.
The next task is to make it analytically credible.

#### Highest-value improvements

- run comparative evaluation between `z_score` and `change_point`
- tune frequency-aware and eventually dataset-specific change-point configs on real datasets
- decide whether slower structural series need alternate event-type classification beyond first-pass `level_shift`

#### Main risk

Over-trusting the new detector before comparative evaluation would make the product look more advanced than it really is.

### Priority 4: Evaluate and tune leading-indicator discovery

The first version now exists.
The next task is to decide whether the ranking is analytically useful enough to trust.

#### Highest-value improvements

- inspect top-ranked leaders for CPI, Fed funds, mortgage rates, and household series
- evaluate whether the new sign-consistency weighting is sufficient or still too permissive
- use the new side-by-side episode comparison browser to inspect whether repeated leaders remain stable across different cluster shapes and regimes
- continue validating whether the new frequency-alignment term is enough to keep mixed-frequency relationships from being overread as broad "leaders"
- evaluate whether the new support-confidence term is enough to keep one-cluster leaders from being overread as mature repeated signals

#### Main risk

A leading-indicator panel is useful only if it reflects repeated episodes rather than accidental lag matches.

### Priority 5: Continue deepening the frontend investigation workflow

The frontend is now materially better than the original MVP shell, but it still stops short of full investigative usefulness.

#### Highest-value improvements

- richer comparison semantics in the constellation view
- clearer selected-range feedback around the chart brush
- anomaly clustering or bucketing for dense daily series
- clearer evidence-provider comparison in the event panel
- decide whether supporting-episode comparison should eventually include sparklines or remain metadata-first
- improve episode quality so ranking trust depends less on heuristic patching and more on better event units

### Priority 6: Add scheduled pipeline execution

The MVP currently runs through manual commands.

That is acceptable during buildout, but the next operational step is predictable refresh behavior.

#### Recommended MVP approach

- simple scheduler
- daily or twice-daily refresh
- ingestion run logging review

Do not overbuild orchestration yet.

## Recommended Build Order From Here

1. compare and harden hosted provider behavior
2. deepen hybrid contextual evidence
3. improve change-point credibility through evaluation and tuning
4. improve event clustering and episode quality
5. continue frontend investigation improvements on top of better episodes

This order keeps the work aligned with the product thesis.

## Concrete Next Sprint Plan

### Sprint Goal

Upgrade MacroLens from a working vertical slice to a more believable intelligence product.

### Sprint Deliverables

1. hosted-provider comparison pass
2. news-context quality improvements
3. episode-quality improvement pass
4. targeted frontend follow-up work on top of better episodes

### Suggested Task Breakdown

#### Evaluation

- compare Gemini and OpenAI outputs on the same anomaly sample
- document provider selection criteria
- decide whether the rules-based provider should remain the default

#### Retrieval

- tighten dataset-specific GDELT queries
- document rate-limit behavior and retry policy
- inspect retrieved articles for relevance drift
- evaluate whether household macro terms need source weighting because they are broader and noisier than asset-specific queries
- expand curated timeline coverage where recent-only live retrieval is the wrong tool

#### Frontend

- add selected-range feedback around the chart brush
- optimize and deepen the 3D constellation view
- make provider comparison clearer inside the event panel

#### Episode Quality

- make clustering frequency-aware instead of globally fixed
- add explicit quality metadata for sparse vs broader episodes
- decide how single-anomaly episodes should be labeled in the UI and downstream systems

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
- The weakest thing in the repo right now is no longer the UI shell. It is the combination of uneven contextual coverage and still-early second-detector tuning.

The next phase should deepen trust, not broaden complexity.
