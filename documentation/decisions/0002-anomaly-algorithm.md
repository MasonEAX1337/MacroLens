# ADR 0002: Initial Anomaly Algorithm

## Decision

Use rolling z-score detection as the first anomaly detection algorithm.

## Context

The MVP needs a detection method that is understandable, quick to implement, and good enough to surface major economic events.

## Alternatives Considered

- moving-average deviation
- change point detection
- volatility-regime detection

## Reasoning

- z-score detection is simple and explainable
- it performs well on obvious spikes and crashes
- more advanced methods increase complexity before the data pipeline is proven

## Consequences

- some false positives are expected on seasonal or trending data
- the API and documentation must make the detection method visible
- future versions may need dataset-specific detection strategies
