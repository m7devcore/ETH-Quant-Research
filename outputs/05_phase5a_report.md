# Economic Edge Research & Multi-Horizon Strategy Report (Phase 5A)
**Document:** `outputs/05_phase5a_report.md`  
**Phase:** Phase 5A — Economic Edge Research and Multi-Horizon Strategy Development  
**Status:** **RESEARCH STAGE EVALUATION COMPLETED — V23 STRICTLY SEALED**  
**Author:** Lead Quantitative Research Engineer  
**Date:** Phase 5A Comprehensive Report  

---

## 1. Executive Summary & Verification of Phase 4 Audit (Task 1)

Before formulating or evaluating candidate strategies, a full independent audit of Phase 4 calculations was conducted:

### Audit Verification Findings:
1. **Gross and Net PnL Verification:**
   - The gross return per signal was independently verified: $\text{Gross Ret} = \frac{\text{next\_close} - \text{next\_open}}{\text{next\_open}} \times 100\%$ for UP signals (and inverse for DOWN).
   - Across the 81 signals of the Fresh Test control, the average gross return is exactly **+0.063494% (+6.35 bps)**, perfectly matching the original V22 reported figure (+0.0635%).
2. **Cost Decomposition of Scenario C (Maker Entry & Taker Exit):**
   - Maker entry fee: $0.0200\%$ ($2.0\text{ bps}$).
   - Taker exit fee: $0.0500\%$ ($5.0\text{ bps}$).
   - Half-spread: $0.0050\%$ on exit ($0.5\text{ bps}$).
   - Execution slippage: $0.0050\%$ on exit ($0.5\text{ bps}$).
   - Total round-trip frictional drag: **0.0900% (9.0 bps)**.
   - Net performance under Scenario C: Net Return per trade = $+0.0635\% - 0.0900\% = \mathbf{-0.0265\%}$. Total Net PnL = $\mathbf{-2.15\%}$ ($-214.70\text{ USD}$ on $10,000 capital).
3. **Causal Execution Pricing:**
   - Every evaluated trade enters strictly at `next_open` and exits at `next_close`. The signal-generating candle's closing price is never used as an execution fill price.
   - The trade ledger (`outputs/v22r_trade_ledger.csv`) accurately reflects these mechanics with zero numerical discrepancies.

---

## 2. Multi-Horizon Research Outcomes (Task 2)

We evaluated position holding horizons of **15 minutes (1 bar)**, **30 minutes (2 bars)**, **1 hour (4 bars)**, **2 hours (8 bars)**, and **4 hours (16 bars)** on the frozen V22-R signal stream across two distinct chronological research partitions:

### 1. Fresh Test Control Window (July 26 – August 1, 2025; 81 Signals)
- **15m:** Net PnL **-4.58%** | Win Rate 43.2% | Max DD 5.54% | Avg MFE 0.29% | Avg MAE 0.32%
- **30m:** Net PnL **-8.77%** | Win Rate 33.3% | Max DD 10.08% | Avg MFE 0.39% | Avg MAE 0.44%
- **1h:** Net PnL **-6.67%** | Win Rate 46.9% | Max DD 10.45% | Avg MFE 0.56% | Avg MAE 0.60%
- **2h:** Net PnL **-15.96%** | Win Rate 39.5% | Max DD 19.37% | Avg MFE 0.71% | Avg MAE 0.83%
- **4h:** Net PnL **-21.43%** | Win Rate 37.0% | Max DD 21.78% | Avg MFE 0.89% | Avg MAE 1.11%

### 2. Adaptation Research Partition (July 12 – July 25, 2025; 108 Signals)
- **15m:** Net PnL **-6.47%** | Win Rate 47.2% | Max DD 7.87% | Avg MFE 0.31% | Avg MAE 0.34%
- **30m:** Net PnL **+1.87%** | Win Rate 50.9% | Max DD 3.75% | Avg MFE 0.45% | Avg MAE 0.46%
- **1h:** Net PnL **+7.89%** | Win Rate 51.9% | Max DD 4.42% | Avg MFE 0.68% | Avg MAE 0.65%
- **2h:** Net PnL **+30.69%** | Win Rate 60.2% | Max DD 4.33% | Avg MFE 0.95% | Avg MAE 0.78%
- **4h:** Net PnL **+3.53%** | Win Rate 50.9% | Max DD 11.69% | Avg MFE 1.25% | Avg MAE 1.28%

