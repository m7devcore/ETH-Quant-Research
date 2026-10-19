# ETH-Quant-Research Architecture & Technical Specification

## 1. Executive System Architecture

`ETH-Quant-Research` is a modular, zero-lookahead quantitative research and paper-trading engine designed for high-frequency directional modeling of ETHUSDT Binance USD-M Perpetual Futures.

The system is strictly layered into six isolated modules:

```text
[ Binance Public API ]
          │
          ▼
┌──────────────────────────────────────────────┐
│  1. Data Ingestion & Validation (data.py)    │
│  - OHLCV candlestick causality               │
│  - Gap, overlap, & duplicate detection       │
│  - V23 Sealed Window Containment Barrier     │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  2. Causal Feature Extraction (features.py)  │
│  - 18 multi-scale technical indicators       │
│  - Multi-timeframe alignment (15m + 4H)      │
│  - Normalization without future lookahead    │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  3. Model Ensemble & Gating (model / policy) │
│  - 3 Logistic Regression Experts (A, B, C)   │
│  - Tripartite Consensus & Spread Filter      │
│  - RMS Distance to historical clusters       │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  4. Dynamic Portfolio & Risk (portfolio.py)  │
│  - Entry-anchored ATR dynamic stop & target  │
│  - Single active position constraint         │
│  - Realistic institutional friction (0.12%)  │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  5. ACID State Persistence (persistence.py)  │
│  - SQLite with WAL (Write-Ahead Logging)     │
│  - Transactional trade lifecycle logging     │
│  - Complete event audit ledger               │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  6. Operational Runner & CLI (runner.py)     │
│  - `--check` diagnostic health verification  │
│  - `--run-once` automated polling loop       │
│  - Safety lock: research_only = True         │
└──────────────────────────────────────────────┘
```

---

## 2. Mathematical Formulations

### 2.1 The 18 Causal Feature Set

Features are extracted strictly using completed candles. Let $t$ denote the current completed 15m candle index, with closing price $C_t$, high $H_t$, low $L_t$, and volume $V_t$.

1. **True Range & Average True Range (ATR):**
   $$\text{TR}_t = \max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)$$
   $$\text{ATR}_n(t) = \frac{1}{n} \sum_{i=0}^{n-1} \text{TR}_{t-i}$$
   - Normalized ATR features: $F_1 = \frac{\text{ATR}_7(t)}{C_t}$, $F_2 = \frac{\text{ATR}_{14}(t)}{C_t}$, $F_3 = \frac{\text{ATR}_{28}(t)}{C_t}$.

2. **Kaufman Efficiency Ratio (ER):**
   Measures directional price efficiency against cumulative path volatility:
   $$\text{ER}_n(t) = \frac{|C_t - C_{t-n}|}{\sum_{i=0}^{n-1} |C_{t-i} - C_{t-i-1}|}$$
   - Features: $F_4 = \text{ER}_{10}(t)$, $F_5 = \text{ER}_{20}(t)$, $F_6 = \text{ER}_{30}(t)$.

3. **Exponential Moving Average Spreads:**
   $$\text{EMA}_\alpha(t) = \alpha C_t + (1 - \alpha)\text{EMA}_\alpha(t-1), \quad \alpha = \frac{2}{k+1}$$
   - Features represent normalized distance from short to medium and long EMAs:
     - $F_7 = \frac{C_t - \text{EMA}_8(t)}{\text{ATR}_7(t)}$
     - $F_8 = \frac{\text{EMA}_8(t) - \text{EMA}_{21}(t)}{\text{ATR}_{14}(t)}$
     - $F_9 = \frac{\text{EMA}_{21}(t) - \text{EMA}_{55}(t)}{\text{ATR}_{28}(t)}$

4. **Midpoint Channels & Normalized Range Extremes:**
   $$\text{Midpoint}_k(t) = \frac{\max_{i \in [0, k-1]} H_{t-i} + \min_{i \in [0, k-1]} L_{t-i}}{2}$$
   - Features:
     - $F_{10} = \frac{C_t - \text{Midpoint}_{32}(t)}{\text{ATR}_{14}(t)}$
     - $F_{11} = \frac{H_t - \max_{i \in [1, 16]} H_{t-i}}{\text{ATR}_7(t)}$
     - $F_{12} = \frac{L_t - \min_{i \in [1, 16]} L_{t-i}}{\text{ATR}_7(t)}$

