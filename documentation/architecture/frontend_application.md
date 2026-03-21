# Frontend Application

## Purpose

The frontend is the investigation surface for the MacroLens evidence pipeline.

Its job is not to perform analysis. Its job is to make stored analysis inspectable.

## Current Interaction Model

The UI is organized around a simple loop:

1. choose dataset
2. inspect chart
3. identify anomaly marker
4. open event details
5. review cluster context, propagation timeline, correlations, cited news, and explanation
6. regenerate the explanation if the evidence or provider changes

This is intentionally narrow. It keeps the interface centered on event investigation rather than dashboard sprawl.

## Current Implementation

The frontend currently includes:

- dataset selector
- date-window controls
- anomaly severity and direction filters
- multi-dataset 3D constellation surface
- leading-indicator panel
- supporting-episode browser
- side-by-side supporting-episode comparison
- timeseries chart
- chart brush for local zooming
- anomaly markers on the chart
- recent anomaly list
- event detail panel
- macro-event cluster section
- explicit episode-kind, frequency-mix, and quality labels in cluster-facing surfaces
- propagation timeline section
- propagation score decomposition
- evidence provenance section
- cited news context section
- article timing badges
- correlation cards
- explanation cards
- explanation regeneration control

## Data Dependencies

The UI depends on:

- `GET /api/v1/datasets`
- `GET /api/v1/datasets/{id}/timeseries`
- `GET /api/v1/datasets/{id}/anomalies`
- `GET /api/v1/datasets/{id}/leading-indicators`
- `GET /api/v1/anomalies/{id}`
- `POST /api/v1/anomalies/{id}/regenerate-explanation`

This is a strong MVP boundary because it keeps the UI data contract small and event-centric.

The constellation view deliberately reuses the same endpoints rather than introducing a second API surface. It is a frontend composition of the existing dataset, timeseries, anomaly, and anomaly-detail contracts.

It is also lazy-loaded and chunked separately from the main application shell. That is necessary because the visual gain from Three.js is real, but so is the payload cost.

## Design Direction

The current visual language aims to avoid generic dashboard flatness.

It uses:

- strong headline hierarchy
- light atmospheric gradients
- glass-like cards
- clear separation between chart surface and evidence panel

The goal is not ornamental style. The goal is to make the system feel intentional.

## Current Strengths

- clear left-to-right investigation flow
- global multi-dataset view now exists without breaking the focused single-series investigation flow
- anomaly list and chart reinforce each other
- evidence panel is easy to scan
- frontend is wired to live backend data rather than placeholder content

## Current Weaknesses

- no selected-range summary around the brush interaction
- no loading skeletons
- no explicit raw evidence payload view
- the 3D constellation adds a meaningful visual layer, but it also increases bundle size and needs performance discipline
- episode-quality labels are now visible, but the UI still does not show why a mixed-frequency episode was grouped the way it was

## Next Improvements

### Highest-value

- selected-range summary tied to the chart brush
- richer comparison semantics inside the constellation view
- explicit raw evidence payload view
- stronger explanation of why a cluster was labeled low, medium, or high quality

### Second-order improvements

- richer comparison mode between datasets
- explanation history comparison across providers
- propagation graph expansion beyond one click-ahead step

## Design Standard

The frontend should remain an analysis instrument, not a decorative shell.

Every additional interaction should make the evidence easier to interrogate.
