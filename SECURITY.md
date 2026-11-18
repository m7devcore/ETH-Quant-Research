# Security Policy

## 1. Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| < 1.1.0 | :x:                |

---

## 2. Security Architecture & Governance

`ETH-Quant-Research` is architected with multiple defense-in-depth security layers:

1. **Research-Only Scope (Reviewed Source):**
   - `config/research_mode.json` declares `mode: research_only`, `allow_live_trading: false`, and `allow_private_api: false`. Configuration declarations are not an immutable security boundary.
   - No order-submission, balance manipulation, or authenticated exchange API interface was identified in the tracked source reviewed on 2026-11-18. This claim does not cover forks, future changes, or external integrations.
   - Real funds, private API keys, and exchange secret keys must **never** be used with this repository. See [`DISCLAIMER.md`](DISCLAIMER.md) and [`docs/SAFETY_AND_LIMITATIONS.md`](docs/SAFETY_AND_LIMITATIONS.md).
2. **No Credentials in Codebase:**
   - The reviewed tracked network clients use public, unauthenticated Binance Futures candlestick data (`GET /fapi/v1/klines`). New network transports or endpoints must undergo explicit security review and pass research-only regression tests.
   - Any pull request containing API keys, private tokens, passwords, or exchange credentials will be closed and scrubbed immediately.
3. **Data Integrity & Sealed Gate Containment:**
   - The engine includes cryptographic barriers (`check_v23_sealed_overlap`) designed to detect and block unauthorized access to sealed test periods.
4. **ACID SQLite Resilience:**
   - State persistence uses local SQLite databases operating in WAL mode with strict foreign key constraints and transactional integrity.

---

## 3. Reporting a Vulnerability

If you discover a security vulnerability, data leakage flaw, or integrity bypass in this repository:

1. **Do NOT open a public GitHub issue.**
2. Contact the project maintainers through a verified private channel or GitHub's private vulnerability reporting feature if enabled. Do not post security-sensitive details publicly.
3. Include:
   - A description of the issue and potential impact.
   - Step-by-step reproduction instructions or proof-of-concept code.
   - Recommended mitigations.

Maintainers will aim to acknowledge reports and coordinate remediation; response times are not guaranteed. No exchange account credentials or live orders should be included in reports.
