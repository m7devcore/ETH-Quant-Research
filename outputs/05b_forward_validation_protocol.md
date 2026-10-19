# Prospective Forward-Testing & Independent Validation Protocol
**Document:** `outputs/05b_forward_validation_protocol.md`  
**Purpose:** Preregistered Evaluation Protocol for Candidate Strategy `ETH-V22-D1`  
**Status:** **CORRECTED & FROZEN PROTOCOL — PREREGISTERED PRIOR TO TOUCHING EVALUATION WINDOW**  
**Author:** Lead Quantitative Research Engineer  
**Date:** Protocol Correction (Effective October 8, 2026)  

---

## 1. Protocol Correction & Forensics Notice

### Critical Flaw in Initial Draft (Identified & Corrected):
The initial draft of this document proposed an evaluation window spanning `2026-08-16` to `2026-09-12`.  
**This proposed window was fundamentally invalid on two fatal grounds:**
1. **Temporal Non-Prospective Violation:** As of current research operations (October 8, 2026), August–September 2026 is already in the past.
2. **Historical Report Overlap Contamination:** That window directly overlapped historical research reports already completed:
   - `V03`: August 1–22, 2026 (`research/backtests/V03_ETH_4H_15m_5m_Blind_Backtest_V3_2026-08-01_to_2026-08-22.md`)
   - `V02`: August 23 – September 13, 2026 (`research/backtests/V02_ETH_4H_15m_Blind_Backtest_2026-08-23_to_2026-09-13.md`)
   - `V01`: September 3–24, 2026 (`research/backtests/V01_ETH_4H_Backtest_Report_14D_vs_7D.md`)

Testing on that interval would have violated the core scientific mandate of AGENTS.md against evaluating on previously observed data. In accordance with strict quantitative governance, the window is formally replaced with a genuinely future, untouched prospective testing block.

---

## 2. Corrected Prospective Evaluation Window Definition

- **Target Prospective Evaluation Window:**
  - **Start Date:** `2026-10-12 00:00:00` Europe/Istanbul (`1791752400000` UTC ms)
  - **End Date:** `2026-11-08 23:59:59.999` Europe/Istanbul (`1794171599999` UTC ms)
  - **Duration:** Exactly **28 calendar days (4 full continuous weeks)**.
  - **Anticipated 15m Bars:** $28 \times 24 \times 4 = \mathbf{2,688\text{ candles}}$.
  - **Relationship to Current Time:** The start date (`2026-10-12`) is strictly in the future relative to the freeze date (October 8, 2026). Zero backdating.
- **Warmup Window Requirement:**
  - Preceding 100 15m bars and preceding 28 4H bars strictly prior to evaluation start (`1791752400000`) are used purely for causal indicator warmup. Zero labels, trade executions, or outcomes from the warmup window enter performance metrics.

---

## 3. Preregistered Acceptance & Rejection Criteria

To prevent post-hoc rationalization, the decision thresholds are locked prior to running the prospective evaluation:

### Primary Success Criteria (Strategy Accepted as Tradable Edge):
1. **Net Profitability After Full Costs:**
   Total Net PnL $> \mathbf{+3.00\%}$ across the 28-day window under standard taker frictions (12 bps round-trip).
2. **Net Expectancy per Executed Trade:**
   Average Net Return per Trade $\ge \mathbf{+0.0800\%}$ ($+8.0\text{ bps}$).
3. **Risk & Drawdown Containment:**
   Maximum Portfolio Drawdown $\le \mathbf{7.50\%}$ from equity peak.
4. **Profit Factor:**
   Net Profit Factor $\ge \mathbf{1.30}$.
5. **Sample Size Significance:**
   Executed trades $\ge \mathbf{60\text{ trades}}$ across the 28-day period (ensuring statistical relevance).

### Definitive Failure Criteria (Strategy Formally Rejected):
1. **Negative Net PnL:** Total Net PnL $< \mathbf{0.00\%}$ after modeled costs.
2. **Drawdown Breach:** Maximum Drawdown $> \mathbf{10.00\%}$ at any point.
3. **Severe Payoff Degradation:** Profit Factor $< \mathbf{1.00}$.

### Inconclusive Outcome & Statistical Uncertainty Handling:
- If executed trades $< \mathbf{60\text{ trades}}$:
  - If executed trades $< 30$, the test is declared **INCONCLUSIVE (INSUFFICIENT SAMPLE)** regardless of PnL, because the statistical power is too weak to distinguish skill from luck.
  - If executed trades are between 30 and 59 trades, 95% bootstrap confidence intervals for mean net return and win rate will be reported alongside aggregate figures. The strategy cannot be declared definitively accepted without a formal extension protocol.
  - **Anti-Overfitting Rule:** Under no circumstances will entry gates or thresholds be relaxed during or after the test to fabricate higher trade counts.

---

## 4. Friction & Stress Testing Requirements

The prospective evaluation will report metrics across three predefined execution environments:
1. **Baseline Standard Taker (12 bps):** Entry 0.05%, Exit 0.05%, Spread 0.01%, Slippage 0.01%.
2. **Conservative Taker (16 bps):** Entry 0.05%, Exit 0.05%, Spread 0.02%, Slippage 0.04%.
3. **High-Stress Execution (22 bps):** Entry 0.05%, Exit 0.05%, Spread 0.04%, Slippage 0.08% (simulating extreme volatility slippage).

---

## 5. Missing Data, Connectivity Disruption & Order Fill Rules

- **Causal Real-Time Evaluation Standard:**
  All forward evaluation signals must be generated strictly at candle close time $t$ from completed exchange candles, never retroactively after observing $t+1$ outcomes.
- **Handling Exchange Gaps & Disconnections:**
  1. A missing interval of $\le 2$ bars (30 min) will be causally forward-filled using the last completed close for indicator continuity, but **NO new trade can enter during the gap**.
  2. A missing interval of $> 2$ bars will trigger an automatic emergency exit of any active position (marked at last known close) and require a 100-bar clean warmup re-initialization.
  3. Every missing candle, API timeout, or rate-limit retry must be logged with timestamp, duration, and error payload in the execution audit log.
- **Independence from Chat Interfaces:**
  The paper-trading runner must execute as a headless, standalone Python process with autonomous disk logging, completely decoupled from active Gemini or Continue chat sessions.

