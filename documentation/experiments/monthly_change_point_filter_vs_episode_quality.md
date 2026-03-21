# Experiment

Monthly change-point filtering versus global episode quality.

## Goal

Test whether removing weak transformed monthly change-point anomalies from `CPIAUCSL` and `CSUSHPISA` improves the live episode graph, rather than only improving anomaly quality in isolation.

## Methods Tested

### Method A

Keep the transformed monthly change-point supply without an additional transformed-change floor.

### Method B

Apply narrow dataset-specific transformed monthly filters:

- `CPIAUCSL`
  - `abs(delta_mean) >= 0.0018`
  - `abs(transformed_value) >= 0.0006`
- `CSUSHPISA`
  - `abs(transformed_value) >= 0.0029`

The filter was applied:

- only inside the `change_point` path
- only for these two monthly series
- without changing timestamps
- without affecting `z_score`

## Dataset

Live PostgreSQL evidence graph after the transformed monthly change-point rollout.

Focus datasets:

- `CPIAUCSL`
- `CSUSHPISA`

Observed through:

- anomaly counts by detector
- cluster membership
- episode kind distribution
- quality-band distribution

## Results

The local anomaly cleanup worked.

Weak monthly change-point anomalies were removed.

Removed `CPIAUCSL` weak change points included:

- `1948-02-01`
- `1958-05-01`
- `1988-04-01`

Removed `CSUSHPISA` weak change points included:

- `1990-05-01`
- `1991-05-01`
- `2006-04-01`
- `2007-03-01`
- `2009-05-01`
- `2025-03-01`

But the live episode graph degraded.

Before the filter:

- clusters: `161`
- `cross_dataset_episode`: `27`
- `isolated_signal`: `127`
- `single_dataset_wave`: `7`
- quality bands:
  - `low`: `133`
  - `medium`: `27`
  - `high`: `1`

After the filter:

- clusters: `160`
- `cross_dataset_episode`: `20`
- `isolated_signal`: `133`
- `single_dataset_wave`: `7`
- quality bands:
  - `low`: `133`
  - `medium`: `27`
  - `high`: `0`

Dataset-specific damage:

- `CPIAUCSL` change-point cross-dataset episodes: `10 -> 7`
- `CSUSHPISA` change-point cross-dataset episodes: `7 -> 2`

This means the filter removed not only weak standalone monthly events, but also anomalies that were contributing to real cross-dataset episode formation.

## Conclusion

This experiment established an important system-level result:

- local anomaly quality does not equal global episode quality

The weak monthly anomalies were not always useless.
Some of them were acting as structural connectors inside the episode graph.

In graph terms:

- anomalies behave like nodes
- proximity and relationship evidence behave like edges
- clusters behave like connected components

Removing locally weak anomalies can therefore:

- remove nodes
- break edges
- split components

The practical implication is clear:

- local pre-clustering filtering is too blunt as the next step
- further threshold tuning is not the right frontier
- the next improvement should be structure-aware filtering or bridge-preserving logic, not a more aggressive local floor
