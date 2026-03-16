# Decision

Add persisted anomaly clustering before building event-chain or leading-indicator features.

## Context

MacroLens already persisted anomalies as first-class events.

That was enough for single-event investigation, but it was not enough for the next level of product capability.

Features such as:

- event chains
- multi-dataset propagation views
- leading-indicator discovery

all need a larger unit than an isolated anomaly.

Without that intermediate unit, the system would jump too quickly from point events to causal-looking stories.

## Alternatives Considered

- build event chains directly on single anomalies
- keep clustering as a frontend-only grouping function
- add a full causal graph model immediately
- persist simple time-based event clusters first

## Reasoning

Building chains directly on single anomalies is too brittle.
It would overfit noisy point-to-point timing relationships.

Keeping clustering only in the frontend would make it presentation logic rather than system evidence.

A full causal graph model is premature and would imply a level of certainty the current evidence does not support.

The strongest current choice is:

- persist simple time-window clusters
- treat them as event envelopes
- build richer chain logic later on top of those envelopes

This creates a defensible intermediate layer between anomaly detection and causal interpretation.

## Consequences

- the database now stores anomaly clusters and cluster membership
- the ingestion pipeline now recomputes clusters after anomaly detection
- anomaly detail now includes cluster membership and nearby event context
- future chain and leading-indicator work can operate on clustered events rather than only isolated anomalies
- the current cluster semantics must remain clearly non-causal