5. **Multi-Timeframe 4H Contextual Features:**
   Constructed from aligned completed 4-hour bars:
   - $F_{13} = \frac{C_{4H} - \text{EMA}_{8, 4H}}{\text{ATR}_{7, 4H}}$
   - $F_{14} = \text{ER}_{10, 4H}$
   - $F_{15} = \frac{\text{ATR}_{14, 4H}}{C_{4H}}$

6. **Cross-Horizon Dynamics & Volume Momentum:**
   - $F_{16} = \frac{V_{15m}}{\text{SMA}_{20}(V_{15m})}$ (Volume surge ratio)
   - $F_{17} = \frac{C_t - \text{Open}_{4H}}{\text{ATR}_{14}(t)}$ (Intra-regime drift)
   - $F_{18} = \frac{\text{ATR}_{7, 15m}}{\text{ATR}_{7, 4H}}$ (Volatility scale ratio)

---

## 3. Reconstructed Logistic Ensemble (V22-R)

Directional probability for class $y \in \{\text{UP}\}$ is computed across three independent linear models:

$$z_m = w_{m,0} + \sum_{j=1}^{18} w_{m,j} \tilde{F}_{j}, \quad p_m = \sigma(z_m) = \frac{1}{1 + e^{-z_m}}, \quad m \in \{A, B, C\}$$

Where $\tilde{F}_j = \frac{F_j - \mu_j}{\sigma_j}$ is normalized via pre-fitted historical scalers.

### 3.1 Tripartite Consensus Gate

$$\bar{p} = \frac{1}{3} (p_A + p_B + p_C)$$
$$\Delta_{\text{spread}} = \max(p_A, p_B, p_C) - \min(p_A, p_B, p_C)$$
$$d_{\min} = \min_{k} \sqrt{\sum_{j=1}^{18} \left(\frac{\tilde{F}_j - c_{k,j}}{s_{k,j}}\right)^2}$$

The decision rule $\mathcal{D}(\vec{F})$ produces:

$$\mathcal{D}(\vec{F}) = \begin{cases}
\text{UP} & \text{if } \bar{p} \ge 0.55 \land \Delta_{\text{spread}} \le 0.04 \land d_{\min} \le 1.8 \\
\text{DOWN} & \text{if } \bar{p} \le 0.45 \land \Delta_{\text{spread}} \le 0.04 \land d_{\min} \le 1.8 \\
\text{NO\_TRADE} & \text{otherwise}
\end{cases}$$

---

## 4. Entry-Anchored Dynamic Execution & Frictions

When a signal triggers a position entry at bar $t+1$ (open price $P_{\text{entry}}$):

1. **Stop Loss ($P_{\text{SL}}$) and Profit Target ($P_{\text{TP}}$):**
   Fixed strictly at the entry bar using entry ATR:
   $$\text{For LONG: } P_{\text{SL}} = P_{\text{entry}} - 1.5 \times \text{ATR}_7, \quad P_{\text{TP}} = P_{\text{entry}} + 2.5 \times \text{ATR}_7$$
   $$\text{For SHORT: } P_{\text{SL}} = P_{\text{entry}} + 1.5 \times \text{ATR}_7, \quad P_{\text{TP}} = P_{\text{entry}} - 2.5 \times \text{ATR}_7$$

2. **Conservative Intra-Bar Tie-Breaking:**
   If a single bar touches both $P_{\text{SL}}$ and $P_{\text{TP}}$, the stop loss is assumed to have triggered first (`STOP_LOSS_FIRST`), preventing optimistic backtest inflation.

3. **Time-Horizon Stop:**
   If neither threshold is triggered within $H_{\max} = 4$ bars (1 hour), the position is exited at market on the close of bar $t+4$.

4. **Institutional Taker Friction:**
   $$R_{\text{friction}} = \text{Fee}_{\text{entry}} + \text{Fee}_{\text{exit}} + \text{Spread} + \text{Slippage} = 0.0005 + 0.0005 + 0.0001 + 0.0001 = 0.0012 \; (12\text{ bps})$$

---

## 5. ACID Persistence & Crash Resilience

All state mutations in `src/eth_research/persistence.py` execute within explicit SQLite transactions:

```sql
BEGIN IMMEDIATE;
-- Insert evaluated signal
-- Update position status
-- Recalculate portfolio equity
COMMIT;
```

With `PRAGMA synchronous=NORMAL` and `PRAGMA journal_mode=WAL`, the system withstands power disruptions, process terminations, or API connection errors without corrupting the historical trading ledger.
