# Economic Feasibility & Execution Realism Audit Report (Phase 4)
**Document:** `outputs/04_economic_feasibility.md`  
**Dataset Evaluated:** Known V22 Fresh Test Control Window (`2025-07-26 00:00:00` to `2025-08-01 23:59:59` Europe/Istanbul)  
**Sealed Window Status:** **V23 (`2025-07-05 00:00:00` to `2025-07-11 23:59:59` Europe/Istanbul) REMAINED FULLY SEALED & UNTOUCHED**  
**Author:** Lead Quantitative Research Engineer  
**Date:** Phase 4 Execution Deliverable  

---

## 1. Executive Summary & The Core Economic Question

### Is the Frozen V22-R Strategy Economically Profitable After Realistic Trading Costs?

> **THE SCIENTIFIC ANSWER IS: NO, NOT UNDER REALISTIC MARKET EXECUTION.**  
> While the directional classification model achieves a statistically respectable **59.26% gross win rate** (48 hits out of 81 signals), its average gross directional return is only **+0.0635% (6.35 basis points) per trade**.  
> The standard round-trip friction on Binance Futures (taker entry + taker exit fees of $0.05\% \times 2 = 0.10\%$, plus bid-ask spread of $0.01\%$ and modest execution slippage of $0.01\%$) totals **0.1200% (12.0 basis points)**.  
> Because the round-trip friction ($0.1200\%$) exceeds the gross directional edge ($0.0635\%$), the strategy generates a **negative expected value ($-5.65\text{ USD}$ per trade)** and ends in a net loss of **$-4.58\%$ ($-457.70\text{ USD}$)** across the 81 signals.

Only under an unrealistically optimistic, zero-friction maker-only scenario (0.02% maker in and maker out with 100% passive fills and zero adverse selection) does the strategy show a fragile net positive result ($+1.90\%$), which collapses immediately into negative territory as soon as a single taker exit is required.

---

## 2. Step 1: Input Verification & Return Mechanics

### Signal and Return Verification
- Total 15m evaluation bars: **672 candles** (exactly 7 calendar days).
- Inactive / Gate-filtered bars (`NO_TRADE`): **591 candles**.
- Active evaluated trades: **81 signals** (41 UP, 40 DOWN).
- **Execution Timing & Causality:**
  - Signals are generated at decision time $t$ using the completed candle's closing price.
  - Position entry occurs strictly at the opening of candle $t+1$ (`next_open`).
  - Empirical verification: Across all 81 signals, `next_open` differed from signal candle `close_price` by an average of only $+0.000056\%$ (maximum difference $0.00028\%$), confirming seamless contiguous exchange pricing without unmodeled gaps.
  - Position exit occurs strictly at the completion of candle $t+1$ (`next_close`).

### Investigation of Training Sample Accounting (7,458 vs Historical 7,455 / 7,452 / 7,445)
- In Step 1 of Phase 4, we verified that the 18 Study regimes each span exactly 14 calendar days ($14 \times 96 = 1,344$ 15m bars).
- With 100 bars of warmup and 1 bar lost to next-candle label boundary, the theoretical clean count is exactly $6 \times 1,243 = 7,458$ bars per expert.
- **Evidence-Based Finding:** We confirm that our data feed retrieved contiguous 15m bars. The slight historical difference in the original reports (3 bars in A, 6 bars in B, 13 bars in C) represents minor historical exchange gaps that the original ContiguousBarValidator dropped. This difference ($<0.1\%$) has zero impact on the economic conclusions.

---

## 3. Step 2 & 3: Execution Simulator & Cost Scenarios

We developed a fully portable, deterministic execution simulator in `src/eth_research/execution.py` adhering to strict causal accounting.

### Six Predefined Cost Scenarios (No Selective Cherry-Picking)

1. **Scenario A: Zero-Cost Theoretical Benchmark**
   - Maker fee: 0.0%, Taker fee: 0.0%, Spread: 0.0, Slippage: 0.0.
   - Purpose: Baseline theoretical ceiling reported in V22 research report.
