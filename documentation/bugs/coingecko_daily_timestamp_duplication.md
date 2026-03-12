# Bug Record: CoinGecko Daily Timestamp Duplication

## Bug

Bitcoin daily data from CoinGecko produced duplicate same-day rows with different timestamps.

Example pattern:

- one row at midnight UTC
- another row later in the same day

## Cause

The source payload includes timestamps that are valid as raw data points but do not match the product assumption of one normalized daily observation per day.

Without normalization, the uniqueness constraint on `(dataset_id, timestamp)` was not enough because the timestamps were technically different even though they represented the same logical day.

## Fix

- normalize CoinGecko timestamps to midnight UTC before persistence
- switch current source ingestion to full-refresh replacement so stale malformed rows are removed on rerun

## Result

- the chart no longer shows duplicate same-day points
- anomaly detection sees a cleaner series
- correlation windows become more trustworthy

## Lesson

Time-series integrity problems often look minor at the source layer and major everywhere else.
