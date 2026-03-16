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

The current implementation is deliberately simple:

- sort anomalies by timestamp
- group adjacent anomalies when the gap between consecutive anomalies is at most the configured window
- persist cluster summaries and anomaly-to-cluster membership

Current persisted fields include:

- cluster start timestamp
- cluster end timestamp
- anchor timestamp
- anomaly count
- dataset count
- peak severity score

The default clustering window is `7` days.

## Why This Was Chosen

- simple to reason about
- easy to persist and test
- compatible with the current anomaly model
- gives the UI a real event layer without claiming more than the data supports

## Current Strengths

- turns the product into more than a point-event viewer
- creates a clean substrate for future event-chain views
- makes dense anomaly periods easier to inspect

## Current Weaknesses

- clustering is based on time proximity only
- a cluster can still contain weakly related anomalies
- sparse household and monthly series often collapse to single-anomaly clusters
- the current method does not distinguish local noise from true systemic episodes

## Why This Is Still Worth Having

Even imperfect clustering is better than forcing users to reason from isolated anomalies only.

The important boundary is honesty:

- clusters define investigation scope
- they do not prove shared causation

## Best Next Step

The next quality step is not more chain breadth.
It is better chain trust:

- decompose propagation edge strength
- make weak links easier to reject
- keep the cluster-to-causality boundary explicit
