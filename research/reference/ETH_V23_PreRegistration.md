# ETH V23 — Pre-registration and reproducibility audit

**Status:** NOT SCORED; test outcomes unopened.

## Frozen source of truth
- Model: V22, three logistic experts trained on the prior 18 Study regimes.
- Experts: A = V16–V21, B = V10–V15, C = V4–V9.
- Features: same 18 inputs specified in V22; target = next completed 15-minute ETHUSDT perpetual candle.
- Ensemble probability: (pA+pB+pC)/3.
- UP when >= 0.55; DOWN when <= 0.45; otherwise NO TRADE.
- Agreement: max(pA,pB,pC)-min(pA,pB,pC) <= 0.06.
- Distribution support: minimum normalized RMS distance to one expert's training distribution <= 2.0.
- No online learning, retraining, threshold optimization, day-specific exceptions, or modifications after accessing the test outcomes.

## V23 test-period choice (fixed before accessing test candles)
- ETHUSDT USDⓈ-M perpetual (Binance Futures).
- Local reporting clock: Europe/Istanbul (UTC+03:00).
- Period: **2025-07-05 00:00 to 2025-07-11 23:59:59 (Istanbul)**.
- Expected 15-minute candles: 7 x 24 x 4 = **672**.
- This period precedes the V22 adaptation window (July 12–25, 2025) and V22 fresh window (July 26–Aug 1, 2025); no test period in V4–V21 reports is dated in this interval.
- Use prior-to-test completed candles as indicator warmup, where necessary, but NEVER train or calibrate on V23 labels.

## Blocker to an exact untouched replication
The uploaded V22 report specifies the model family, feature names, optimizer settings, group partition, and decision thresholds, but does **not** retain its actual learned coefficient vectors and intercepts, each expert's mean/sd standardization statistics, nor the full source code needed to disambiguate feature definitions. They have not been found in the supplied training reports. Therefore any reimplementation from these documents would be a **reconstruction** of V22, not the exact frozen V22 model. It must not be called an official V23 replication without an independently verified equality check against original signal-level V22 decisions (aggregate percentage similarity is not sufficient).

## Control data source verified
Using Binance's historical ETHUSDT USDⓈ-M Futures 15m klines, V22 Fresh Test (2025-07-26 to 2025-08-01 Istanbul) reproduced the report's input-market data: 672 candles, open 3683.58, high 3940.81, low 3490.00, close 3539.90.

## Required official report after exact artifact recovery
For each 15m event, record timestamp, pA,pB,pC, averaged probability, spread, minimum distance, UP/DOWN/NO TRADE, next candle open/high/low/close, predicted-direction hit/miss, signed close return, MFE, MAE. Report the number of signals, total eligible candles, coverage, UP/DOWN breakdown, comparisons to always-UP and always-DOWN on the same signaled candles, accuracy, Wilson 95% interval, day-by-day distribution, worst individual misses, and results before costs. Only after the official score is sealed consider tail-risk or executable PnL follow-up. Preserve and publish every MISS.

## Integrity decision
V23 remains `PENDING_EXACT_MODEL_ARTIFACTS`, not `FAILED`, `PASSED`, or `NO_TRADE`. No actual V23 outcomes were read when this preregistration was written.

## Independent reconstruction attempt (audit only)
Using Binance historical candles, an independent implementation was fitted on the same eighteen V4–V21 Study-date blocks with the published settings (18 features, L2=0.20, 260 gradient steps, learning rate 0.04). For each of the three six-regime groups, this implementation found **7,458** labeled samples, rather than the reported **7,455 / 7,452 / 7,445**. The exact original feature-engineering code and stored scalers/weights were unavailable. This near-match does not establish reproducibility: there remain sample-boundary/preprocessing and optimizer ambiguity; **the re-fitted coefficients must not be substituted silently for the exact frozen V22 artifacts.** Control-signal output still requires comparison against the known V22 adaptation and fresh-test results. The untouched V23 dates have not been queried.

## Rebuild control check — outcome
The independent model (checkpoint separately saved) was tested on V22's *known* control windows, not on V23:

| Check | Original V22 | Independently re-built model |
|---|---:|---:|
| Adaptation signals | 159 | 175 |
| Adaptation hits | 95 | 105 |
| Adaptation accuracy | 59.75% | 60.00% |
| Fresh signals | 81 | 80 |
| Fresh hits | 48 | 48 |
| Fresh accuracy | 59.26% | 60.00% |
| Fresh UP signals | 41 | 41 |
| Fresh DOWN signals | 40 | 39 |

Independent rebuild used only 667 eligible 15m Fresh candles (one-day local warmup with 100-bar feature mask excludes first five); V22 counted the full 672. The Fresh result is remarkably close, but the discrepancy in Adaptation signal counts and missing control signals **prevents scientific identification of this rebuild with the original V22 model**. Neither the checkpoint nor its output may be represented as the official V22 weights. **Do not open the V23 test or issue an official V23 score on the basis of this reproduction.**
