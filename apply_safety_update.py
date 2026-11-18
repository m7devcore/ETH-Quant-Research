"""Apply non-destructive safety documentation patches to ETH-Quant-Research.

Run from within a checked-out repository after extracting this bundle at root.
All replacement anchors are verified before any file is written.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if not (ROOT / "LICENSE").exists() or not (ROOT / "README.md").exists():
    sys.exit("ERROR: Extract this package into the ROOT of an ETH-Quant-Research checkout before running.")


def replacements(text, ops, filename):
    for old, new in ops:
        if old == new:
            continue
        if new in text:
            continue  # idempotent rerun (the old anchor may be inside the new block)
        elif old in text:
            text = text.replace(old, new, 1)
        else:
            raise ValueError(f"Cannot safely apply {filename}: expected anchor not found: {old[:120]!r}")
    return text


readme_ops = [
    (
        "[![Zero Lookahead](https://img.shields.io/badge/Leakage_Audit-0_Lookahead_Verified-success)](docs/RESEARCH_PROTOCOL.md)",
        "[![Causality Checks](https://img.shields.io/badge/Causality-Checks_in_CI-blue)](docs/RESEARCH_PROTOCOL.md)",
    ),
    (
        "> **Causal, zero-lookahead quantitative research engine and paper-trading harness for Binance ETHUSDT Perpetual Futures.**",
        "> **Causal, zero-lookahead quantitative research engine and paper-trading harness for Binance ETHUSDT Perpetual Futures.**\n\n> **Research only. Not investment advice or a live-execution product.** Read [the full disclaimer](DISCLAIMER.md) and [known limitations and safety review](docs/SAFETY_AND_LIMITATIONS.md). Simulated results are not proof of future profitability.",
    ),
    (
        '4. **No Warranties:** This software is provided under the Apache-2.0 License "AS IS", without warranties or conditions of any kind, either express or implied.',
        '4. **No Warranties:** This software is provided under the Apache-2.0 License "AS IS", without warranties or conditions of any kind, either express or implied, except where the law does not permit exclusion.\n5. **No Live Execution:** Do not connect exchange secrets, fund accounts, or treat paper positions as real trade orders. The reviewed code has no identified private trading interface, but forks and future changes are outside this claim. [Read the complete disclaimer](DISCLAIMER.md).',
    ),
    (
        "- [Security Policy](#security-policy)",
        "- [Security Policy](#security-policy)\n- [Full Risk Disclaimer](DISCLAIMER.md)\n- [Known Limitations and Review Scope](docs/SAFETY_AND_LIMITATIONS.md)",
    ),
    (
        "**absolute scientific discipline**:",
        "**reproducible research controls**:",
    ),
    (
        "- **Realistic Friction Schedule:** Every executed order applies realistic institutional taker friction:",
        "- **Illustrative Simulation Friction:** Each simulated fill uses assumed transaction-cost parameters (not a guarantee of executable live prices):",
    ),
    (
        "Strategy parameters and operational code are tracked via an immutable cryptographic manifest (`outputs/05b_freeze_manifest.json`). Any modification to code or parameters breaks the SHA-256 integrity seal, ensuring reproducible research audits.",
        "Selected frozen strategy files are checked against SHA-256 hashes in the versioned manifest (`outputs/05b_freeze_manifest.json`). The verification detects changes to covered files when run; the repository and local logs are not tamper-proof.",
    ),
    (
        "providing an immutable audit trail of every evaluated signal, active position, and realized PnL.",
        "recording a local (not tamper-proof) audit log of simulated signals, positions, and PnL.",
    ),
    (
        "Execute the 63 unit tests verifying data causality, feature extraction, policy thresholds, dynamic execution, and sealed window containment:",
        "Execute the unit tests covering data causality, policy thresholds, simulation, sealed windows, and research-only safety controls:",
    ),
    (
        "*Expected output:* `Ran 63 tests in ~3s. OK`",
        "*Expected output:* `OK` (test count and runtime vary by version and platform).",
    ),
    (
        "Security and safety are built into the engine by design. The codebase is locked in `research_only` mode and contains zero facilities to execute real financial transactions. To report vulnerabilities or security issues, please review [`SECURITY.md`](SECURITY.md).",
        "The reviewed repository is intended for `research_only` operation and contains no identified private exchange order-submission interface. This is a scoped source review, not a security or legal certification; modified forks may add execution. See [`SECURITY.md`](SECURITY.md), [`DISCLAIMER.md`](DISCLAIMER.md), and [`docs/SAFETY_AND_LIMITATIONS.md`](docs/SAFETY_AND_LIMITATIONS.md).",
    ),
    (
        "Distributed under the **Apache-2.0 License**. See [`LICENSE`](LICENSE) for details.",
        "Distributed under the **Apache-2.0 License**. See [`LICENSE`](LICENSE) for details. The [research and financial risk disclaimer](DISCLAIMER.md) explains intended use and material limitations. Neither the license nor a disclaimer eliminates non-waivable liability.",
    ),
]

arabic_ops = [
    (
        "هذا المشروع مجلد أبحاث وتجارب لتطوير نظام تحليل ETHUSDT. **ليس بوت تداول حي، وليس استراتيجية مثبتة الربحية**.",
        "هذا المشروع مجلد أبحاث وتجارب لتطوير نظام تحليل ETHUSDT. **ليس بوت تداول حي، وليس استراتيجية مثبتة الربحية**.\n\n**تنبيه قانوني ومالي:** لا يقدم توصيات استثمارية، ولا يضمن الأرباح أو عدم الخسارة، ولا يجوز إدخال مفاتيح API خاصة أو استخدامه لتنفيذ تداول حي. اقرأ [إخلاء المسؤولية الكامل](DISCLAIMER.md) و[حدود النظام والفحص الأمني](docs/SAFETY_AND_LIMITATIONS.md). الترخيص لا يمنع رفع دعاوى ولا يلغي المسؤولية التي يفرضها القانون.",
    ),
]

security_ops = [
    (
        "1. **Hardcoded Research-Only Scope:**\n   - The framework has `research_only = True` hardcoded as the immutable default.\n   - There are **zero** order-execution endpoints, exchange balance manipulation calls, or private account API integrations.\n   - Real funds, private API keys, or exchange secret keys must **never** be used with this repository.",
        "1. **Research-Only Scope (Reviewed Source):**\n   - `config/research_mode.json` declares `mode: research_only`, `allow_live_trading: false`, and `allow_private_api: false`. Configuration declarations are not an immutable security boundary.\n   - No order-submission, balance manipulation, or authenticated exchange API interface was identified in the tracked source reviewed on 2026-11-18. This claim does not cover forks, future changes, or external integrations.\n   - Real funds, private API keys, and exchange secret keys must **never** be used with this repository. See [`DISCLAIMER.md`](DISCLAIMER.md) and [`docs/SAFETY_AND_LIMITATIONS.md`](docs/SAFETY_AND_LIMITATIONS.md).",
    ),
    (
        "   - The project strictly connects only to public, unauthenticated market data endpoints (such as `GET /fapi/v1/klines` on Binance Futures).",
        "   - The reviewed tracked network clients use public, unauthenticated Binance Futures candlestick data (`GET /fapi/v1/klines`). New network transports or endpoints must undergo explicit security review and pass research-only regression tests.",
    ),
    (
        "2. Send a responsible disclosure email detailing the vulnerability to the project maintainers.",
        "2. Contact the project maintainers through a verified private channel or GitHub's private vulnerability reporting feature if enabled. Do not post security-sensitive details publicly.",
    ),
    (
        "We will acknowledge receipt within 48 hours and work with you on a coordinated public fix.",
        "Maintainers will aim to acknowledge reports and coordinate remediation; response times are not guaranteed. No exchange account credentials or live orders should be included in reports.",
    ),
]

contributing_ops = [
    (
        "## 4. Code of Conduct",
        "## 4. Safety, Claims and Release Requirements\n\n- Do not introduce exchange order-submission, authenticated account APIs, private API keys, wallet handling, leverage changes, or live-execution pathways into this research repository.\n- Review any change in network access or dependencies; keep `tests/test_research_only_safety.py` and the existing CI suite passing. Static policy checks do not replace independent review.\n- Never advertise simulated PnL, historical win rates, or reconstructed model metrics as guaranteed or independently verified investment returns. Preserve negative outcomes and limitations.\n- Review [the full disclaimer](DISCLAIMER.md) and [known limitations](docs/SAFETY_AND_LIMITATIONS.md) when research, model behavior, or risk assumptions change.\n\n---\n\n## 5. Code of Conduct",
    ),
]

workflow_ops = [
    (
        "      - name: Run Full Python Test Suite\n        run: python -m unittest discover -s tests -v",
        "      - name: Verify Research-Only Safety Guard\n        run: python -m unittest discover -s tests -p test_research_only_safety.py -v\n\n      - name: Run Full Python Test Suite\n        run: python -m unittest discover -s tests -v",
    ),
]

jobs = {
    "README.md": readme_ops,
    "README_AR.md": arabic_ops,
    "SECURITY.md": security_ops,
    "CONTRIBUTING.md": contributing_ops,
    ".github/workflows/ci.yml": workflow_ops,
}

pending = {}
for filename, ops in jobs.items():
    path = ROOT / filename
    if not path.exists():
        sys.exit(f"ERROR: Required repository file missing: {filename}")
    raw = path.read_bytes()
    decoded = raw.decode("utf-8-sig")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    normalized = decoded.replace("\r\n", "\n")
    if filename == ".github/workflows/ci.yml":
        # Match a complete line: the new name is a prefix of the old name.
        old_line = "      - name: Run Full Python Test Suite (63 tests)"
        new_line = "      - name: Run Full Python Test Suite"
        lines = normalized.splitlines(keepends=True)
        matches = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == old_line]
        if len(matches) > 1:
            raise ValueError("Cannot safely apply CI update: ambiguous full test suite steps")
        if matches:
            i = matches[0]
            lines[i] = lines[i].replace(old_line, new_line, 1)
            normalized = "".join(lines)
    updated = replacements(normalized, ops, filename)
    if updated != decoded.replace("\r\n", "\n"):
        pending[path] = (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + updated.replace("\n", newline).encode("utf-8")

for required in ["DISCLAIMER.md", "docs/SAFETY_AND_LIMITATIONS.md", "tests/test_research_only_safety.py"]:
    if not (ROOT / required).is_file():
        sys.exit(f"ERROR: Extract the included file first: {required}")

for path, content in pending.items():
    path.write_bytes(content)
    print("Updated:", path.relative_to(ROOT))
print("Safety documentation patches applied. Apache LICENSE and frozen research files were not modified.")
print("NEXT: Run workspace/integrity checks and unit tests; review and commit the changes.")
