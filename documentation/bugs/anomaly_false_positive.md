# Bug Record: Anomaly False Positive

## Bug

False anomalies appear in inflation-oriented datasets where the series moves with expected seasonal structure rather than true shocks.

## Cause

Plain rolling z-score detection can mistake normal recurring variation for abnormal behavior when the series is low-frequency or seasonal.

## Fix

- tune window size by dataset frequency
- consider smoothing or seasonal adjustment before scoring
- store dataset-specific anomaly configuration instead of using one global threshold

## Result

False positives should decrease, but the real fix is methodological rather than cosmetic threshold tuning.
