# Provenance and verification status

## Included source documents
- All 22 V1–V22 historical backtest reports from the locally mounted originals; reports are copied without modification under `research/backtests`.
- `research/reference/ETH_V1_to_V21_Learning_Corpus_and_V22_Methodology.md` — short original learning state; main V22 detailed document is the V22 report itself.
- `research/reference/ETH_V23_PreRegistration.md` — states V23 is NOT SCORED / PENDING_EXACT_MODEL_ARTIFACTS.
- `artifacts/unverified/ETH_V22_Reconstruction_Audit_Model.UNVERIFIED.json` — independently reconstructed model; not official.

## Missing original source
The originally uploaded `ETH_V1_to_V22_Learning_Corpus_and_V23_Methodology.md` could not be accessed as a raw file when packaging. Do not pretend it is present. Recover it from the original conversation/files if possible. The accessible V22 report covers much of the same conceptual content, but is not byte-identical.

## Critical blocker
The original frozen V22 expert intercepts/weights, per-expert train means/sds, exact feature code, exclusions and original signal-level control outputs are absent. The reconstruction has different sample and signal counts from V22:

| Control | Original | Reconstruction |
|---|---|---|
| Adaptation | 95 hits / 159 signals | 105 / 175 |
| Fresh | 48 / 81 | 48 / 80 |

Hence V23 must NOT be described as an official exact V22 replication until artifact/parity verification succeeds.

## Leakage warning
The complete V22 Fresh data are known, not fresh anymore. V1–V21 historical studies/hidden periods are also documented, so they cannot become fresh untouched tests again. V23 2025-07-05..2025-07-11 remains locked in the preregistration; avoid even descriptive V23 outcome browsing during reproducibility work.

## Privacy Redactions for Public Open-Source Release
In accordance with open-source privacy standards, historical backtest reports V11 through V22 in this public repository have been sanitized to replace individual personal names in section titles with standard executive headings (e.g. Executive Summary). SOURCE_MANIFEST.json has been updated with recalculated SHA-256 hashes reflecting these public release copies, explicitly documenting their provenance as privacy-redacted copies while preserving 100% of underlying numerical results, dates, and conclusions.
