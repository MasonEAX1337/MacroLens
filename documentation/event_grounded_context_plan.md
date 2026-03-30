# Event-Grounded Context Plan

## Goal

Make MacroLens better at answering:

- what happened in the real world
- why this anomaly or episode plausibly occurred
- how market relationships fit into that event story

The current system is stronger at:

- what else moved
- which datasets aligned statistically

That is useful, but incomplete.

The product needs to move from correlation-heavy explanations toward event-grounded macro explanations.

## Core Problem

The current explanation stack is imbalanced:

1. correlation evidence is abundant
2. real-world event evidence is sparse
3. the explainer falls back to correlations because they are always available

That produces explanations that are often structurally correct but causally unsatisfying.

Example failure mode:

- the app says rates, housing, Bitcoin, and the S&P moved nearby
- the app does not say whether the anomaly aligned with:
  - a Fed pivot
  - banking stress
  - an inflation surprise
  - an oil shock
  - war
  - fiscal policy

The result sounds informed, but it answers the wrong question.

## First-Principles Design Shift

MacroLens should move from:

`anomaly -> correlations -> maybe some context`

to:

`anomaly or episode -> event context -> correlations as supporting structure`

This means:

- real-world context should explain likely drivers
- correlations should explain transmission and alignment
- explanations should not lead with market co-movement unless event evidence is genuinely absent

## Product Thesis

There are three distinct evidence classes:

1. **event evidence**
   - articles
   - curated macro timeline entries
   - structured event tags

2. **episode evidence**
   - clustered anomaly structure
   - quality band
   - participating datasets
   - propagation paths

3. **market-relationship evidence**
   - lagged correlations
   - leading indicators
   - supporting dataset movements

The current system is strongest in class 3.
To become a better investigation product, it needs to become much stronger in class 1.

## Roadmap

### Phase 1: Context Model Upgrade

#### Objective

Make contextual evidence richer and more explicit than a flat news list.

#### Build

- separate contextual evidence into:
  - `live_articles`
  - `curated_macro_timeline`
  - `structured_event_tags`
- preserve provider provenance on every context item
- add explicit context quality metadata:
  - source type
  - timing relative to anomaly or episode
  - confidence or ranking basis

#### Why

The system currently treats context too much like a single generic blob.
It should instead distinguish:

- live reporting
- curated historical regime context
- extracted event themes

### Phase 2: Episode-Level Retrieval

#### Objective

Search for real-world context around the full episode window, not only one anomaly timestamp.

#### Build

- move retrieval from anomaly-centered search to episode-aware search when a cluster exists
- use:
  - episode start
  - episode end
  - dataset family
  - direction
  - nearby correlated datasets
- keep anomaly-level search as fallback for isolated signals

#### Why

Monthly and weekly series often do not map cleanly to a single day.
Searching around one timestamp is too weak for:

- CPI
- house prices
- mortgage rates
- income series

### Phase 3: Event and Theme Extraction

#### Objective

Convert raw article hits into reusable macro event evidence.

#### Build

- extract or assign:
  - event type
  - entities
  - countries
  - institutions
  - themes
- first event/theme families should include:
  - Fed policy shift
  - inflation surprise
  - labor market shock
  - banking stress
  - oil or energy shock
  - war or geopolitical escalation
  - fiscal policy
  - housing slowdown or acceleration
  - recession scare

#### Why

The system should be able to say:

- this episode aligned with banking stress and Fed repricing

not just:

- these headlines existed nearby

### Phase 4: Explanation Priority Rewrite

#### Objective

Make explanations lead with likely real-world drivers when credible context exists.

#### Build

- rewrite explanation structure to prefer:
  1. likely real-world driver
  2. episode framing
  3. market relationships
  4. uncertainty notes
- add explicit prompt rules:
  - if credible event evidence exists, lead with it
  - correlations should support the story, not dominate it
  - do not present co-movement as cause when event evidence is present

#### Why

The current explanations often answer:

- what else moved

instead of:

- what likely happened in the world

### Phase 5: UI Upgrade For Context

#### Objective

Expose real-world drivers clearly in the investigation interface.

#### Build

- split the current context area into:
  - `Likely Real-World Drivers`
  - `Supporting Articles`
  - `Market Relationships`
- show timing relative to the episode:
  - before
  - during
  - after
- show which explanation sentences were grounded in:
  - event context
  - cluster evidence
  - correlation evidence

#### Why

Users should not have to infer whether a paragraph came from:

- news context
- curated timeline background
- or pure market structure

## Suggested Build Order

1. episode-level context retrieval
2. stronger event/theme extraction
3. explanation rewrite to prioritize real-world drivers
4. UI separation between drivers, articles, and market evidence
5. expand curated macro event coverage

## Narrow Next Sprint

If this work starts immediately, the best first sprint is:

1. add episode-level context retrieval
2. add context timing labels relative to episode windows
3. update explanation prompts so real-world context leads when available
4. change the UI language from generic `News Context` toward explicit driver/support sections

## What Success Looks Like

A better result should sound more like:

- this anomaly likely aligned with banking stress, shifting Fed expectations, and rate repricing across housing-sensitive assets

and less like:

- the strongest stored relationship was a negative correlation between rates and house prices

The second sentence is still useful.
It just should not be the main answer to a causation-style user question.

## Risks

- event context can be overread just as easily as correlations if ranking is weak
- generic article retrieval can create fluent but shallow explanations
- curated macro timeline coverage can become misleading if it is too sparse and treated as comprehensive
- explanation prompts can overclaim if they are not forced to distinguish:
  - likely driver
  - supporting evidence
  - uncertainty

## Recommendation

Make **event-grounded context** the next major product topic.

Not because correlations are wrong.
Because correlations are currently being asked to answer a question they cannot answer well on their own.
