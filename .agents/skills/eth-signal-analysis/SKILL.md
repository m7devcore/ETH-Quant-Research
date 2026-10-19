---
name: eth-signal-analysis
description: Explains the frozen V22 ETHUSDT next-15m UP/DOWN/NO TRADE classification and its three-expert agreement/distribution permission, using verified candle inputs without placing trades.
---
# ETH Signal Analysis

Use for traceable research/paper decisions, not execution.

Input: completed-bar-derived features in the exact 18-feature order, model identity and signed provenance, 3 expert probability outputs and distribution distances, UTC as-of timestamp. Never consume future information.

V22 policy: `p_avg = (pA+pB+pC)/3`; UP if `p_avg >= 0.55`, DOWN if `p_avg <= 0.45`, otherwise NO TRADE; require `max(p)-min(p) <= 0.06` and minimum normalized RMS distance <= 2.0; next single 15m candle only.

Output: timestamp, model_version, provenance status, pA/B/C, average, spread, distances, `UP|DOWN|NO_TRADE`, failed gates, as-of data time, and uncertainty. Do not call something a verified V22 prediction if the only available artifact is `UNVERIFIED`.

A classifier's confidence score is not a calibrated guaranteed success probability. Never transform an UP/DOWN label directly into a live order.
