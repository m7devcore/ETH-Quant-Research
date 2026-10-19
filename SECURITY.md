# Security Policy

## 1. Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| < 1.1.0 | :x:                |

---

## 2. Security Architecture & Governance

`ETH-Quant-Research` is architected with multiple defense-in-depth security layers:

1. **Hardcoded Research-Only Scope:**
   - The framework has `research_only = True` hardcoded as the immutable default.
   - There are **zero** order-execution endpoints, exchange balance manipulation calls, or private account API integrations.
   - Real funds, private API keys, or exchange secret keys must **never** be used with this repository.
2. **No Credentials in Codebase:**
   - The project strictly connects only to public, unauthenticated market data endpoints (such as `GET /fapi/v1/klines` on Binance Futures).
   - Any pull request containing API keys, private tokens, passwords, or exchange credentials will be closed and scrubbed immediately.
3. **Data Integrity & Sealed Gate Containment:**
   - The engine includes cryptographic barriers (`check_v23_sealed_overlap`) designed to detect and block unauthorized access to sealed test periods.
4. **ACID SQLite Resilience:**
   - State persistence uses local SQLite databases operating in WAL mode with strict foreign key constraints and transactional integrity.

---

## 3. Reporting a Vulnerability

If you discover a security vulnerability, data leakage flaw, or integrity bypass in this repository:

1. **Do NOT open a public GitHub issue.**
2. Send a responsible disclosure email detailing the vulnerability to the project maintainers.
3. Include:
   - A description of the issue and potential impact.
   - Step-by-step reproduction instructions or proof-of-concept code.
   - Recommended mitigations.

We will acknowledge receipt within 48 hours and work with you on a coordinated public fix.
