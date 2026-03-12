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
5. review correlations and explanation

This is intentionally narrow. It keeps the interface centered on event investigation rather than dashboard sprawl.

## Current Implementation

The frontend currently includes:

- dataset selector
- timeseries chart
- anomaly markers on the chart
- recent anomaly list
- event detail panel
- correlation cards
- explanation cards

## Data Dependencies

The UI depends on:

- `GET /api/v1/datasets`
- `GET /api/v1/datasets/{id}/timeseries`
- `GET /api/v1/datasets/{id}/anomalies`
- `GET /api/v1/anomalies/{id}`

This is a strong MVP boundary because it keeps the UI data contract small and event-centric.

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
- anomaly list and chart reinforce each other
- evidence panel is easy to scan
- frontend is wired to live backend data rather than placeholder content

## Current Weaknesses

- no zooming or brush control
- no anomaly filtering
- no loading skeletons
- no explanation regeneration control
- no explicit raw evidence view

## Next Improvements

### Highest-value

- chart zoom and range selection
- anomaly severity filtering
- better visual distinction between positive and negative anomaly types
- evidence provenance section in the detail panel

### Second-order improvements

- comparison mode between datasets
- explanation refresh button
- anomaly clustering view

## Design Standard

The frontend should remain an analysis instrument, not a decorative shell.

Every additional interaction should make the evidence easier to interrogate.
