# ETH V1 → V21 Learning State
## V22 Research Architecture

V21 is now part of the research corpus.

Official V21 Hidden:
**45.45%**

The central learning after 21 versions:

1. Hand-built setup thresholds repeatedly fail across regimes.
2. Value migration alone is not sufficient.
3. Volatility alone is not sufficient.
4. Higher-timeframe direction alone is not sufficient.
5. Setup quality is not calibrated probability.
6. Internal chronological holdout inside one market regime is not enough.
7. Four-fold walk-forward inside one 14-day regime is also not enough.
8. Static models can inherit regime priors and fail on the next state.
9. Confidence thresholds can lose calibration after regime change.
10. Naive class balancing, intercept removal, OOD filtering and online gradient updates did not repair V21 Hidden.

## V22 main change

Stop using one 14-day Study period as the main training universe.

Use all already-seen V1–V21 data as research/training data.

Then validate using:
- leave-one-regime-out folds,
- period-balanced weighting,
- direction-balanced weighting,
- regime-conditioned experts.

Fresh untouched V22 Hidden remains the only final validation.

Suggested next block:
- Study/adaptation: 2025-07-12 → 2025-07-25
- Hidden: 2025-07-26 → 2025-08-01