2. **Scenario B: Maker Entry & Maker Exit (Optimistic Upper Bound)**
   - Entry fee: 0.02% (maker), Exit fee: 0.02% (maker), Spread: 0.0, Slippage: 0.0.
   - Assumes 100% limit fill at `next_open` and `next_close` with zero queue delay.
3. **Scenario C: Maker Entry & Taker Exit (Hybrid Execution)**
   - Entry fee: 0.02% (passive limit), Exit fee: 0.05% (market order on candle close).
   - Half-spread: 0.005% (0.5 bps), Slippage: 0.005% (0.5 bps). Total round-trip drag: 0.09%.
4. **Scenario D: Taker Entry & Taker Exit (Standard Realistic Frictions)**
   - Entry fee: 0.05% (taker), Exit fee: 0.05% (taker).
   - Half-spread: 0.005% (0.5 bps), Slippage: 0.005% (0.5 bps). Total round-trip drag: 0.12% (12 bps).
5. **Scenario E: Conservative Spread & Slippage (Adverse Liquidity)**
   - Entry fee: 0.05%, Exit fee: 0.05%.
   - Half-spread: 0.01% (1.0 bps), Slippage: 0.015% (1.5 bps). Total round-trip drag: 0.15% (15 bps).
6. **Scenario F: High-Cost & Latency Stress Test**
   - Entry fee: 0.05%, Exit fee: 0.05%.
   - Half-spread: 0.02% (2.0 bps), Slippage: 0.03% (3.0 bps). Total round-trip drag: 0.20% (20 bps).

---

## 4. Step 4: Comprehensive Economic Performance Comparison

### Master Performance Table (Fresh Test Control: 81 Signals, Initial Capital $10,000 USD)

| Scenario Name | Trades | Gross PnL (%) | Net PnL (%) | Net PnL ($) | Avg Net Return | Win Rate (%) | Profit Factor | Max Drawdown | Expected Value / Trade |
|---|---|---|---|---|---|---|---|---|---|
| **A. Zero-Cost Benchmark** | 81 | +5.14% | **+5.14%** | +$514.30 | +0.0635% | 59.26% | 1.65 | 1.29% | +$6.35 |
| **B. Maker / Maker (Optimistic)** | 81 | +5.14% | **+1.90%** | +$190.30 | +0.0235% | 53.09% | 1.20 | 1.69% | +$2.35 |
| **C. Maker / Taker (Hybrid)** | 81 | +5.14% | **-2.15%** | -$214.70 | -0.0265% | 45.68% | 0.81 | 3.72% | -$2.65 |
| **D. Taker / Taker (Standard)** | 81 | +5.14% | **-4.58%** | **-$457.70** | **-0.0565%** | **43.21%** | **0.64** | **5.54%** | **-$5.65** |
| **E. Conservative Spread/Slip** | 81 | +5.14% | **-7.01%** | -$700.70 | -0.0865% | 40.74% | 0.51 | 7.43% | -$8.65 |
| **F. High-Cost Stress Test** | 81 | +5.14% | **-11.06%** | -$1,105.70 | -0.1365% | 35.80% | 0.34 | 11.43% | -$13.65 |

### Breakeven Cost Benchmark
- **Gross Directional Edge:** **+0.0635% (6.35 bps)**.
- **Critical Breakeven Round-Trip Drag:** **0.0635%**.
- Any execution framework whose total round-trip cost (Fees + Spread + Slippage + Latency) exceeds **6.35 bps** is mathematically doomed to lose money over time.

---

## 5. Directional Breakdown & Adverse Excursion Analysis

### UP vs DOWN Performance Under Standard Taker Frictions (Scenario D)
- **UP Trades (Long):** 41 signals. Net PnL: **-0.83%**. Average net return: **-0.0202%**.
- **DOWN Trades (Short):** 40 signals. Net PnL: **-3.75%**. Average net return: **-0.0937%**.
- While UP trades were roughly near breakeven gross, DOWN trades suffered severe drag, generating net losses on 26 out of 40 trades.

