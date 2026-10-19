# Antigravity Portable Trading Skills

## 1. What is an Antigravity Trading Skill?

A **Portable Trading Skill** is a standardized, modular set of instructions, procedural rules, and domain-specific knowledge that equips autonomous AI agents (such as Gemini CLI, Google Antigravity, or Claude Code) to perform complex quantitative research and auditing tasks without human micro-management.

In `ETH-Quant-Research`, skills are located in `.agents/skills/`.

---

## 2. Integrated Skills Inventory

### 2.1 `eth-signal-analysis`
- **Location:** `.agents/skills/eth-signal-analysis/SKILL.md`
- **Purpose:** On-demand zero-order classification of arbitrary candlestick series into `UP`, `DOWN`, or `NO_TRADE`.
- **Key Capabilities:**
  - Ingests verified completed candles.
  - Extracts the causal 18-feature vector.
  - Computes expert probabilities and consensus spreads.
  - Emits structured JSON rationale explaining why a signal was accepted or rejected.
  - **Hard Safety Rule:** Never places live financial orders.

### 2.2 `eth-backtest-audit`
- **Location:** `.agents/skills/eth-backtest-audit/SKILL.md`
- **Purpose:** Forensic audit of quantitative backtest reports.
- **Key Capabilities:**
  - Audits Binance ETHUSDT perpetual backtests for lookahead leaks.
  - Verifies candlestick alignment and settlement lag.
  - Detects regime contamination, survivorship bias, and sample size discrepancies.
  - Validates trading friction realism (commissions, spread, slippage).

### 2.3 `eth-research-cycle`
- **Location:** `.agents/skills/eth-research-cycle/SKILL.md`
- **Purpose:** Bounded, preregistered hypothesis formulation and scientific evaluation.
- **Key Capabilities:**
  - Formulates new hypotheses derived from historical failures (V01–V22).
  - Drafts formal preregistrations locking parameter sets and evaluation bounds.
  - Enforces out-of-sample data isolation.
  - Generates reproducible markdown research reports and decision logs.

---

## 3. Portable Skill Integration Guide

To invoke these skills within agentic workflows:

```bash
# In Gemini CLI / Antigravity agent sessions:
activate_skill eth-backtest-audit
# or
activate_skill eth-signal-analysis
# or
activate_skill eth-research-cycle
```

Each skill adheres to the unified Antigravity Skill Specification:
1. `<instructions>`: Clear, enforceable step-by-step procedures.
2. `<rules>`: Strict constraints and prohibited actions.
3. `<output_format>`: Predictable, machine-parseable response schemas.
