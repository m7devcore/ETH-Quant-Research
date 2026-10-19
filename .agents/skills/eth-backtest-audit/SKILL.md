---
name: eth-backtest-audit
description: Audits Binance ETHUSDT perpetual backtests for lookahead, wrong candle alignment, regime contamination, original-model parity, unexplained sample count differences, and unrealistic trading-cost assumptions.
---
# ETH Backtest Audit

## Workflow
1. Inspect timezones and Binance native 4H open buckets. Enforce sorted UTC millisecond timestamps and one unique bar per period.
2. Verify 15m and 4H bar counts, gaps and OHLC consistency, and warmup selection. Never expose an incomplete candle as an input.
3. Compute features with causal rolling calculations; split train/adapt/holdout before fitting scalers.
4. Crosscheck 18 feature order, formula, label mapping, sample boundaries, normalization, optimizer and parameters.
5. Compare on the **known V22 controls**: original Adaptation 95/159, Fresh 48/81, and if recovered, every timestamped signal. Close totals do not equal parity.
6. Mark every checkpoint as VERIFIED_ORIGINAL, RECONSTRUCTED_UNVERIFIED or REJECTED. Do not silently rename.
7. Export checksums, exact reproducer commands, divergence report, baselines, Wilson intervals, fee assumptions and all misses.
8. Leave V23 5–11 Jul 2025 inaccessible until `docs/RESEARCH_PROTOCOL.md` conditions are met.

A missing original checkpoint is a blocker to **exact** replication, not permission to fabricate it.
