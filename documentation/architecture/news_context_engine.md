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
3. retrieve article context around the anomaly or episode window
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
`macro_timeline` is a curated historical-context path used to cover older and better-known macro regimes that keyword search handles poorly.

For each anomaly, the engine:

- loads the anomaly timestamp, dataset symbol, and dataset frequency
- checks whether the anomaly belongs to a non-trivial stored cluster
- chooses one or more providers based on the configured provider mode
- derives either:
  - an anomaly-centered context window
  - or an episode-centered context window based on cluster span
- adjusts the effective search window for slower weekly and monthly series
- builds a dataset-aware keyword query for live retrieval, with narrow extra hint terms when an episode contains multiple datasets
- searches within a configurable date window using a deeper raw candidate pool than the final stored article count
- filters titles that do not look relevant to the dataset
- suppresses duplicate article titles
- adds curated historical entries when the anomaly or episode window lands inside a known macro regime
- ranks surviving articles by provider priority, episode timing, and original provider order
- stores article citations with rank and provenance
- extracts first-pass event themes from article titles and query context

Operationally, the live provider is now treated as a recent-context provider rather than a universal historical archive.

That means:

- GDELT is queried only for anomalies inside a configurable recent-age window
- the default provider mode is now `hybrid`, so curated macro-timeline context is available for all series when it exists
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
- retrieval scope
- timing relation
- context window start
- context window end
- event themes
- primary theme

The retrieval scope is now explicit:

- `anomaly`
- `episode`
- `curated_timeline`

That matters because slower clustered episodes should no longer pretend that every context item was found from a single-day anomaly lookup.

The current theme extraction layer is intentionally narrow.

It is not a full semantic event model.
It is a deterministic tagging pass over:

- article title
- search query context
- dataset-specific theme priors

That first pass is enough to let the app say things like:

- banking stress
- fed policy
- inflation
- housing
- market stress

without pretending it has solved macro event understanding.

## Why GDELT Was Chosen First

- supports historical article search
- works without introducing another paid API key immediately
- returns enough article metadata for a citation-first MVP

## Why Macro Timeline Was Added

The first provider exposed a real weakness:

- broad household topics often do not map cleanly to article search
- slower monthly and weekly series have weaker same-window headline alignment
- historical macro regimes matter even when there is no single decisive headline

So the system now supplements live retrieval with a curated `macro_timeline` provider for selected historical macro scenarios.

That is a deliberate design choice, not a hack.

It reflects a first-principles distinction:

- live article search is good for event-level market context
- curated historical context is better for slower structural regimes and older benchmark episodes

The timeline matcher is now episode-aware.

That means:

- it can match against the anomaly's primary dataset
- or against the broader set of datasets participating in the anomaly's cluster

This matters because many useful real-world drivers are not specific to only one series.
A 2022 oil anomaly and a 2022 Fed anomaly can both belong to the same geopolitical shock.

## Current Weaknesses

- live keyword retrieval is noisy
- rate limiting is strict
- transport-level failures happen and must be treated as provider misses rather than pipeline-fatal errors
- curated macro-timeline coverage is still intentionally sparse and does not cover every anomaly
- article timestamps are "seen" timestamps, not guaranteed publication timestamps
- historical coverage quality varies by topic and era
- the current curated set helps on episodes like March 2022 and October 2008, but many older anomalies such as early-1990s CPI or 2003 housing still have no real-world context

## Current Guardrails

- news context is stored separately from correlations
- explanations can cite article context, but the engine still treats it as evidence, not certainty
- explanations are instructed to treat `macro_timeline` items as broad background, not direct causal proof
- provider failures degrade to empty news context rather than crashing explanation generation
- the coordinated evidence-refresh workflow now commits news-context refreshes per anomaly so long backfills are resumable
- article ranking now prefers episode-during context first, then slightly leading context, then lagging context
- the anomaly API now distinguishes between available citations and limited provider coverage for empty news-context results
- provider ordering now prefers curated macro-timeline context over generic live articles when both point at the same episode
- stored context now records whether the item was retrieved against an anomaly window, an episode window, or curated timeline coverage

## What Should Improve Next

### Retrieval quality

- better dataset-specific query templates
- domain filtering
- duplicate suppression
- title-cleaning normalization
- semantic reranking over stored context candidates
- continued expansion of curated historical coverage where live retrieval is predictably weak

### Trust and provenance

- expose search query and provider more clearly in the UI
- show whether context is before, during, or after the anomaly or episode
- keep article citations inspectable
- distinguish:
  - live articles
  - curated macro timeline items
  - structured event tags
- expose the first-pass primary theme when one is available

### Product direction

The next major step is not just "more articles."
It is a shift toward **event-grounded context**.

That means the system should increasingly answer:

- what likely happened in the real world

before it answers:

- what else moved statistically

Correlations should remain supporting evidence.
They should not keep dominating explanations when better real-world context is available.

### Longer-term

- expand curated macro-timeline coverage beyond the first household regimes
- add a second live provider for comparison if GDELT remains too noisy
- add semantic reranking over stored article candidates
- use extracted event entities and macro themes rather than only raw titles