### The MAE vs MFE Imbalance
- **Average Maximum Favorable Excursion (MFE):** **0.2915%**
- **Average Maximum Adverse Excursion (MAE):** **0.3172%**
- **Structural Vulnerability:** On average, during the 15-minute holding period, price retraced against the trade ($0.3172\%$) further than it traveled in favor of the trade ($0.2915\%$). This negative skew means that even winning trades experienced uncomfortable tail risk, and losing trades cut deeply.

### Top 5 Worst Losses (Preserved in Full — Scenario D)
1. **Trade #78 (UP):** Gross: $-0.7242\%$, Drag: $0.1200\%$, Net: **$-0.8442\%$**, MAE: $1.3652\%$.
2. **Trade #54 (DOWN):** Gross: $-0.6387\%$, Drag: $0.1200\%$, Net: **$-0.7587\%$**, MAE: $0.9864\%$.
3. **Trade #56 (UP):** Gross: $-0.5872\%$, Drag: $0.1200\%$, Net: **$-0.7072\%$**, MAE: $1.7768\%$.
4. **Trade #21 (DOWN):** Gross: $-0.4972\%$, Drag: $0.1200\%$, Net: **$-0.6172\%$**, MAE: $0.5322\%$.
5. **Trade #59 (DOWN):** Gross: $-0.4431\%$, Drag: $0.1200\%$, Net: **$-0.5631\%$**, MAE: $0.6345\%$.

---

## 6. Portable Skill Architecture (`eth_research/execution.py`)

The simulator is implemented strictly in clean, pure Python without dependencies on Gemini, Continue, or web frameworks:
- **`ExecutionConfig`:** Immutable dataclass for fee tiers, spread, slippage, latency, fill rate, and capital.
- **`TradeRecord`:** Immutable record capturing trade timing, prices, granular cost breakdown, excursions, net PnL, equity, and drawdown.
- **`ExecutionSimulator`:** Pure deterministic engine with zero side effects. Any AI agent or script can instantiate it, pass a signal stream, and receive a structured `SimulationSummary`.
- Complete trade ledger exported to **`outputs/v22r_trade_ledger.csv`**.

---

## 7. Answers to the Core Mandate Questions

### 1. Is the frozen V22-R strategy profitable after realistic costs?
**No.** Under realistic Binance taker execution (fees + spread + slippage = $0.12\%$), the strategy generates a net loss of **$-4.58\%$** with a Win Rate falling from $59.26\%$ to **$43.21\%$** and a Profit Factor of only **$0.64$**.

### 2. Under which assumptions would it be profitable?
It is profitable only under the **Maker/Maker scenario** ($+1.90\%$ net), which assumes:
- VIP fee tier with maker fee $\le 0.02\%$.
- $100\%$ limit order fill rate at the open without being front-run or suffering adverse selection.
- Passive limit exit at the close without crossing the spread.
In live trading, executing two passive maker fills within a single 15-minute candle with $100\%$ fill rate is virtually impossible.

### 3. How sensitive are conclusions to execution quality?
**Extremely sensitive.** The margin of edge is paper-thin ($0.0635\%$). A mere $0.02\%$ (2 basis points) increase in slippage or spread swings the strategy from a winning to a losing system.

### 4. What evidence is still missing?
- **Tick-level L2/L3 order book data:** To model realistic maker fill probabilities and queue position.
- **Dynamic slippage modeling:** Modeling liquidity depth during high-volatility 15m expansions.

### 5. Recommendation: Should we continue with this model, improve execution, or investigate alternative horizons?
**We should NOT deploy or trade this 15-minute 1-candle model.**
- Trying to capture a $0.0635\%$ edge over a single 15m candle is fighting an uphill battle against exchange fees.
- **Recommended Path:** In future preregistered research, investigate **multi-candle holding horizons (e.g., 1 hour, 4 hours, or trailing regime-based exits)** where gross expected moves are $0.50\% - 1.50\%$, easily absorbing the $0.10\% - 0.12\%$ exchange friction.
