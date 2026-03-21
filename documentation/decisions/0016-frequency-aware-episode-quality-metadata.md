# Decision

Use frequency-aware anomaly clustering and persist first-pass episode-quality metadata in `anomaly_clusters`.

## Context

MacroLens had already grown beyond single-anomaly investigation.

Propagation, explanations, and leading-indicator discovery were all consuming persisted clusters, but the cluster model was still too thin:

- one global `7`-day gap rule
- no distinction between isolated signals and broader cross-dataset episodes
- no explicit metadata about frequency mix or episode breadth

That made downstream systems rely too heavily on local heuristics because the event unit itself was underdescribed.

## Alternatives Considered

### Keep the fixed global window and tune downstream scores harder

Rejected.

That would keep patching symptoms instead of improving the event model.

### Add a continuous cluster-quality score immediately

Rejected for now.

That would look more precise than the current event corpus supports.

### Build relationship-aware clustering immediately

Rejected for this pass.

That would be a larger algorithmic change and risk destabilizing the live evidence graph before the simpler event-quality improvements were in place.

## Reasoning

The irreducible problem was not that downstream views lacked one more heuristic.

The problem was that clusters were not expressive enough.

A conservative first pass needed to do two things:

1. let slower weekly and monthly datasets participate in broader episodes without widening the daily window globally
2. expose transparent metadata so downstream systems and users can tell what kind of episode they are looking at

So the clusterer now:

- keeps the existing daily base window
- expands weekly windows to `14` days
- expands monthly windows to `35` days
- uses conservative bridge windows for mixed-frequency pairs instead of always inheriting the widest side
- persists:
  - `span_days`
  - `frequency_mix`
  - `episode_kind`
  - `quality_band`

The labels are intentionally simple and inspectable:

- `episode_kind`
  - `isolated_signal`
  - `single_dataset_wave`
  - `cross_dataset_episode`
- `quality_band`
  - `low`
  - `medium`
  - `high`

This is a better first step than inventing another hidden downstream score term.

## Consequences

Positive:

- episode quality is now visible in the API and UI
- explanations can distinguish isolated events from broader episodes
- propagation and leading-indicator views can expose episode quality without pretending to prove causation
- slower datasets are less likely to collapse into one-point episodes by default
- mixed-frequency episode formation is less likely to over-group daily and monthly series across very wide gaps

Negative:

- the clusterer is still proximity-based and can still over-group mixed-frequency events
- `quality_band` is a transparent heuristic, not a formal confidence estimate
- live databases need the updated `schema.sql` re-applied so the new `anomaly_clusters` columns exist

Follow-up:

- evaluate whether mixed-frequency bridging needs to be less blunt
- decide whether low-quality episodes should directly down-weight downstream propagation or explanation framing
