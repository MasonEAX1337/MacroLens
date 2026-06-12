# Bug: Change-Point Volatility Shifts Were Under-Scored

## Bug

The change-point detector could classify a breakpoint as a `volatility_shift`, but the persisted severity score was still based only on the mean shift.

That meant a pure volatility-regime change could be detected by the segmentation algorithm, labeled as volatility-driven, and then filtered out because the mean difference was small.

## Cause

`classify_change_point_event_type` compared mean-shift magnitude against volatility-shift magnitude, but `detect_change_point_anomalies` calculated severity only from `delta_mean`.

The scoring rule did not match the event classification rule.

## Fix

The detector now calculates both:

- `mean_shift_score`
- `volatility_shift_score`

The persisted severity score is the larger of the two. For `volatility_shift` events, direction now reflects whether volatility increased or decreased.

The detector metadata now stores:

- `before_std`
- `after_std`
- `delta_std`
- `mean_shift_score`
- `volatility_shift_score`

## Result

Volatility-regime changes are no longer silently down-scored just because their mean level is stable.

This makes the change-point detector more consistent with its documented purpose and closes one audit-relevant blind spot around volatility clusters.
