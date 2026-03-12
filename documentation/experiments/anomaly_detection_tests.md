# Experiment: Anomaly Detection Tests

## Goal

Determine which anomaly detection method is the best first choice for the MVP.

## Methods Tested

- rolling z-score detection
- rolling moving-average deviation

## Dataset

Bitcoin price history is the initial benchmark because it contains obvious spikes and crashes.

## Results

- z-score detection captures sharp crash and spike behavior well
- moving-average deviation is easier to tune badly and can blur discrete event boundaries
- both methods can misfire on trending or highly volatile segments

## Conclusion

Use rolling z-score detection for the MVP because it is simple, explainable, and sufficient for early event discovery.

Future work should test change point detection on slower regime shifts.
