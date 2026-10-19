# Protocol Correction & Window Invalidation Document (Phase 5B)
**Document:** `outputs/05b_protocol_correction.md`  
**Phase:** Phase 5B-Preparation — Strategy Freeze, Portfolio Integrity Audit, and Prospective Validation Design  
**Date of Correction:** October 8, 2026  
**Author:** Lead Quantitative Research Engineer  
**Status:** **OFFICIAL PROTOCOL REVISION — PRESERVES IMMUTABLE AUDIT TRAIL**  

---

## 1. Executive Summary & Statement of Invalidation

During the peer and governance review of the Phase 5B preparation deliverable, a critical scientific error was identified in the originally drafted forward-testing window:

- **Original Draft Window:** `2026-08-16 00:00:00` to `2026-09-12 23:59:59` Europe/Istanbul.
- **Reference Date Today:** **October 8, 2026**.

### Why the Original Window Was Scientifically Invalid:
1. **Temporal Non-Prospective Violation (Evaluating the Past as Future):**
   A prospective evaluation must, by mathematical and scientific definition, evaluate data generated *after* the strategy and its evaluation protocol are frozen. Proposing an August–September 2026 test on October 8, 2026 represents retrospective evaluation (backtesting), not prospective testing.
2. **Historical Backtest Report Contamination:**
   The interval August 16 to September 12, 2026 directly overlapped the periods of historical reports already executed and archived in the repository:
   - `research/backtests/V03_ETH_4H_15m_5m_Blind_Backtest_V3_2026-08-01_to_2026-08-22.md` (August 1 to 22, 2026)
   - `research/backtests/V02_ETH_4H_15m_Blind_Backtest_2026-08-23_to_2026-09-13.md` (August 23 to September 13, 2026)
   - `research/backtests/V01_ETH_4H_Backtest_Report_14D_vs_7D.md` (September 3 to 24, 2026)

Evaluating a candidate strategy on a time window whose market behavior, volatility, and price trajectory have already been analyzed in prior research reports introduces severe lookahead and selection bias.

---

## 2. Corrected Prospective Evaluation Window

In strict compliance with the core mandate of `AGENTS.md` ("Never backdate a preregistration"), the evaluation window is formally replaced with a genuinely future, untouched testing period:

| Dimension | Original Invalid Proposal | Corrected Preregistered Protocol |
|---|---|---|
| **Start Date** | `2026-08-16 00:00:00` (Past) | **`2026-10-12 00:00:00` Europe/Istanbul** (`1791752400000` UTC ms) |
| **End Date** | `2026-09-12 23:59:59` (Past) | **`2026-11-08 23:59:59.999` Europe/Istanbul** (`1794171599999` UTC ms) |
| **Duration** | 28 calendar days | **28 calendar days (4 continuous weeks)** |
| **Expected 15m Bars** | 2,688 bars | **2,688 contiguous 15m bars** |
| **Temporal Status** | **Contaminated / Past** | **Genuinely Future & Prospective (Starts 4 days after freeze)** |
| **Overlap with V01–V22** | **Severe Overlap with V01, V02, V03** | **Zero Overlap (Strictly Beyond All Repository Reports)** |
| **V23 Window Integrity** | Maintained Sealed | **Maintained Strictly Sealed (July 5–11, 2025)** |

---

## 3. Position Sizing & Monetary Risk Audit

To resolve any ambiguity regarding order mechanics in `ETH-V22-D1`:
- **Stop-Loss and Take-Profit Mechanics:** The stop ($1.5 \times \text{ATR}_7$) and target ($2.5 \times \text{ATR}_7$) are **computed once and fixed at position entry**. They are **not dynamically trailed** bar-by-bar. This strictly preserves the documented rule set.
- **Audited Monetary Risk per Trade:**
  - Standard ETH 15m $\text{ATR}_7$ is typically between $0.18\%$ and $0.24\%$ of price.
  - A stop-loss distance of $1.5 \times \text{ATR}_7$ equates to an adverse price move of approximately $0.27\%$ to $0.36\%$.
  - For a fixed $\$10,000\text{ USD}$ unleveraged position, maximum loss per stopped-out trade is:
    $$\text{Max Capital Loss} = \$10,000 \times (0.0027 \text{ to } 0.0036) + \text{Cost Drag } (\$12) \approx \mathbf{\$39 \text{ to } \$48 \text{ USD}}$$
  - This limits portfolio risk to roughly **0.39% to 0.48% of account equity per trade**.

---

## 4. Minimum Trade Count & Inconclusive Evidence Standard

The original protocol required $\ge 60$ executed trades over 28 days. The review raised the valid concern of what happens if trade frequency falls below this threshold due to strict gating:
- **Preregistered Inconclusive Standard:**
  - If executed trades $< 30$: The evaluation is classified as **INCONCLUSIVE (INSUFFICIENT STATISTICAL POWER)**. No claim of edge or failure is permitted.
  - If executed trades are between 30 and 59: Formal bootstrap confidence intervals (95% CI) will be calculated. A decision on system viability will require an explicit preregistered window extension.
  - **Zero Parameter Modification Rule:** Entry filters and gating criteria are completely frozen. Under no circumstances will thresholds be widened during the test to artificially inflate trade counts.

---

## 5. Architectural Independence & Continuous Operation

- The execution and portfolio verification engines (`src/eth_research/dynamic_portfolio.py` and `src/eth_research/execution.py`) are pure, standalone Python modules with zero dependency on Gemini, Continue, or active chat sessions.
- Data ingestion, feature calculation, gate evaluation, and trade logging can run in headless continuous environments using standard Python scheduling, outputting deterministic CSV trade ledgers to disk.
