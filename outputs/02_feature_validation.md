# Feature Engineering & Causality Validation Report (Phase 2)
**Generated:** Phase 2 Feature Pipeline Implementation & Verification  
**Author:** Lead Quantitative Research Engineer  
**Scope:** Strict causal extraction of the 18 V21/V22 multi-regime features on ETHUSDT Futures.

---

## 1. Feature Set Definition & Mathematical Verification

All 18 features documented in `research/backtests/V22_ETH_Multi_Regime_Blind_Backtest_V22_2025-07-12_to_2025-08-01.md` (Section 4) and inherited from V21 (Section 17) have been implemented in `src/eth_research/features.py`.

### Feature Catalog
1. **Local Return Path:**
   - Feature 1: `(close - close[t-1]) / ATR7` (1-bar return normalized by ATR7)
   - Feature 2: `(close - close[t-3]) / ATR7` (3-bar return normalized by ATR7)
   - Feature 3: `(close - close[t-6]) / ATR7` (6-bar return normalized by ATR7)
   - Feature 4: `(close - close[t-12]) / ATR7` (12-bar return normalized by ATR7)
2. **Efficiency:**
   - Feature 5: `ER6` (Kaufman Efficiency Ratio over 6 bars)
   - Feature 6: `ER12` (Kaufman Efficiency Ratio over 12 bars)
   - Feature 7: `ER24` (Kaufman Efficiency Ratio over 24 bars)
3. **Candle Structure:**
   - Feature 8: `(close - open) / ATR7` (Current 15m candle body normalized by ATR7)
   - Feature 9: `(high - low) / ATR7` (Current 15m candle range normalized by ATR7)
4. **Local Volatility:**
   - Feature 10: `ATR7 / close` (Normalized local volatility)
   - Feature 11: `ATR7 / ATR28` (Volatility expansion / compression ratio)
5. **Trend & Value Structure:**
   - Feature 12: `(EMA9 - EMA21) / ATR7` (Fast vs medium moving average spread)
   - Feature 13: `(EMA21 - EMA21[t-4]) / ATR7` (EMA21 4-bar slope)
   - Feature 14: `(Mid32 - Mid32[t-8]) / ATR7` (32-bar midpoint migration over 8 bars)
   - Feature 15: `(close - Mid32) / ATR7` (Close distance from 32-bar value midpoint)
6. **Higher Timeframe Context (4H):**
   - Feature 16: `4H ER6` (Efficiency Ratio on completed 4H bars)
   - Feature 17: `(4H close - 4H EMA13) / 4H ATR14` (Macro trend displacement)
   - Feature 18: `4H ATR7 / 4H ATR28` (Macro volatility regime ratio)

---

## 2. Strict Causal Alignment & Anti-Leakage Rules

- **Zero Future Information in Input:** All features at bar $t$ use only candles $0 \le i \le t$.
- **4H HTF Synchronization:** Only 4H candles with `close_time <= candles_15m[t].close_time` are queried. Unclosed 4H bars are strictly excluded.
- **Target Label Isolation:** The label is strictly defined as `1 if next_candle.close > next_candle.open else 0` (horizon = 1 candle, i.e., $t+1$). Next candle prices are never passed into the feature matrix.
- **Warmup Boundary Enforced:** A minimum warmup of 100 15m bars and pre-warmed 4H data ensures no truncated or uninitialized indicator states pollute the feature space.
- **Sealed V23 Containment:** If any candle inside the processing series falls within `[1751662800000, 1752267599999]` (July 5–11, 2025 Europe/Istanbul), `SealedWindowViolationError` is instantly raised.

---

## 3. Unit Test Validation

All 21 unit tests across data ingestion, decision gating, and causal feature extraction pass cleanly:
```
Ran 21 tests in 0.028s
OK
```
Covered test suites:
- `test_atr_series`: Simple moving average of True Range.
- `test_ema_series`: Recursive exponential moving average with standard initialization.
- `test_er_series`: Absolute displacement divided by path length.
- `test_midpoint_32_series`: Rolling 32-bar high/low midpoint.
- `test_causality_and_no_future_leakage`: Feature extraction causal sequence and label alignment.
- `test_v23_sealed_gate_blocks_feature_extraction`: Rejection of sealed window candles.
