# Event Clustering

## Purpose

Event clustering turns isolated anomaly records into macro-event envelopes.

This matters because economic events rarely manifest as one point in one series.
They usually appear as nearby anomalies across time, and sometimes across multiple datasets.

## Current Role in the Pipeline

The current sequence is:

1. ingest and normalize source data
2. detect anomalies per dataset
3. cluster nearby anomalies into persisted event groups
4. compute lag-aware correlations
5. retrieve contextual evidence
6. generate explanations

Clustering sits between anomaly detection and downstream interpretation.

## First-Principles Design

The system needs a unit larger than a single anomaly but smaller than a fully inferred causal story.

That unit is the cluster.

A cluster is not a causal graph.
It is a bounded event envelope that says:

- these anomalies happened close enough in time to be investigated together

That is a much safer claim than:

- these anomalies caused each other

## Current Implementation

The current implementation is still deliberately conservative, but it is no longer purely global-window based:

- sort anomalies by timestamp
- compute a frequency-aware gap allowance between adjacent anomalies
- group adjacent anomalies when the gap stays inside that pair-specific allowance
- for wider cross-dataset merges, require an existing stored relationship between the incoming dataset and at least one dataset already inside the cluster
- persist cluster summaries and anomaly-to-cluster membership
- persist basic episode-quality labels for downstream consumers

Current persisted fields include:

- cluster start timestamp
- cluster end timestamp
- anchor timestamp
- span days
- anomaly count
- dataset count
- peak severity score
- frequency mix
- episode kind
- quality band

The default daily base window is `7` days.

Current same-frequency windows are:

- daily: `7` days
- weekly: `14` days
- monthly: `35` days

Mixed-frequency pairs now use a more conservative bridge window instead of simply inheriting the widest side:

- daily to weekly: `10` days
- weekly to monthly: `22` days
- daily to monthly: `16` days

The relationship-aware gate is intentionally narrow:

- same-dataset waves still merge on proximity alone
- cross-dataset anomalies that land inside the base daily window still merge on proximity alone
- cross-dataset anomalies that only qualify because of a wider weekly/monthly bridge must also have a pre-existing stored correlation relationship

This prevents the wider mixed-frequency windows from manufacturing broad episodes out of weakly related monthly points.

The clusterer now also owns a narrow episode-filter responsibility for transformed monthly change-point anomalies in `CPIAUCSL` and `CSUSHPISA`:

- first build provisional clusters from the full anomaly set
- then suppress only weak monthly target anomalies that remain isolated or single-dataset
- preserve weak monthly anomalies if they participate in a provisional cross-dataset episode
- rebuild final clusters from the retained candidates

This is intentionally bridge-preserving.
It keeps weak connector anomalies alive long enough for the graph to show whether they matter.

Operationally, this also means stored-data refresh order matters.

The current refresh script now reclusters after correlation rebuild when both stages run together.
That second pass is not redundant. It lets the relationship-aware gate and bridge-preserving suppression see current relationship evidence rather than stale pre-refresh correlations.

## Why This Was Chosen

- simple to reason about
- easy to persist and test
- compatible with the current anomaly model
- gives the UI a real event layer without claiming more than the data supports

## Current Strengths

- turns the product into more than a point-event viewer
- creates a clean substrate for propagation and leading-indicator views
- gives slower weekly and monthly series a more realistic chance of forming multi-event episodes
- keeps slower mixed-frequency episodes possible without letting every nearby monthly anomaly collapse into a broad macro episode
- makes sparse isolated events explicit instead of letting them masquerade as broad macro episodes

## Current Weaknesses

- clustering is still fundamentally proximity based rather than relationship aware
- the relationship-aware rule still depends on already-stored correlations, so a good new episode can be split if historical relationship evidence is missing
- mixed-frequency clusters are less blunt than the first frequency-aware pass, but they are still proximity-based and can still over-group weakly related slow and fast series
- local anomaly cleanup can still damage the episode graph, because a weak-looking anomaly may function as a bridge node between otherwise separate cross-dataset events
- quality labels are intentionally simple and should be read as investigation cues, not formal confidence estimates

## Why This Is Still Worth Having

Even imperfect clustering is better than forcing users to reason from isolated anomalies only.

The important boundary is honesty:

- clusters define investigation scope
- they do not prove shared causation

## Current Episode Labels

The clusterer now persists three fields that matter downstream:

- `frequency_mix`
  - `daily_only`
  - `weekly_only`
  - `monthly_only`
  - `mixed`
- `episode_kind`
  - `isolated_signal`
  - `single_dataset_wave`
  - `cross_dataset_episode`
- `quality_band`
  - `low`
  - `medium`
  - `high`

These labels are intentionally transparent.
They are not trying to predict causality.
They are trying to tell the investigator what kind of event envelope the system believes it is looking at.

## Best Next Step

The next quality step is still deeper episode quality, but now the obvious blind spot is the cold-start case:

- inspect whether good cross-dataset episodes are being split because the relationship-aware gate depends on historical correlation coverage
- inspect whether the current bridge-preserving suppression still leaves too many weak monthly isolates in the graph
- decide whether the next improvement should be a small correlation-aware fallback or a richer episode-quality audit, not another broad threshold change
