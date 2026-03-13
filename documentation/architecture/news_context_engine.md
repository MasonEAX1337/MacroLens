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

The first provider is GDELT DOC 2.0 article search.

For each anomaly, the engine:

- loads the anomaly timestamp and dataset symbol
- builds a dataset-aware keyword query
- searches within a configurable date window
- filters titles that do not look relevant to the dataset
- suppresses duplicate article titles
- ranks surviving articles by timing and original provider order
- stores article citations with rank and provenance

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

## Current Weaknesses

- keyword retrieval is noisy
- rate limiting is strict
- ranking is shallow
- article timestamps are "seen" timestamps, not guaranteed publication timestamps
- historical coverage quality varies by topic and era

## Current Guardrails

- news context is stored separately from correlations
- explanations can cite article context, but the engine still treats it as evidence, not certainty
- provider failures degrade to empty news context rather than crashing explanation generation
- article ranking prefers leading and same-day context over clearly lagging context

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

- add second provider for comparison
- add semantic reranking over stored article candidates
- use extracted event entities rather than only raw titles
