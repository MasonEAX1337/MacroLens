# Experiment: Detector Anomaly Density Audit

## Goal

Measure whether the current anomaly engine is starving the episode graph for specific datasets.

## Method

Using the live Postgres database:

1. count anomalies per dataset
2. break counts down by frequency and detection method
3. compare anomaly supply to dataset length and observed episode quality

## Baseline Findings

Before the override pass, anomaly supply was highly uneven.

Examples:

- `CPIAUCSL`: `4` anomalies
- `CSUSHPISA`: `1`
- `MORTGAGE30US`: `12`
- `BTC`: `5`
- `DCOILWTICO`: `53`
- `FEDFUNDS`: `37`

Two patterns stood out:

1. slow monthly household series were under-producing badly
2. daily `change_point` detection was almost absent outside isolated cases

## Intervention

Added first-pass dataset-specific overrides:

- lower z-score threshold for `CPIAUCSL` and `CSUSHPISA`
- lower change-point penalty for:
  - `BTC`
  - `DCOILWTICO`
  - `SP500`
  - `CPIAUCSL`
  - `CSUSHPISA`
  - `MORTGAGE30US`

## Post-Override Result

After a full stored-data refresh:

- total anomalies: `145 -> 158`
- `CPIAUCSL`: `4 -> 11`
- `CSUSHPISA`: `1 -> 6`
- `MORTGAGE30US`: `12 -> 13`

Live post-refresh counts by dataset and method:

- `A229RX0`: monthly `z_score=21`
- `BTC`: daily `z_score=4`, `change_point=1`
- `CPIAUCSL`: monthly `z_score=11`
- `CSUSHPISA`: monthly `z_score=6`
- `DCOILWTICO`: daily `z_score=52`, `change_point=1`
- `FEDFUNDS`: monthly `z_score=23`, `change_point=14`
- `MORTGAGE30US`: weekly `z_score=6`, `change_point=7`
- `SP500`: daily `z_score=12`

## Interpretation

The override pass improved anomaly supply where the graph was clearly starved.

It did not solve the deeper issue entirely:

- daily market `change_point` is still sparse
- some slow monthly series may need different event definitions, not just lower thresholds
- better anomaly counts do not automatically imply better episode formation

## Conclusion

The live evidence supports a narrow dataset-specific tuning layer.

The next question is not whether overrides are allowed.
The next question is whether the new anomalies produce better cross-dataset episodes or only inflate raw counts.
