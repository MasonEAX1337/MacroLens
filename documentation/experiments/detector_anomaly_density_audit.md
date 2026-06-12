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

## Follow-Up: Episode Outcome Auditability

The original audit measured anomaly density, but its unresolved risk was downstream usefulness:

- a new anomaly is useful when it becomes part of a meaningful episode, bridge, or same-dataset wave
- a new anomaly is weaker when it remains an isolated low-quality signal
- a new anomaly is actively suspect when it is later suppressed by the episode filter

To make that distinction auditable, the graph-quality report now includes episode outcomes by dataset and detection method.

The added report section tracks:

- total anomalies
- clustered anomalies
- suppressed anomalies
- isolated signals
- single-dataset waves
- cross-dataset episodes
- medium-or-high-quality cluster membership

That makes the detector audit stricter. Future override changes should not be justified by raw anomaly counts alone.

### Current Verification Result

The live graph-quality snapshot was refreshed after starting the local PostgreSQL Docker service and rebuilding the evidence graph.

The refresh used:

```powershell
docker compose up -d db
Get-Content -Raw database\schema.sql | docker exec -i macrolens-db psql -U postgres -d macrolens
.\.venv\Scripts\python scripts\ingest\run_ingestion.py --dataset bitcoin --dataset cpi --dataset fed_funds --dataset wti --dataset sp500 --dataset house_price_us --dataset mortgage_30y --dataset income_real_per_capita --skip-news-context --skip-explanations
.\.venv\Scripts\python scripts\clusters\recompute_clusters.py
.\.venv\Scripts\python scripts\news\fetch_news_context.py --local-only
.\.venv\Scripts\python scripts\explanations\generate_explanations.py --provider rules_based --quiet
.\.venv\Scripts\python scripts\evaluation\report_graph_quality.py
```

The generated `documentation/research/latest_graph_quality_snapshot.json` now includes `anomaly_episode_outcomes`.

Key audit findings from the refreshed snapshot:

- `CPIAUCSL` `change_point`: `27` total, `24` clustered, `3` suppressed, `10` cross-dataset episodes
- `CSUSHPISA` `change_point`: `15` total, `9` clustered, `6` suppressed, `7` cross-dataset episodes
- `DCOILWTICO` `change_point`: `1` total, `1` cross-dataset episode
- `MORTGAGE30US` `change_point`: `7` total, `1` cross-dataset episode
- total suppressed anomalies: `9`
- bridge-preserved change points: `33`

This proves the monthly transformed change-point supply is not only inflating raw counts. A meaningful subset is participating in cross-dataset episodes, while weak isolated monthly change points are still being suppressed.
