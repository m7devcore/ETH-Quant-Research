# Candidate Strategy Specification: ETH-V22-D1 (Dynamic ATR-Gated Exit)
**Document:** `outputs/05b_strategy_specification.md`  
**Candidate Designation:** `ETH-V22-D1`  
**Base Model:** Reconstructed V22-R Ensemble Checkpoint  
**Checkpoint SHA-256:** `fa367bd77adc597448ac7d163e6297986d365c2af93bbf0fc7226c992f7fea28`  
**Status:** **FROZEN SPECIFICATION — NO FURTHER TUNING PERMITTED PRIOR TO PROSPECTIVE VALIDATION**  
**Author:** Lead Quantitative Research Engineer  
**Date:** Phase 5B Deliverable  

---

## 1. Strategy Overview & Scientific Rationale

`ETH-V22-D1` is a research candidate designed to resolve the two primary failure modes of baseline V22-R:
1. **Frictional Erosion:** Instead of exiting after a single 15-minute bar (where gross moves average only 6.35 bps and are wiped out by 12 bps taker drag), the strategy allows profitable trades to expand up to a 1-hour maximum holding horizon (4 bars).
2. **Adverse Excursion Bleed:** Instead of passive time-based holding (which suffered when MAE > MFE), it introduces a **causal, volatility-anchored dynamic stop-loss** ($1.5 \times \text{ATR}_7$) and a **take-profit target** ($2.5 \times \text{ATR}_7$).

---

## 2. Frozen Parameter & Logic Specifications

### A. Directional Signal & Entry Gates (Causal, $t$ Decision Time)
- **Base Ensemble:** Three logistic experts ($A, B, C$) evaluated on completed 15m candle $t$.
- **Directional Edge Gate:**
  - $\text{Long (UP)} \iff p_{\text{avg}} \ge 0.5500$
  - $\text{Short (DOWN)} \iff p_{\text{avg}} \le 0.4500$
- **High-Consensus Spread Gate:** $\text{spread} = \max(p) - \min(p) \le \mathbf{0.0400}$ (tightened from baseline $0.06$).
- **Historical Support Gate:** $\min(\text{RMS Distance}) \le \mathbf{1.8000}$ (tightened from baseline $2.0$).
- **Volatility Tradeability Gate:** $\frac{\text{ATR}_7}{\text{Close}} \ge \mathbf{0.0018}$ ($0.18\%$ local volatility required to ensure potential price expansion exceeds transaction drag).
- **Abstention (`NO_TRADE`):** If any gate fails, no trade is generated.

### B. Execution Timing & Pricing (Strictly Causal)
- **Signal Confirmation:** Bar $t$ close (e.g., 12:15:00 UTC).
- **Position Entry:** Bar $t+1$ open (`next_open` at 12:15:00 UTC). Signal bar close price is never used as fill price.
- **Order Type:** Immediate taker entry and taker exit.

### C. Dynamic Exit Rules (Bar-by-Bar Resolution)
For an entered position with nominal entry price $P_{\text{entry}}$ and entry bar $\text{ATR}_7$:
- **Stop-Loss and Take-Profit Mechanics (Fixed at Entry):**
  - The Stop-Loss and Take-Profit price levels are **computed and fixed at position entry time** based on the entry candle's completed $\text{ATR}_7$. They are **not dynamically trailed** with subsequent bars. This preserves the documented design of `ETH-V22-D1` without introducing post-hoc trailing parameters.
  - **Stop-Loss Price ($P_{\text{SL}}$):**
    - For UP: $P_{\text{SL}} = P_{\text{entry}} - 1.50 \times \text{ATR}_7$
    - For DOWN: $P_{\text{SL}} = P_{\text{entry}} + 1.50 \times \text{ATR}_7$
  - **Take-Profit Price ($P_{\text{TP}}$):**
    - For UP: $P_{\text{TP}} = P_{\text{entry}} + 2.50 \times \text{ATR}_7$
    - For DOWN: $P_{\text{TP}} = P_{\text{entry}} - 2.50 \times \text{ATR}_7$
- **Expected Monetary Risk per Trade (Audited):**
  - Local ETH 15m $\text{ATR}_7$ averages approximately $0.18\% - 0.24\%$ of price (e.g., \$6.00 to \$8.00 at ETH = \$3,500).
  - A stop distance of $1.50 \times \text{ATR}_7$ corresponds to approximately $0.27\% - 0.36\%$ price distance.
  - On a fixed unleveraged position size of $\$10,000\text{ USD}$, the expected monetary loss per triggered stop-loss trade is:
    $$\text{Expected Max Loss} = \$10,000 \times (0.0027 \text{ to } 0.0036) + \text{Cost Drag } (\$12) \approx \mathbf{\$39 \text{ to } \$48 \text{ USD per trade}}$$
    representing an audited risk of approximately **0.39% to 0.48% of total portfolio equity** per trade.
- **Maximum Holding Horizon:** **4 bars (60 minutes)**. If neither SL nor TP is triggered during bars $1, 2, 3, 4$, the position is mandatorily closed at Bar 4 close price.
- **Intrabar Ambiguity Resolution Rule (Deterministic Conservative):**
  If in any single 15m candle the High touches $P_{\text{TP}}$ and the Low touches $P_{\text{SL}}$, **the stop-loss is conservatively assumed to have executed first**. Zero optimistic tie-breaking.

### D. Portfolio Capital & Risk Management
- **Account Model:** Single-position margin portfolio.
- **Fixed Starting Capital:** $\$10,000\text{ USD}$.
- **Position Size:** $\$10,000\text{ USD}$ (1.0x unleveraged, no phantom compounding).
- **Maximum Concurrent Positions:** **1 position maximum**. If a valid signal occurs while a position is already open, it is rejected with reason `REJECTED_PORTFOLIO_BUSY`.

### E. Standard Cost Model (Taker Frictions)
- Entry Fee: $0.0500\%$ ($5.0\text{ bps}$).
- Exit Fee: $0.0500\%$ ($5.0\text{ bps}$).
- Half-Spread: $0.0050\%$ ($0.5\text{ bps}$) on entry and exit.
- Execution Slippage: $0.0050\%$ ($0.5\text{ bps}$) on entry and exit.
- **Total Round-Trip Drag:** **0.1200% (12.0 basis points)**.

---

## 3. Immutable Reproducibility Metadata

- **Model Checkpoint File:** `artifacts/unverified/ETH_V22_Reconstruction_Audit_Model.UNVERIFIED.json`
- **Model Checkpoint SHA-256:** `fa367bd77adc597448ac7d163e6297986d365c2af93bbf0fc7226c992f7fea28`
- **Feature Engine:** `src/eth_research/features.py` (18 causal indicators with strict 4H completed-bar lookup).
- **Execution Simulator:** `src/eth_research/dynamic_portfolio.py` (`CausalDynamicPortfolioSimulator`).
- **All Parameters Frozen:** No parameter modification is permitted prior to independent prospective evaluation.
