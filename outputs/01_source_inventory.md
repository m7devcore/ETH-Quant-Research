# Quantitative Research Source Inventory & Integrity Audit
**Generated:** Phase 1 Bootstrap & Data Infrastructure Audit  
**Author:** Lead Quantitative Research Engineer  
**Scope:** ETHUSDT USD-M Perpetual (Binance Futures) Research Corpus (V01–V22, V23 Preregistration)

---

## 1. Overview & Verification Status

Every historical document from V01 through V22 is archived with frozen checksums in `SOURCE_MANIFEST.json`. These files serve as the primary immutable historical record of hypotheses, experiments, failures, regime shifts, and directional results.

### Key Architectural Baseline
- **V22 Multi-Regime Architecture:** 3 Logistic Experts trained on 18 Study Regimes (V04–V21), evaluated on 18 holdout regimes (59.24%), Adaptation (59.75%), and Fresh (59.26%).
- **Original V22 Model Artifacts:** **MISSING**. Frozen learned weights, intercepts, scaling vectors, and exact raw feature generation scripts were not archived in raw form.
- **Unverified Reconstruction (`artifacts/unverified/`):** Reconstructed independently with slight sample discrepancies (7,458 samples per group vs reported 7,455/7,452/7,445). **MUST NOT be represented as official V22.**
- **V23 Status:** **SEALED & UNSCORED**. Reserved strictly for an exact verified frozen V22 checkpoint. Any alternative model (including V22-R) requires a separately preregistered out-of-sample window and cannot unlock V23.

---

## 2. Inventory of Historical Backtests (V01 to V22)

All reports are located under `research/backtests/` and verified with SHA-256.

