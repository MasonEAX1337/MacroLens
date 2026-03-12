# Bug Record: Correlation Lag Issue

## Bug

Related datasets can appear uncorrelated when one series reacts several days or weeks after the triggering event.

## Cause

Same-day correlation assumes synchronized movement, which is often false in macroeconomic systems.

## Fix

- test bounded positive and negative lags
- require minimum overlap after lagging
- store `lag_days` with each result

## Result

Lag-aware scoring should recover more realistic relationships and reduce false negatives in event analysis.
