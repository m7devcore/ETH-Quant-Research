# Proposed agent and skill architecture

## Persistent agent
`AGENTS.md` governs every research step. The human uses Gemini/Antigravity to write, execute, test and review research code, but it is not a broker account or autonomous investment manager.

## Independent skills
- `eth-research-cycle`: choose hypothesis, preregister, run bounded implementation/test/evaluation cycle, document pass/fail, stop.
- `eth-backtest-audit`: prevent leakage, reconstruct data and check old models against known-control signals, report discrepancies honestly.
- `eth-signal-analysis`: apply existing frozen model to supplied OHLCV/feature tensors and return UP/DOWN/NO TRADE + trace; no real orders.

## Application components to implement in later phases
1. Public market data adapter; 2. immutable bar storage; 3. feature engine; 4. expert/scaler artifact loader with provenance; 5. signal permission engine; 6. deterministic simulator; 7. risk/fee evaluator; 8. metrics reporter; 9. paper-trading observer; 10. separately authorized live executor **only after future signoff**.

Do not combine trading execution with the research/validation agent. The build must work without keys and without a connected exchange trading account.