| Version | File Name | Study / Train Window | Hidden / Holdout Window | SHA-256 Checksum | Scientific Takeaway / Core Lesson |
|---|---|---|---|---|---|
| **V01** | `V01_ETH_4H_Backtest_Report_14D_vs_7D.md` | 14-day & 7-day comparative | Comparative 4H | `912b7d14...` | Invalidation rules; never defend a refuted fixed price thesis. |
| **V02** | `V02_ETH_4H_15m_Blind_Backtest_2026-08-23_to_2026-09-13.md` | Pre-Aug 2026 | 2026-08-23 to 2026-09-13 | `fa52397e...` | Regime classification before directional prediction; `NO_TRADE` validity. |
| **V03** | `V03_ETH_4H_15m_5m_Blind_Backtest_V3_2026-08-01_to_2026-08-22.md` | Pre-Aug 2026 | 2026-08-01 to 2026-08-22 | `2e28b211...` | Regime timeout and structural expiry; 5m is execution timing, not direction engine. |
| **V04** | `V04_ETH_1D_4H_15m_5m_Blind_Backtest_V4_2026-07-25_to_2026-08-14.md` | Prior 14D | 2026-07-25 to 2026-08-14 | `e8b26fdc...` | Early shock invalidates naive mean reversion; counter-candles insufficient. |
| **V05** | `V05_ETH_1D_4H_15m_5m_Blind_Backtest_V5_2026-07-04_to_2026-07-24.md` | Prior 14D | 2026-07-04 to 2026-07-24 | `fef32027...` | Failed acceptance is stronger evidence than visual wick rejection. |
| **V06** | `V06_ETH_1D_4H_15m_5m_Blind_Backtest_V6_2026-06-13_to_2026-07-03.md` | Prior 14D | 2026-06-13 to 2026-07-03 | `4218611d...` | Marginal trend strength cannot be treated as persistent momentum. |
| **V07** | `V07_ETH_1D_4H_15m_5m_Blind_Backtest_V7_2026-05-23_to_2026-06-12.md` | Prior 14D | 2026-05-23 to 2026-06-12 | `bd4c4d30...` | High win-rate on micro-samples is statistically fragile. |
| **V08** | `V08_ETH_1D_4H_15m_5m_Blind_Backtest_V8_2026-05-02_to_2026-05-22.md` | Prior 14D | 2026-05-02 to 2026-05-22 | `43664d74...` | Low Efficiency Ratio (ER) does not guarantee a safe mean-reverting range. |
| **V09** | `V09_ETH_1D_4H_15m_5m_Blind_Backtest_V9_2026-04-11_to_2026-05-01.md` | Prior 14D | 2026-04-11 to 2026-05-01 | `0129b2cb...` | Value/midpoint migration; avoid overfitting to single lucky thresholds. |
| **V10** | `V10_ETH_1D_4H_15m_5m_Blind_Backtest_V10_2026-03-21_to_2026-04-10.md` | Prior 14D | 2026-03-21 to 2026-04-10 | `979762c2...` | High displacement can represent repricing rather than exhaustion. |
| **V11** | `V11_ETH_1D_4H_15m_5m_Blind_Backtest_V11_2026-02-28_to_2026-03-20.md` | Prior 14D (87.5% Study) | 2026-02-28 to 2026-03-20 (54.5% Hidden) | `6061f887...` | Local pauses occur inside larger expansions; Study overfit exposed. |
| **V12** | `V12_ETH_1D_4H_15m_5m_Blind_Backtest_V12_2026-02-07_to_2026-02-27.md` | Prior 14D (66.0% Study) | 2026-02-07 to 2026-02-27 (50.0% Hidden) | `4bb75bf2...` | Failed breakout does not guarantee higher-timeframe rejection. |
| **V13** | `V13_ETH_1D_4H_15m_5m_Blind_Backtest_V13_2026-01-17_to_2026-02-06.md` | Prior 14D (80.0% Study) | 2026-01-17 to 2026-02-06 (36.4% Hidden) | `5f8057d4...` | Regime identification does not solve timing; catastrophic hidden collapse. |
| **V14** | `V14_ETH_1D_4H_15m_5m_Blind_Backtest_V14_2025-12-27_to_2026-01-16.md` | Prior 14D (75.0% Study) | 2025-12-27 to 2026-01-16 (36.4% Hidden) | `4fb6f247...` | Repeated boundary occupation alters the meaning of resistance/support. |
| **V15** | `V15_ETH_1D_4H_15m_5m_Blind_Backtest_V15_2025-12-06_to_2025-12-26.md` | Prior 14D (66.7% Study) | 2025-12-06 to 2025-12-26 (44.7% Hidden) | `390753c4...` | Stronger impulse does not guarantee continuation into next session. |
| **V16** | `V16_ETH_1D_4H_15m_5m_Blind_Backtest_V16_2025-11-15_to_2025-12-05.md` | Prior 14D (82.1% Study) | 2025-11-15 to 2025-12-05 (58.3% Hidden) | `cb9dfd69...` | Geometric retracement improves description but walk-forward degradation remains. |
| **V17** | `V17_ETH_1D_4H_15m_5m_Blind_Backtest_V17_2025-10-25_to_2025-11-14.md` | Prior 14D | 2025-10-25 to 2025-11-14 | `d0ce315d...` | Clean pullback efficiency; small sample caveat (9 trades). |
| **V18** | `V18_ETH_1D_4H_15m_5m_Blind_Backtest_V18_2025-10-04_to_2025-10-24.md` | Prior 14D | 2025-10-04 to 2025-10-24 | `bab09284...` | Three-layer filter (permission, quality, survival); micro-sample alert. |
| **V19** | `V19_ETH_1D_4H_15m_5m_Blind_Backtest_V19_2025-09-13_to_2025-10-03.md` | Prior 14D | 2025-09-13 to 2025-10-03 | `c74702da...` | Formalized separation of regime, setup, survival, and abstention. |
| **V20** | `V20_ETH_1D_4H_15m_5m_Blind_Backtest_V20_2025-08-23_to_2025-09-12.md` | Prior 14D (81.8% Study) | 2025-08-23 to 2025-09-12 (41.7% Hidden) | `3583f98d...` | Volatility filter alone failed to transport across shifts. |
| **V21** | `V21_ETH_1D_4H_15m_5m_Blind_Backtest_V21_2025-08-02_to_2025-08-22.md` | Prior 14D (60.7% Walk-fwd) | 2025-08-02 to 2025-08-22 (**45.45% Hidden**) | `e41c42ba...` | Single-regime collapse; accuracy equaled always-UP baseline (85/187). Single-regime fitting refuted. |
| **V22** | `V22_ETH_Multi_Regime_Blind_Backtest_V22_2025-07-12_to_2025-08-01.md` | 18 Study Regimes (V4–V21) | Adapt: 2025-07-12..25; Fresh: 2025-07-26..08-01 | `1596163a...` | Multi-regime 3-expert ensemble + consensus gate (spread <= 0.06) + support gate (dist <= 2.0). 59.26% Fresh. |

---

## 3. Preregistration: V23

- **Document:** `research/reference/ETH_V23_PreRegistration.md` (SHA-256: `af79a1c4...`)
- **Fixed Window:** `2025-07-05 00:00:00` to `2025-07-11 23:59:59` Europe/Istanbul (672 bars of 15m).
- **Rule of Engagement:** **PERMANENTLY SEALED** against arbitrary models. Only an exact, verified match of the frozen V22 artifacts can be scored on V23. Reconstructed models (V22-R) are prohibited from opening or scoring V23.

---

## 4. Known Data and Reproducibility Gaps

1. **Missing Original Parameters:** Exact frozen coefficient vectors, intercepts, and per-expert mean/std standardization vectors from the original V22 run are absent.
2. **Warmup & Sample Discrepancy:** The independent reconstruction obtained 7,458 labeled samples per group, compared to 7,455 (Group A), 7,452 (Group B), and 7,445 (Group C) in original V22. This divergence stems from candle boundary alignment and warmup bar exclusions.
3. **Execution Realism:** V22 achieved +0.0635% directional gross close return per signal, while MAE (0.3172%) exceeded MFE (0.2915%). Any real-world implementation requires factoring in exchange fee tiers, maker/taker slippage, and spread.
