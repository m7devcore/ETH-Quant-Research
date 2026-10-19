# ETH-Quant-Research

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![CI Suite](https://github.com/m7devcore/ETH-Quant-Research/actions/workflows/ci.yml/badge.svg)](https://github.com/m7devcore/ETH-Quant-Research/actions)
[![Zero Lookahead](https://img.shields.io/badge/Leakage_Audit-0_Lookahead_Verified-success)](docs/RESEARCH_PROTOCOL.md)
[![Preregistration](https://img.shields.io/badge/Methodology-Preregistered_Frozen_Gates-purple)](outputs/05b_freeze_manifest.json)
[![Standard Library](https://img.shields.io/badge/Dependencies-Standard_Library_Only-brightgreen)](pyproject.toml)

> **Causal, zero-lookahead quantitative research engine and paper-trading harness for Binance ETHUSDT Perpetual Futures.**

---

## ⚠️ Critical Research & Financial Disclaimer

**TRADING PROFITABILITY HAS NOT BEEN INDEPENDENTLY ESTABLISHED.**

1. **Academic and Research Purpose Only:** This repository is an open-source quantitative research framework developed for reproducible scientific backtesting, feature causality verification, and algorithmic auditing. It is not financial advice, an investment recommendation, or a commercial signal service.
2. **No Historical Parity Guarantee:** The models and heuristics contained herein (including `V22-R`) are independent reconstructions of earlier research hypotheses. As thoroughly documented in the audit logs, original training artifacts from legacy versions were unpreserved, making reconstructed models distinct model families whose performance must not be conflated with historical theoretical claims.
3. **Severe Financial Risk:** Cryptocurrency derivative trading carries substantial financial risk, including liquidation and total loss of capital. This software is configured in `research_only` mode by default. **DO NOT** connect live financial exchange accounts or private trading API keys.
4. **No Warranties:** This software is provided under the Apache-2.0 License "AS IS", without warranties or conditions of any kind, either express or implied.

---

## Table of Contents

- [Core Mission & Philosophy](#core-mission--philosophy)
- [Scientific Innovations & Architecture](#scientific-innovations--architecture)
  - [1. Zero-Lookahead Causal Pipeline](#1-zero-lookahead-causal-pipeline)
  - [2. 18 Multi-Scale Causal Features](#2-18-multi-scale-causal-features)
  - [3. Reconstructed Logistic Ensemble (V22-R)](#3-reconstructed-logistic-ensemble-v22-r)
  - [4. Dynamic Execution & Friction Modeling](#4-dynamic-execution--friction-modeling)
  - [5. Cryptographic Research Freeze Gate](#5-cryptographic-research-freeze-gate)
  - [6. ACID SQLite Paper-Trading Engine](#6-acid-sqlite-paper-trading-engine)
- [Project Directory Structure](#project-directory-structure)
- [Quick Start & Installation](#quick-start--installation)
  - [Prerequisites](#prerequisites)
  - [Health Check Diagnostic](#health-check-diagnostic)
  - [Running the Unit Test Suite](#running-the-unit-test-suite)
  - [Executing a Paper-Trading Cycle](#executing-a-paper-trading-cycle)
- [Research Corpus & History (V01–V22)](#research-corpus--history-v01v22)
- [Current Limitations & Known Discrepancies](#current-limitations--known-discrepancies)
- [Roadmap: Antigravity Portable Trading Skills](#roadmap-antigravity-portable-trading-skills)
- [Contributing](#contributing)
- [Security Policy](#security-policy)
- [License & Citation](#license--citation)

---

## Core Mission & Philosophy

The crypto algorithmic trading landscape is dominated by overfitted backtests, hidden lookahead bias, unmodeled taker slippage, and unreplicable cherry-picked wins. 

`ETH-Quant-Research` was built to counter these practices through **absolute scientific discipline**:
- **Zero Third-Party Runtime Dependencies:** Implemented exclusively with the Python Standard Library (`urllib`, `sqlite3`, `hashlib`, `math`, `json`, `dataclasses`). Fast, lightweight, portable across Windows, Linux, and macOS.
- **Strictly Causal Information Flow:** Decisions for the next 15-minute bar are formed exclusively from closed candles.
- **Audited Parity & Preservation:** Preserves 22 iterations of historical research reports (`research/backtests/V01..V22`) and transparently documents every failure mode, adaptation defect, and data discrepancy.
- **Programmatically Sealed Evaluation Windows:** The V23 evaluation block (July 5–11, 2025 Europe/Istanbul) is cryptographically locked behind programmatic gates (`check_v23_sealed_overlap`) to prevent test-set contamination.

---

## Scientific Innovations & Architecture

### 1. Zero-Lookahead Causal Pipeline
- **Candle Alignment:** Native Binance USD-M Perpetual 4H and 15m candle buckets.
- **Settlement Buffers:** Enforces a mandatory settlement lag ($t_{close} + 2500\text{ms}$) to guarantee complete candle finality and avoid intrabar price repaint.
- **Temporal Strictness:** All internal computations utilize UTC millisecond timestamps, eliminating timezone ambivalence.

### 2. 18 Multi-Scale Causal Features
The feature extraction engine calculates 18 normalized technical features across 15m, 4H, and cross-horizon structures without future peeking:
- **Momentum & Efficiency:** Kaufman Efficiency Ratio (ER) across 10, 20, and 30 bars.
- **Volatility Dynamics:** Average True Range (ATR) over 7, 14, and 28 periods, normalized by close price.
- **Trend Dispersion:** Exponential Moving Average (EMA) ratios and divergences (EMA 8, 21, 55).
- **Geometric Support/Resistance:** Midpoint-32 channels and normalized distance metrics to cyclical extremes.

### 3. Reconstructed Logistic Ensemble (V22-R)
The classification model evaluates next-15m directional expectancy ($y \in \{\text{UP}, \text{DOWN}\}$) using a multi-expert linear/logistic architecture:
- **Three Specialized Experts:**
  - Expert A (Short-horizon momentum and efficiency)
  - Expert B (Intermediate trend structure and volatility regimes)
  - Expert C (Multi-timeframe 4H regime integration)
- **Tripartite Consensus Gate:**
  - $\text{Long Signal (UP)} \iff \bar{p} \ge 0.55 \land \Delta_{\text{spread}} \le 0.04 \land d_{\min} \le 1.8$
  - $\text{Short Signal (DOWN)} \iff \bar{p} \le 0.45 \land \Delta_{\text{spread}} \le 0.04 \land d_{\min} \le 1.8$
  - Otherwise: `NO_TRADE` (Capital preservation mode).

### 4. Dynamic Execution & Friction Modeling
- **Entry-Anchored Trailing Rules:** Stop-loss ($1.5 \times \text{ATR}_7$) and take-profit ($2.5 \times \text{ATR}_7$) are fixed at the entry bar to prevent intra-trade target drift.
- **Realistic Friction Schedule:** Every executed order applies realistic institutional taker friction:
  - Exchange Taker Commission: $0.05\%$
  - Half-Spread Penalty: $0.005\%$
  - Adverse Execution Slippage: $0.005\%$
  - **Total Round-Trip Friction:** $0.12\%$ ($12\text{ bps}$).
- **Single Concurrent Position:** Conservative portfolio management enforcing a maximum of 1 active position at $1.0\times$ unleveraged capital.

### 5. Cryptographic Research Freeze Gate
Strategy parameters and operational code are tracked via an immutable cryptographic manifest (`outputs/05b_freeze_manifest.json`). Any modification to code or parameters breaks the SHA-256 integrity seal, ensuring reproducible research audits.

### 6. ACID SQLite Paper-Trading Engine
The operational runner (`src/eth_research/runner.py`) uses an embedded SQLite database configured in Write-Ahead Logging (`PRAGMA journal_mode=WAL`) with foreign key constraints, providing an immutable audit trail of every evaluated signal, active position, and realized PnL.

---

## Project Directory Structure

```text
ETH-Quant-Research/
├── .agents/skills/            # Antigravity agentic skill definitions
│   ├── eth-backtest-audit/    # Skill: Backtest lookahead and alignment audit
│   ├── eth-research-cycle/    # Skill: Bounded hypothesis research cycle
│   └── eth-signal-analysis/   # Skill: Zero-order signal classification
├── .github/workflows/         # GitHub Actions CI pipeline
│   └── ci.yml
├── artifacts/unverified/      # Unverified model weights checkpoint
│   └── ETH_V22_Reconstruction_Audit_Model.UNVERIFIED.json
├── config/                    # Research safety and boundary configuration
│   └── research_mode.json
├── data/raw/                  # Cached kline directory (.gitkeep protected)
├── docs/                      # Scientific documentation & architectural specs
│   ├── ARCHITECTURE.md        # Mathematical formulations & engine dataflow
│   ├── PORTABLE_SKILLS.md     # Reusable agent skills specifications
│   ├── RESEARCH_PROTOCOL.md   # Causal holdout protocol and rules
│   ├── SKILL_ARCHITECTURE.md  # Antigravity integration design
│   └── SOURCE_STATUS.md       # Provenance audit and source manifest
├── logs/                      # Execution and health check logs (.gitkeep)
├── outputs/                   # Phase reports, trade ledgers, freeze manifest
│   ├── 05b_freeze_manifest.json          # Cryptographic SHA-256 seal
│   ├── 05b_strategy_specification.md    # Strategy ETH-V22-D1 definition
│   ├── 05b_forward_validation_protocol.md# Preregistered evaluation window
│   └── ...
├── prompts/                   # Research agent system prompts
│   ├── 01_BOOTSTRAP_PROMPT.md
│   └── 02_RESEARCH_CYCLE_PROMPT.md
├── research/                  # Historical research corpus V01 through V22
│   ├── RESEARCH_LESSONS.md    # Forensic archive of failure modes
│   ├── backtests/             # 22 immutable historical backtest reports
│   └── reference/             # Learning corpus & V23 preregistration
├── scripts/                   # Workspace integrity and maintenance scripts
│   └── check_workspace.py
├── src/eth_research/          # Zero-dependency Python quantitative engine
│   ├── __init__.py
│   ├── candidates.py          # Parametric candidate evaluator
│   ├── data.py                # Public market data ingestion & validation
│   ├── dynamic_portfolio.py   # Entry-anchored portfolio simulator
│   ├── execution.py           # Trade execution & friction simulator
│   ├── features.py            # 18 causal multi-scale feature calculators
│   ├── model.py               # Logistic ensemble model loader
│   ├── persistence.py         # ACID SQLite state manager
│   ├── policy.py              # Decision gate & threshold evaluator
│   └── runner.py              # Paper-trading CLI & diagnostic harness
├── tests/                     # Comprehensive automated unit test suite (63 tests)
├── CONTRIBUTING.md            # Guidelines for open-source contributors
├── LICENSE                    # Apache-2.0 open-source license
├── pyproject.toml             # Standard Python packaging configuration
├── README.md                  # This documentation
└── SECURITY.md                # Vulnerability disclosure & safety policy
```

---

## Quick Start & Installation

### Prerequisites
- **Python:** 3.10 or higher.
- **Dependencies:** None! Zero third-party dependencies required. Standard library only.

### 1. Clone the Repository
```bash
git clone https://github.com/m7devcore/ETH-Quant-Research.git
cd ETH-Quant-Research
```

### 2. Run Workspace Integrity Check
Verify the byte-level integrity of all 22 historical research reports and configurations:
```bash
python scripts/check_workspace.py
```
*Expected output:* `PASS: 22 immutable original research reports V01..V22 present`

### 3. Run the Automated Unit Test Suite
Execute the 63 unit tests verifying data causality, feature extraction, policy thresholds, dynamic execution, and sealed window containment:
```bash
python -m unittest discover -s tests -v
```
*Expected output:* `Ran 63 tests in ~3s. OK`

### 4. Run Operational Health Check
Verify checkpoint integrity, SQLite persistence in WAL mode, public Binance endpoint reachability, and V23 sealed gate protection:
```bash
python src/eth_research/runner.py --check
```
*Expected output:* `RESULT: HEALTH CHECK PASSED. System is safe and ready for paper trading.`

### 5. Execute a Single Paper-Trading Cycle
Poll the latest closed candles, extract causal features, evaluate model consensus, and record simulated trade states into local SQLite:
```bash
python src/eth_research/runner.py --run-once --db-path data/paper_trading_state.sqlite3
```

---

## Research Corpus & History (V01–V22)

This repository preserves the complete evolutionary history of the strategy across 22 research phases in `research/backtests/`:
- **V01–V05:** Baseline 4H/15m trend-following; discovered acute lag in static EMA cross-overs.
- **V06–V12:** Introduction of multi-timeframe regime filtering; identified survivorship and multiple-testing biases.
- **V13–V18:** Feature space expansion to 18 indicators; identified lookahead traps in non-causal normalization.
- **V19–V21:** Machine-learned logistic experts; observed adaptation degradation during sudden volatility shocks.
- **V22:** Introduction of tripartite consensus gating and RMS distance filters.

For full forensic details on failure modes and methodological refinements, see [`research/RESEARCH_LESSONS.md`](research/RESEARCH_LESSONS.md).

---

## Current Limitations & Known Discrepancies

1. **Reconstructed Model vs Original Artifact:** The original trained model weights from legacy V22 were not preserved in the initial bundle. `V22-R` is an independent reconstruction. While it approximates historical aggregate win rates, exact signal-by-signal identity cannot be established.
2. **Execution Latency & Queue Dynamics:** Simulated fills assume market execution at the open of the bar following signal generation. Under volatile market spikes, real-world execution may experience additional slippage.
3. **Funding Rate Volatility:** Unleveraged paper trading does not account for long-term perpetual swap funding payments, which can impact net expectancy during sustained directional trending.

---

## Roadmap: Antigravity Portable Trading Skills

A primary objective of this repository is to modularize quantitative methodologies into **Portable Trading Skills** compatible with AI agent environments (such as Gemini CLI and Google Antigravity):
- [x] **`eth-signal-analysis`**: On-demand classification of arbitrary candle series into UP/DOWN/NO_TRADE with full explanation vectors.
- [x] **`eth-backtest-audit`**: Automated scanner that ingests historical backtests and audits them for lookahead leakage, candle alignment errors, and unrealistic trading friction.
- [x] **`eth-research-cycle`**: Structured quantitative framework enabling autonomous AI agents to propose, preregister, test, and audit new hypotheses without human intervention.
- [ ] **Cross-Asset Skill Adaptation:** Extending the causal 18-feature pipeline to BTCUSDT and SOLUSDT perpetual markets.
- [ ] **Reinforcement Learning Calibration:** Meta-policy optimization within strictly causal gym environments.

---

## Contributing

We welcome contributions from quantitative researchers, software engineers, and algorithmic traders!
Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) for full instructions on our coding standards, zero-lookahead verification, and the mandatory **preregistration process** for proposing new strategy candidates.

---

## Security Policy

Security and safety are built into the engine by design. The codebase is locked in `research_only` mode and contains zero facilities to execute real financial transactions. To report vulnerabilities or security issues, please review [`SECURITY.md`](SECURITY.md).

---

## License & Citation

Distributed under the **Apache-2.0 License**. See [`LICENSE`](LICENSE) for details.

If you use this research framework or dataset corpus in academic work or open-source projects, please cite:

```bibtex
@misc{eth_quant_research_2026,
  author = {ETH Quant Research Community},
  title = {ETH-Quant-Research: Causal Quantitative Research Engine for ETHUSDT Perpetual Futures},
  year = {2026},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/m7devcore/ETH-Quant-Research}}
}
```
