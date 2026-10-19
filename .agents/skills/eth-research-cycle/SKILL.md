---
name: eth-research-cycle
description: Runs a bounded, preregistered quantitative research cycle for ETHUSDT candle prediction, turning V1–V22 failure lessons into hypotheses with controlled out-of-sample checks and reproducible reporting.
---
# ETH Research Cycle

Read `AGENTS.md`, `docs/SOURCE_STATUS.md`, `docs/RESEARCH_PROTOCOL.md`, and `research/RESEARCH_LESSONS.md` before experiments.

1. Identify the current research version and frozen baselines; review relevant original reports.
2. State ONE falsifiable hypothesis, expected reason from earlier errors, minimum sample and acceptance conditions. Lock period splits and parameter grid before running held-out evaluations.
3. Write the pre-registration under `outputs/preregistrations/<version>.md` and a machine-readable config.
4. Implement deterministic data/feature/model code with unit tests.
5. Run only on allowed training/adaptation/validation periods. Do not view sealed holdout outcomes until every artifact is frozen and audited.
6. Report ALL outcomes, uncertainty, baselines, number of attempted variants, and failure modes. No retroactive repair.
7. If it fails, mark FAIL or INCONCLUSIVE; if it looks promising, require a new untouched window and economic execution validation before promotion.
8. Stop the cycle after a reproducible report, test run, and next recommendation. No infinite hyperparameter search.

Do not route to a live-order connector. Use `eth-backtest-audit` whenever data split, parity or lookahead is in question.
