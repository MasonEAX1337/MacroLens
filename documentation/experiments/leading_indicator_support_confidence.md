# Experiment

Leading Indicator Ranking With Absolute Support Confidence

## Goal

Determine whether the leading-indicator score should include an explicit absolute-support term so one-cluster leaders do not look as mature as repeated leaders with similar raw strength.

## Methods Tested

- baseline score:
  - cluster coverage
  - average absolute correlation strength
  - sign consistency
  - frequency alignment
- revised score:
  - cluster coverage
  - average absolute correlation strength
  - sign consistency
  - frequency alignment
  - support confidence

Support confidence was defined as a small stepwise heuristic based on the number of distinct supporting target clusters:

- `0.20` for `1` supporting cluster
- `0.55` for `2` supporting clusters
- `0.80` for `3` supporting clusters
- `1.00` for `4+` supporting clusters

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
  - mortgage rates remained the top leader because they still had repeated cluster support
  - one-cluster daily leaders such as S&P 500 and WTI were pushed down more visibly
- Mortgage Rate:
  - WTI remained strong because it has full cluster coverage and repeated support
  - S&P 500 dropped sharply because it only had one supporting cluster
- House Price Index:
  - every current leader is based on one supporting cluster
  - their scores now land in the same lower-confidence band instead of looking near-complete
- Federal Funds Rate and real disposable income:
  - repeated monthly and weekly leaders remained high because they had enough distinct supporting clusters to earn full support confidence

## Conclusion

Absolute support confidence should be part of the score and part of the UI.

Reason:

- cluster coverage alone is relative
- when target-cluster count is small, a one-cluster leader can still look artificially complete
- the ranking needs to express both:
  - how much of the target event graph is covered
  - how many distinct episodes actually produced that support

The revised implementation therefore:

- adds `support_confidence`
- surfaces it in the leading-indicator UI
- lowers the score of one-cluster leaders without removing them
- freezes the first version as a stepwise heuristic rather than continuing to fit a smoother curve on a still-small event corpus

This does not solve every case. A one-cluster leader can still rank highly if every other term is very strong. But it stops sparse leaders from looking fully mature by default.
