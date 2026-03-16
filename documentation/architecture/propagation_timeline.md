# Propagation Timeline

## Purpose

The propagation timeline connects one persisted macro-event cluster to later clusters that are supported by stored lagged evidence.

This matters because the product is no longer only asking:

- what happened here

It is also asking:

- what seems to have unfolded next

## Naming Boundary

The system intentionally avoids calling this a causal timeline.

Why:

- the current inputs are lagged correlations and later anomaly matches
- those inputs support sequencing and investigation
- they do not prove causal transmission

So the correct framing is:

- suggested propagation path
- downstream transmission path
- evidence-backed timeline

## Current Implementation

For the selected anomaly's cluster, the engine:

1. loads all anomalies in the source cluster
2. loads downstream correlations where `lag_days > 0`
3. computes the expected downstream timestamp for each relationship
4. searches later anomalies in the related dataset within a frequency-aware tolerance
5. groups matched anomalies by their target cluster
6. aggregates those matches into cluster-to-cluster edges
7. computes a conservative edge-strength score

The output is surfaced through anomaly detail rather than a separate endpoint.

## Current Edge Evidence

Each propagation edge currently includes:

- target cluster timing
- target anchor anomaly
- target dataset names
- average lag
- strongest stored correlation
- supporting link count
- a bounded list of evidence items linking source anomalies to target anomalies

## Current Scoring

The first edge-strength score is intentionally simple.

It currently combines:

- strongest correlation magnitude
- support density
- temporal alignment
- target cluster scale

This is useful for ranking, but it is not yet decomposed enough for scientific transparency.

## Current Strengths

- builds on persisted clusters instead of isolated anomalies
- gives the UI a real multi-event investigation surface
- keeps the product honest by focusing on downstream suggestions rather than causality claims

## Current Weaknesses

- only downstream links are modeled in the first pass
- only later anomaly matches are considered
- sparse or low-frequency datasets often produce no propagation edge at all
- the current score is not yet decomposed into visible subcomponents

## Best Next Step

Add explicit evidence-strength decomposition before making propagation logic more ambitious.
