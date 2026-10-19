# Research protocol — versioning and verification

1. **Inventory**: verify checksum of all source files and expected V01..V22 coverage. Do not edit source reports.
2. **Data pipeline**: fetch public Binance ETHUSDT USDⓈ-M perpetual OHLCV for 15m and 4H; derive 1D/5m for context as useful. Store immutable raw UTC bars, source request, checksum, completeness/gap report and reproducible environment.
3. **Feature specification**: reimplement the 18 V22 features exactly when source permits, using only fully completed bars. Create unit tests for ATR, EMA, ER, 32-bar midpoint migration, 4H alignment, timestamps, target shift and warmup boundaries.
4. **V22 known controls**: recreate 18 Study regime group data, count labeled samples; compare recorded 7455/7452/7445 vs independent 7458/7458/7458. Explain all differences. With original weights, do signal-by-signal comparison on V22 Adaptation and Fresh; if no originals, explicitly mark reimplementation distinct and do NOT certify V22 exact.
5. **V23 gate**: ONLY after exact equivalence established and freeze manifest signed/logged, test V23 once with no tuning; score fully. If original V22 is impossible to recover, declare V22-R a **new preregistered candidate** with separate naming and decision on untouched test use. Do not present it as V23 official.
6. **After official test**: preserve frozen metrics and errors; analyze day failure clusters and adverse tails; pre-register modifications for another untouched future period.
7. **Execution feasibility**: only after repeated clean OOS tests, evaluate fees, spread, slippage, funding, latency, position sizing, stop/TP, adverse excursions, drawdown, liquidation and paper trading. A 59% hit rate alone proves no profitability.

## Required metrics
N eligible bars, selected signals, coverage, UP/DOWN counts and hit rates, overall hits/misses, Wilson 95% CI, always-UP and always-DOWN on the *same selected bars*, signed next-close returns, MFE/MAE distributions, worst losses, day/regime breakdown, turnover, measured or assumed costs clearly labeled, net simulated PnL, drawdown and sensitivity.

## Standard output per signal
`timestamp_utc, bar_close_utc, expert_A_p, expert_B_p, expert_C_p, p_avg, spread, min_distance, predicted_class, next_open, next_high, next_low, next_close, correct, signed_return_pct, mfe_pct, mae_pct`.

## No leakage checklist
- Group splits are date-exclusive as specified (Study/Adaptation/Fresh).
- Scaler fitted only on the training group for its expert.
- Feature values computed with closed candles at decision time.
- Future open/high/low/close are labels/metrics only, not input features.
- No optimization using the result of a held-out test; one official score per frozen version.
- No pair-specific after-the-fact omission of losing days.
- Keep raw dataset version, code commit and random seeds in each experiment manifest.
