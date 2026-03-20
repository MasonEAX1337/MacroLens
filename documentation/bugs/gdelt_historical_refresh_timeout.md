# Bug

Coordinated evidence refreshes stalled or failed when the system attempted live GDELT retrieval across the full historical anomaly corpus.

## Cause

The first refresh workflow treated GDELT as if it were a good fit for every anomaly in the database, including older macro events from the 1960s through the 1980s.

That created two problems:

- long refresh times due to strict rate limiting and a large number of low-value requests
- full-stage failure when a single transport timeout occurred during live retrieval

## Fix

- treated GDELT as a recent-context provider rather than a universal historical archive
- added a configurable anomaly-age cutoff before live retrieval is attempted
- kept curated `macro_timeline` coverage for selected historical household regimes
- hardened GDELT transport failures so request timeouts degrade to empty context instead of aborting the refresh
- changed the evidence-refresh workflow to commit news-context updates per anomaly so interrupted runs are resumable

## Result

The live refresh path is now operationally credible:

- anomalies, clusters, and correlations can be rebuilt coherently
- explanations can be regenerated across the live anomaly set
- recent anomalies still get live article retrieval
- older anomalies now fail honestly into limited coverage or curated historical context instead of wasting time on weak live queries
