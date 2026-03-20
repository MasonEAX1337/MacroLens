# Experiment

Leading Indicator Ranking With vs Without Sign Consistency

## Goal

Determine whether the leading-indicator ranking should treat directional stability as explicit evidence instead of relying only on cluster coverage and absolute correlation strength.

## Methods Tested

- baseline score:
  - cluster coverage
  - average absolute correlation strength
- revised score:
  - cluster coverage
  - average absolute correlation strength
  - sign consistency

Sign consistency was defined as:

- the share of supporting clustered episodes that agreed on the dominant correlation sign

## Dataset

Live MacroLens anomaly graph, with manual inspection focused on:

- Consumer Price Index
- Federal Funds Rate
- 30-Year Mortgage Rate
- Case-Shiller U.S. National Home Price Index

## Results

Observed examples from the live graph:

- CPI:
  - mortgage rates led in 2 of 3 target clusters
  - sign split was 1 positive / 1 negative
  - this relationship looked too clean under the old score because its absolute correlation strength was very high despite directional inconsistency
- Federal Funds Rate:
  - mortgage rates and CPI both repeated often
  - both also showed mixed signs across episodes
  - the old score surfaced them strongly but hid the fact that their directional behavior was not stable
- Mortgage Rate:
  - WTI Oil Price led all 4 target clusters
  - sign split was 4 positive / 0 negative
  - this relationship remained strong under the revised score, which is the desired behavior

## Conclusion

Sign consistency should be part of the score and part of the UI.

Reason:

- repeated lead relationships with mixed signs are analytically weaker than equally repeated relationships with stable directional behavior
- hiding that instability inside one aggregate ranking made the feature look more confident than it was

The revised implementation therefore:

- adds `sign_consistency`
- adds `dominant_direction`
- incorporates sign consistency directly into the overall ranking

This does not solve every leading-indicator problem. Mixed-frequency relationships can still look stronger than they should. But it makes the ranking more honest and more inspectable.
