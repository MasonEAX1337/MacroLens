# Experiment: Correlation Methods

## Goal

Identify the simplest useful method for finding related datasets around an anomaly.

## Methods Tested

- Pearson correlation on raw values
- Pearson correlation on percent changes
- lagged correlation across bounded day offsets

## Dataset

Initial target comparisons:

- Bitcoin vs S&P 500
- Oil vs CPI
- Federal funds rate vs S&P 500

## Results

- raw-value correlation is too easy to misread when scales and trends differ
- percent-change correlation is more defensible for market-style series
- lagged correlation is necessary because related datasets often move with delay

## Conclusion

Use bounded lagged Pearson correlation on transformed values for the MVP, with overlap minimums and explicit warnings against causal interpretation.
