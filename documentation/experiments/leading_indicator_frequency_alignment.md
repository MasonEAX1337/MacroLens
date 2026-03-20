# Experiment

Leading Indicator Ranking With Frequency Alignment

## Goal

Determine whether the leading-indicator score should include an explicit frequency-alignment term so mixed-frequency pairs are discounted without being discarded.

## Methods Tested

- baseline score:
  - cluster coverage
  - average absolute correlation strength
  - sign consistency
- revised score:
  - cluster coverage
  - average absolute correlation strength
  - sign consistency
  - frequency alignment

Frequency alignment was defined conservatively:

- `1.00` for same-frequency pairs
- `0.85` for adjacent-frequency pairs:
  - daily to weekly
  - weekly to monthly
- `0.65` for wider gaps:
  - daily to monthly

The revised score gives frequency alignment a smaller weight than coverage, strength, or sign consistency.

## Dataset

Live MacroLens anomaly graph, with manual inspection focused on:

- Consumer Price Index
- Federal Funds Rate
- 30-Year Mortgage Rate
- Case-Shiller U.S. National Home Price Index
- Real Disposable Personal Income Per Capita

## Results

Observed live examples after inspection:

- CPI:
  - mortgage rates remained the top leader
  - the pair is `weekly -> monthly`, so it kept a mild discount rather than a severe penalty
  - daily leaders like S&P 500 and WTI remained visible but stayed below the mortgage-rate signal
- Federal Funds Rate:
  - monthly leaders such as CPI and real disposable income moved closer to mortgage rates
  - daily-to-monthly leaders no longer looked artificially comparable to repeated monthly leaders
- Real Disposable Personal Income Per Capita:
  - monthly leaders stayed ahead of the weekly mortgage-rate signal and the daily WTI signal
  - this matched the intended behavior because the score should prefer repeated same-frequency structure when the evidence quality is otherwise similar
- Mortgage Rate:
  - daily-to-weekly WTI remained strong because the relationship has full coverage and stable sign behavior
  - the alignment term reduced overconfidence slightly without burying the signal

## Conclusion

Frequency alignment should be included as a modest score component and visible UI field.

Reason:

- mixed-frequency relationships are not inherently wrong
- but the previous score treated a daily-to-monthly one-off too similarly to a repeated monthly-to-monthly relationship
- the right behavior is to discount wider frequency gaps, not ban them

The revised implementation therefore:

- adds `frequency_alignment`
- exposes the actual frequency pair in the UI
- applies a mild penalty for adjacent-frequency pairs
- applies a stronger penalty for daily-to-monthly pairs

This does not solve every ranking weakness. Low target-cluster counts can still make a leader look cleaner than it really is. But it makes the score more honest about temporal comparability.
