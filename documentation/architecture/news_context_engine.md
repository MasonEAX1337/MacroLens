# News Context Engine

## Purpose

The news context engine adds a second evidence class to MacroLens.

Correlations tell the system what else moved.
News context tries to tell the system what was being discussed around the same time.

That distinction matters. News is contextual evidence, not another market series.

## Current Role in the Pipeline

The current sequence is:

1. detect anomaly
2. compute stored correlations
3. retrieve article context around the anomaly window
4. persist article citations in PostgreSQL
5. allow the explanation layer to use both structured and contextual evidence

## Why This Exists

Without a news layer, the product can only say:

- this event was unusual
- these datasets moved nearby

That is useful, but incomplete.

A user also wants to know whether there were real-world events, headlines, or topic clusters around the anomaly.

## First-Principles Design

The system should not "correlate news" the same way it correlates price series.

Why:

- articles are not numeric time series
- relevance is semantic, not purely statistical
- provenance matters more than coefficient magnitude

So the correct first design is retrieval plus citation, not naive news correlation.

## Current Implementation

The engine now uses two contextual providers:

- `gdelt`
- `macro_timeline`

`gdelt` is the live retrieval path.
`macro_timeline` is a curated historical-context path used to cover household regimes that keyword search handles poorly.

For each anomaly, the engine:

- loads the anomaly timestamp, dataset symbol, and dataset frequency
- chooses one or more providers based on the series type
- adjusts the effective search window for slower weekly and monthly series
- builds a dataset-aware keyword query for live retrieval
- searches within a configurable date window using a deeper raw candidate pool than the final stored article count
- filters titles that do not look relevant to the dataset
- suppresses duplicate article titles
- adds curated historical entries when the anomaly lands inside a known macro regime
- ranks surviving articles by provider priority, timing, and original provider order
- stores article citations with rank and provenance

Operationally, the live provider is now treated as a recent-context provider rather than a universal historical archive.

That means:

- GDELT is queried only for anomalies inside a configurable recent-age window
- older anomalies fall back to curated macro-timeline context when available
- otherwise the system returns structured-evidence-only explanations with explicit limited-coverage status

Stored fields include:

- article URL
- title
- domain
- language
- source country
- seen timestamp
- search query
- relevance rank

## Why GDELT Was Chosen First

- supports historical article search
- works without introducing another paid API key immediately
- returns enough article metadata for a citation-first MVP

## Why Macro Timeline Was Added

The first provider exposed a real weakness:

- broad household topics often do not map cleanly to article search
- slower monthly and weekly series have weaker same-window headline alignment
- historical macro regimes matter even when there is no single decisive headline

So the system now supplements live retrieval with a curated `macro_timeline` provider for selected household scenarios.

That is a deliberate design choice, not a hack.

It reflects a first-principles distinction:

- live article search is good for event-level market context
- curated historical context is better for slower structural household regimes

## Current Weaknesses

- live keyword retrieval is noisy
- rate limiting is strict
- transport-level failures happen and must be treated as provider misses rather than pipeline-fatal errors
- curated macro-timeline coverage is intentionally sparse and does not cover every anomaly
- article timestamps are "seen" timestamps, not guaranteed publication timestamps
- historical coverage quality varies by topic and era

## Current Guardrails

- news context is stored separately from correlations
- explanations can cite article context, but the engine still treats it as evidence, not certainty
- explanations are instructed to treat `macro_timeline` items as broad background, not direct causal proof
- provider failures degrade to empty news context rather than crashing explanation generation
- the coordinated evidence-refresh workflow now commits news-context refreshes per anomaly so long backfills are resumable
- article ranking prefers leading and same-day context over clearly lagging context
- the anomaly API now distinguishes between available citations and limited provider coverage for empty news-context results
- provider ordering surfaces curated household context before weaker live retrieval when both exist

## What Should Improve Next

### Retrieval quality

- better dataset-specific query templates
- domain filtering
- duplicate suppression
- title-cleaning normalization

### Trust and provenance

- expose search query and provider more clearly in the UI
- show whether articles are before, during, or after the anomaly
- keep article citations inspectable

### Longer-term

- expand curated macro-timeline coverage beyond the first household regimes
- add a second live provider for comparison if GDELT remains too noisy
- add semantic reranking over stored article candidates
- use extracted event entities rather than only raw titles
