# Decision

Treat curated historical context as a small structured event registry rather than only a list of article-like timeline entries.

## Context

MacroLens improved coverage by adding curated historical context, but the remaining weakness was obvious:

- a title alone is not enough to explain an event well
- the evidence layer needed reusable event meaning, not just a source link

The product needed to answer:

- what matched
- what kind of event it was
- why it mattered

without forcing the explanation layer to infer all of that from a title string.

## Alternatives Considered

### Keep curated history as plain article-style entries

Rejected.

That would preserve coverage but keep explanations too title-dependent and too brittle.

### Add a new `historical_events` table immediately

Deferred.

This is a plausible longer-term direction, but it adds schema and migration surface before the registry model has been validated inside the existing pipeline.

### Mine a broad list of historical events automatically

Rejected.

That would create a larger but noisier event corpus before the matching model was ready.

## Reasoning

The smallest defensible step was:

1. keep the existing curated historical provider
2. make its entries structurally explicit
3. pass those fields through the existing `news_context` evidence surface

That preserves the current architecture while making the curated layer more useful for:

- explanation generation
- UI display
- later event matching work

The important distinction is:

- raw article citation is provenance
- structured event fields are reusable macro meaning

MacroLens needs both.

## Consequences

Positive:

- explanations can use event summaries instead of only source titles
- the UI can show more than a link when curated history is the evidence source
- the system now has a clearer path toward a future persisted historical-event table

Negative:

- the registry still lives inside `news_context` metadata, which is not ideal forever
- curation remains manual and selective
- provider naming still reflects the older `macro_timeline` label even though the behavior is closer to an event registry

Follow-up work:

- validate whether registry-backed context consistently improves explanations
- add semantic reranking across registry and live article evidence
- decide whether the registry should eventually become a dedicated persisted table