### Core Scientific Findings:
1. **Regime Dependency:** In trending environments (Adaptation), longer holding captures momentum and overcomes trading fees. In choppy/mean-reverting environments (Fresh Test), holding longer amplifies losses and causes deep drawdowns (-15.96% to -21.43%).
2. **Persistent Excursion Asymmetry:** In almost every horizon, average MAE is greater than or equal to MFE. The directional signal does not possess tight timing precision; adverse movement precedes favorable moves.

---

## 3. Evaluation of Candidate Strategies (Task 3 & 4)

Ten concrete candidate variations were evaluated and registered in `outputs/05_strategy_candidate_registry.csv`:

1. **Candidate A (Holding Extensions):** REJECTED due to catastrophic failure during the Fresh Test control window.
2. **Candidate B (Higher-Timeframe 4H Trend Alignment):** REJECTED. Filtering signals by 4H trend halved the sample size (35 trades in Fresh, 53 in Adapt) but degraded net PnL (-3.36% and -5.80%) because many high-probability V22-R signals are short-term mean reversions against the 4H trend.
3. **Candidate C (High-Conviction Edge Filter):** INCONCLUSIVE / INSUFFICIENT SAMPLE. Filtering for extreme probabilities ($p \ge 0.57$ or $\le 0.43$) and tight consensus ($\text{spread} \le 0.04$) yielded a positive net PnL (+0.14%, 80% win rate), but produced only **5 trades in 7 days** in Fresh Test (and 13 in Adaptation). The sample size is too small to establish statistical significance.
4. **Candidate D & E (Volatility-Gated Tradeability & Purged Execution):** REJECTED. While volatility filtering improved gross capture during Adaptation (+4.27% net in purged 1H hold), it still produced negative net returns (-4.43% net) on Fresh Test.

---

## 4. The Portable Trading Analysis Skill Architecture (Task 5)

Implemented in `src/eth_research/candidates.py` and validated by 34 automated unit tests:
- `CandidateStrategyEngine` is completely decoupled from any specific LLM or execution environment.
- Returns structured `CandidateDecision` objects containing:
  - `policy_direction`: UP, DOWN, or NO_TRADE.
  - `tradeable`: Boolean tradeability flag.
  - `rejection_reason`: Explicit causal reason for abstention.
  - `suggested_holding_bars`: Recommended duration.
  - `model_probability` and `model_spread`.
  - `market_regime`: EXPANDING_VOL, NORMAL_VOL, COMPRESSED_VOL, COUNTER_TREND.
  - `estimated_cost_pct` and `expected_edge_pct`.

---

## 5. Answers to the Core Mandate Questions

### 1. Were Phase 4 calculations independently verified?
**Yes.** All gross and net PnL numbers, execution timestamps, cost deductions, and drawdowns from Phase 4 were independently recalculated directly from raw Binance data and confirmed with zero discrepancies.

### 2. Which horizons have the strongest research evidence?
**None of the fixed static horizons demonstrated robust cross-regime profitability.**
- 1-hour and 2-hour horizons showed strong evidence during trending periods (Adaptation), but suffered severe breakdowns during choppy periods (Fresh Test).
- Static time-based exits are structurally flawed; exits must be **dynamic and state-dependent** (e.g., volatility trailing stops, adverse excursion stops, or regime invalidation) rather than arbitrary candle counts.

### 3. Which candidate strategies deserve further testing?
**Candidate C (High-Conviction Edge Filter) and Candidate E (Dynamic Volatility Trailing Exits)** deserve further testing in future phases, provided they are evaluated over multi-month datasets to accumulate sufficient sample sizes.

### 4. Does any candidate have positive net expectancy in research data?
Across both historical periods simultaneously: **No.**  
Every candidate that was profitable in Adaptation turned negative in the Fresh Test control, proving that simple rule tweaks without retraining cannot rescue a narrow 6.35 bps gross edge from 12 bps taker frictions.

### 5. What remains unproven?
- Whether an ensemble retrained specifically on longer return targets (e.g., predicting 4-hour forward returns rather than 15-minute returns) can generate a gross edge of 50–100 bps.
- Whether dynamic stop-loss / take-profit mechanisms can truncate the heavy MAE tail.

### 6. The Exact Next Independent Validation Required
Before advancing, we must **preregister a completely untouched prospective validation window (e.g., a multi-month period in late 2026)** or initiate an audited paper-trading protocol. **V23 must remain sealed** until a model architecture with proven positive net expectancy is formally approved for final held-out replication.
