# Safety Review, Known Limitations and Evidence Boundaries

**Review date:** 2026-11-18

**Scope:** Published repository source and documentation reviewed for research-only boundaries; not a penetration test, legal opinion, investment audit, or independent performance validation.

## Research-only scope observed

- `config/research_mode.json` declares `mode: research_only`, `allow_live_trading: false`, and `allow_private_api: false`. These settings are explicit declarations, not a security sandbox that can constrain modified code.
- The tracked `src/eth_research/data.py` network client uses a public Binance USD-M Futures **GET `/fapi/v1/klines`** candlestick endpoint. `scripts/diagnose_live_api.py` uses the same endpoint for an optional connectivity check. Neither requires private exchange credentials.
- The runner and portfolio classes record **simulated** positions, fills and PnL in local SQLite. In the reviewed code, no exchange order creation, leverage update, balance manipulation, or authenticated exchange API call was identified.
- `tests/test_research_only_safety.py` supplies an automated regression guard for selected research-only configuration and common forbidden live-trading transports. It is a defense-in-depth check, **not** a proof that execution is impossible or that all future vulnerabilities have been excluded.
- The historical frozen strategy, artifacts, backtest reports and integrity hashes are intentionally unchanged by this documentation-and-test update.

## Important limitations and failure modes

| Area | Limitation and user impact |
| --- | --- |
| Model provenance | Original trained legacy V22 weights were not preserved. Reconstructed V22-R is a distinct model family until exact prediction parity is demonstrated. |
| Backtests and research | Historical outcomes may be overfit or contaminated by repeated selection, regime shift, data defects, or hidden lookahead. Do not interpret directional accuracy as executable profit. |
| Execution modeling | Paper fills depend on estimated spread, fees, slippage and timing; actual market liquidity, latency, queue priority and gaps can cause materially worse results. |
| Funding and margin | Funding rate variability, leverage, liquidations, exchange margin rules, and account-specific constraints are not fully modeled by simple unleveraged simulations. |
| Data and services | Public market data can fail, arrive late, be inconsistent, or be unavailable in some jurisdictions. A clean local test is not a guarantee of live service availability. |
| SQLite logs and research hashes | Local state and repository content can be altered by a person with filesystem/repository access; a checksum or SQLite log is not a tamper-proof legal audit record. |
| Trading safety | The maintained code is not a live trading product. User forks or third-party integrations can add order execution regardless of this repository's documented intent. |
| Legal exposure | Disclaimers and Apache 2.0 reduce certain contractual expectations but do not prevent lawsuits or remove mandatory legal duties. Laws and regulatory requirements vary by location and actual use. |

## Release and safety verification checklist

1. Run `python scripts/check_workspace.py` and `python scripts/verify_frozen_hashes.py`; neither should change the frozen corpus or manifest.
2. Run `python -m unittest discover -s tests -v` and confirm that `test_research_only_safety.py` passes. A passing static guard is only a limited code policy check.
3. Run `python scripts/check_offline_health.py` for a deterministic offline health check; avoid real credentials and live order endpoints.
4. Review every new network dependency, CLI mode, exchange endpoint, and commit for authenticated/private API use, secret handling, or any path that can submit transactions.
5. Keep the [`DISCLAIMER.md`](../DISCLAIMER.md), README warnings, security policy, and known limitations consistent with the actual released implementation and observed results.
6. Do not market simulated results as verified profits, guaranteed win rates, financial advice, or trading-system certification. Preserve unsuccessful experiments and reproducibility evidence.
7. Obtain independent financial, security, and jurisdiction-appropriate legal review before repurposing this research into a commercial advisory, signals, or live-execution product.

**Verification status for this proposed update:** Source-level observations above are based on tracked code reviewed on the stated date. The full repository CI and any new test suite must be run against the exact applied commit before recording a PASS. No live exchange order was sent or requested as part of this review.
