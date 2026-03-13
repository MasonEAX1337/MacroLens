# Bug

The first GDELT integration could fail even when the HTTP request technically succeeded.

## Cause

GDELT enforces strict request pacing and can respond with:

- HTTP `429 Too Many Requests`
- plain-text rate-limit messages instead of JSON

The initial provider assumed every successful response body would be valid JSON, which caused crashes during backfill.

## Fix

- added provider-side pacing at roughly one request every five seconds
- added retry logic for rate-limited responses
- degraded non-JSON or repeated rate-limit failures to empty news context instead of crashing the pipeline

## Result

The news retrieval path became slower but much more stable.

That is the correct tradeoff for an evidence pipeline: incomplete context is acceptable, but a retrieval crash should not block explanation generation or API access.
