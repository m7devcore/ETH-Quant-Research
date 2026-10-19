# ETH Quant Research — permanent agent instructions

Goal: create a rigorously validated ETHUSDT Futures quantitative research engine and ultimately reusable Antigravity trading-analysis skills; not a self-justifying signal generator.

## Source of truth and honesty
- Treat `research/backtests/V01..V22` as immutable primary historical reports, not ground truth about future profitability.
- Treat the current V22 architecture in its report as frozen; `artifacts/unverified/*` is explicitly NOT the original V22 checkpoint.
- V23 preregistered period is `2025-07-05 00:00` through `2025-07-11 23:59:59`, Europe/Istanbul, with 672 15m bars anticipated; do not touch its labels or data until the authorized exact replication process has been satisfied and documented.
- A reconstructed V22 is a *new model family* until exact signal-by-signal parity with an original checkpoint or original predictions is verified. Close-looking aggregate accuracy does not establish identity.
- Never invent weights, original signal series, price history, costs, OOS outcomes, research results, timestamps, or citations. Label estimates as estimates.
- Preserve all failures and misses. Do not erase failed strategies, silently overwrite reports, or relabel old periods as "fresh".

## No lookahead / scientific method
- Every proposed experiment: explicit hypothesis, input dataset, feature specification, parameter set, version, commit/hash, train/adapt/eval split, expected acceptance criteria, and preregistration before evaluating held-out labels.
- Use only completed candles available at decision time. Native Binance 4H bucket alignment; timestamps stored in UTC milliseconds; Europe/Istanbul only for user-facing reports.
- Distinguish chronological holdouts, leave-one-regime-out validation, adaptation and truly fresh testing; avoid train/validation contamination and multiple-testing bias.
- No tuning on V23 or on a previously revealed Fresh result. Any post-reveal improvements are new research candidates, not an upgrade to the old official score.
- Report sample count, coverage, class balance, per-day & per-regime breakdown, confidence intervals, gross directional return, MFE/MAE, major tail losses and baselines.
- Distinguish direction classification from actual tradable expected value. For PnL simulation include commissions, spread, slippage, latency, funding if applicable, liquidation/margin constraints, and sizing.
- Every agent development cycle must leave reproducible code, tests, experiment config, logs, exact output paths, and a written decision. Prefer simpler model over cherry-picked high percentages.

## Safety and scope
- Default `research_only`. Never submit real trades, change exchange leverage or access private accounts/keys. No network calls to private endpoints, no order endpoints, no secrets in files.
- Never enable live execution without a **separate, explicit user authorization** after an audited paper-trading and risk review.
- Do not run uncontrolled open-ended experimental loops. Work in bounded research cycles with stop criteria and an audit trail.
- Cite the source report path + section/line for claims from historical documents. Resolve contradictions explicitly.

## Response
- Arabic explanations; code/comments/names may use English.
- Start every session with current phase, locked datasets, outstanding blockers, then next actionable implementation step.
- Prompt the user only when absolutely essential; otherwise implement the next safe research step and report actual test outcomes.
