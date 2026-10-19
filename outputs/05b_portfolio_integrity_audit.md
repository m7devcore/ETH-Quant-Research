# Portfolio Integrity & Concurrency Audit Report (Phase 5B)
**Document:** `outputs/05b_portfolio_integrity_audit.md`  
**Scope:** Forensic Audit of Phase 5A Multi-Horizon Returns and Portfolio Capital Accounting  
**Status:** **AUDIT COMPLETED — NUMERICAL DISCREPANCIES RECONCILED & DOCUMENTED**  
**Author:** Lead Quantitative Research Engineer  
**Date:** Phase 5B Execution  

---

## 1. Executive Summary & The Core Portfolio Audit Finding

In Phase 5A, multi-horizon holding evaluations reported large positive net returns in certain configurations (notably **+30.69% Net PnL** on the Adaptation dataset under a 2-hour holding horizon, and **+7.89%** under a 1-hour holding horizon).

### The Crucial Audit Verdict:
> **The +30.69% and +7.89% returns were NOT executable by a single portfolio with fixed capital ($10,000 USD).**  
> Those numbers were the **summed returns of individual, overlapping trades**, which implicitly assumed:
> 1. Unlimited capital expansion (concurrent execution of up to 4 or 5 simultaneous positions on the same asset).
> 2. Or unmodeled 4x–5x leverage with zero margin constraints and zero liquidation risk.

When evaluated as a **true single-position portfolio** (where capital is fixed at $10,000 USD, leverage is 1.0x unleveraged, and new signals are rejected if a prior position is already open):
- **Adaptation 2H Return collapses from +30.69% down to +4.71%** (a 25.98% drop).
- **Adaptation 1H Return drops from +7.89% down to +4.27%** (a 3.61% drop).
- **Fresh Test 2H Return improves from -15.96% to -5.68%** (because the single portfolio rejected 38 catastrophic overlapping losing trades).
- **Fresh Test 1H Return changes from -6.67% to -4.43%**.

---

## 2. Quantitative Overlap Audit Table

| Dataset & Horizon | Evaluated Signals | Max Concurrent Overlapping Positions | Summed Returns (Hypothetical Multi-Capital) | True Single Portfolio (Non-Overlapping, $10k Fixed) | Trade Count (Single Portfolio) | Capital Overlap Discrepancy |
|---|---|---|---|---|---|---|
| **Adaptation 2H (8 bars)** | 108 | **4 concurrent** | **+30.69%** | **+4.71%** | 58 trades | **-25.98%** (Severe Phantom Compounding) |
| **Adaptation 1H (4 bars)** | 108 | **3 concurrent** | **+7.89%** | **+4.27%** | 78 trades | **-3.61%** (Phantom Compounding) |
| **Fresh Test 2H (8 bars)** | 81 | **5 concurrent** | **-15.96%** | **-5.68%** | 43 trades | **+10.28%** (Phantom Compounding of Losses) |
| **Fresh Test 1H (4 bars)** | 81 | **4 concurrent** | **-6.67%** | **-4.43%** | 56 trades | **+2.24%** (Phantom Compounding of Losses) |

---

## 3. Root Cause Analysis: The Three Flaws of Summed Return Accounting

1. **Implicit Multi-Capital Allocation:**
   When a 15-minute signal stream triggers multiple entries within an open 1-hour or 2-hour window, summing returns assumes the trader deposits a fresh $10,000 for each new signal. During the Adaptation period, 4 trades ran concurrently at peak, requiring $40,000 of capital rather than $10,000.
2. **Hidden Leverage Risk:**
   If attempted within a fixed $10,000 margin account, entering 4 or 5 simultaneous positions constitutes 4x to 5x leverage. During high-volatility adverse swings (such as the 19.37% drawdown in Fresh Test), 5x leverage would have instantly liquidated the account.
3. **Double Counting of Market Moves:**
   Because 15m signals cluster during momentum regimes, overlapping trades were entering the same move at slightly different prices, counting the same market expansion 3 to 4 times.

---

## 4. Methodological Correction Implemented in Phase 5B

To guarantee absolute institutional portfolio integrity:
1. We designed and implemented `src/eth_research/dynamic_portfolio.py`, which enforces **Strict Single-Position Portfolio Integrity**:
   - Once a position is opened at `entry_time`, no other signal can be executed until the position reaches its dynamic exit (Stop-Loss, Take-Profit, or Max-Hold close).
   - Signals generated while the portfolio is occupied are strictly classified as `REJECTED_PORTFOLIO_BUSY` and logged with zero PnL.
2. Prior Phase 5A reports remain preserved without retroactive alteration; this audit document serves as the official scientific correction.
