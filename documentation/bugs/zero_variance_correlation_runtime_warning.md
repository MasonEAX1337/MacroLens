# Bug: Zero-Variance Correlation Runtime Warning

## Cause

The correlation engine computes Pearson correlation on percent-change windows after aligning two datasets across lag candidates.

For some overlaps, one side becomes constant after percent-change transformation.

Example shape:

- base returns: `0, 0, 0, 0, 0`
- related returns: varying values

That overlap has zero variance on one side, which makes Pearson correlation undefined.

Before the fix, the engine still called `Series.corr()`, which delegated into NumPy and emitted:

- `RuntimeWarning: invalid value encountered in divide`

Pandas then returned `NaN`, which the engine skipped afterward.

So the system was functionally surviving the case, but only after triggering a numerical warning.

## Fix

Added an explicit zero-variance guard inside `compute_best_lag_correlation`.

The engine now skips an overlap before attempting correlation when either merged return series has fewer than two distinct values.

This keeps the behavior explicit:

- undefined correlation is rejected as invalid input
- NumPy is never asked to divide by zero variance in the first place

## Result

- the warning path is removed by design
- constant overlap windows now return no correlation candidate cleanly
- regression coverage was added so constant-window inputs remain warning-free
