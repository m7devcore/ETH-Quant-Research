Activate `eth-research-cycle` and `eth-backtest-audit`. Continue from the existing versioned experiment registry, without modifying previous official results.

1. Show the latest verified results and open blockers, with exact source references.
2. Form ONE hypothesis based on a documented error, specify fixed train/adapt/holdout splits, primary metric, sample minimum, economic metrics and preregistered pass/fail thresholds.
3. Make a narrow code change and tests; run only allowed development data.
4. Freeze code/config/weights/scalers/hashes *before* fresh evaluation.
5. Evaluate untouched data once when the preregistration and provenance gate truly allow it; otherwise stop with a concrete blocker and continue safe reproducibility work.
6. Save a signed-off-style reproducible research report with ALL hits and misses, CI, day stability, MAE/MFE, costs assumptions and baselines; conclude ACCEPT / REJECT / INCONCLUSIVE.
7. Output what improved, what failed, and the next hypothesis without claiming guaranteed future profit. No real orders.

Arabic narrative; English code. Work in a finite, auditable cycle; never silently overfit a revealed test set.
