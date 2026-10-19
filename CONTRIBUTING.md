# Contributing to ETH-Quant-Research

Thank you for your interest in contributing to **ETH-Quant-Research**!

We welcome contributions from quantitative researchers, software engineers, and domain experts. This project is built on institutional scientific rigour, zero lookahead bias, and absolute reproducibility.

---

## 1. Scientific Research Principles

To protect this project from the common pitfalls of quantitative research (such as data dredging, p-hacking, and hindsight contamination), all contributors must uphold the following rules:

1. **Mandatory Hypothesis Preregistration:**
   - Any new trading strategy candidate or parameter adjustment **must be preregistered** with an explicit written hypothesis, feature set, and parameter bounds *before* evaluating out-of-sample test windows.
   - You must never adjust thresholds or feature weights after observing test results to inflate apparent win rates.
2. **Strict Zero-Lookahead Causality:**
   - Predictions at time $T$ must rely exclusively on information strictly available at or before $T$.
   - Intrabar price peeking, non-causal normalization across future bars, and post-dated candle revisions are considered critical bugs.
3. **Preservation of Failures:**
   - Historical failures and negative experimental results are first-class scientific assets. Never delete, rewrite, or suppress failed strategy logs.
4. **V23 Sealed Gate Integrity:**
   - The preregistered historical evaluation period (`2025-07-05 00:00` to `2025-07-11 23:59:59` Europe/Istanbul) is permanently locked and protected. Pull requests that weaken, bypass, or query the sealed window will be rejected immediately.

---

## 2. Engineering Standards

1. **Zero External Runtime Dependencies:**
   - The core research engine (`src/eth_research/`) is built **exclusively using the Python Standard Library** (`urllib`, `sqlite3`, `hashlib`, `math`, `json`, `dataclasses`).
   - Do NOT introduce dependencies (such as `pandas`, `numpy`, or `scikit-learn`) into the core runtime without prior architectural discussion. Keeping the framework dependency-free guarantees maximum portability, lightning-fast CI, and zero supply-chain risk.
2. **Python Compatibility & Style:**
   - Compatible with Python 3.10, 3.11, 3.12, 3.13, and 3.14.
   - Code must adhere to PEP 8.
   - Explicit type annotations (`typing`, `dataclasses`) are mandatory for all public functions, classes, and methods.
3. **Automated Unit Testing:**
   - Every bug fix or feature addition must be accompanied by new automated test cases in `tests/`.
   - All tests must run cleanly via `python -m unittest discover -s tests -v`.

---

## 3. Pull Request Workflow

1. **Fork the Repository:**
   - Fork `https://github.com/m7devcore/ETH-Quant-Research` to your GitHub account.
2. **Create a Topic Branch:**
   ```bash
   git checkout -b feat/causal-volatility-estimator
   # or
   git checkout -b fix/timestamp-alignment-edgecase
   ```
3. **Make Surgical, Idiomatic Changes:**
   - Keep changes focused and well-documented.
4. **Run Local Validation Suite:**
   ```bash
   # 1. Verify workspace reports and configs
   python scripts/check_workspace.py

   # 2. Run all unit tests
   python -m unittest discover -s tests -v

   # 3. Run operational health check
   python src/eth_research/runner.py --check --db-path temp_check.sqlite3
   ```
5. **Submit your Pull Request:**
   - Provide a clear, detailed summary of your changes.
   - Document any changes in computational complexity, memory usage, or feature definitions.
   - Ensure the CI workflow passes on all matrix configurations.

---

## 4. Code of Conduct

We are committed to providing a welcoming, inclusive, and professional environment for all contributors. Please maintain constructive and respectful discourse in all issues and pull requests.
