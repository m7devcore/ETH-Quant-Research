"""Regression checks for research-only scope (no third-party dependencies).

These static checks cover common accidental regressions; they cannot establish
that all conceivable execution paths or modified forks are harmless.
"""

from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKED = (ROOT / "src" / "eth_research", ROOT / "scripts")
APPROVED_NETWORK_FILES = {
    "src/eth_research/data.py",
    "scripts/diagnose_live_api.py",
}
PUBLIC_KLINES = "https://fapi.binance.com/fapi/v1/klines"
FORBIDDEN_NETWORK_MODULES = (
    "requests", "httpx", "aiohttp", "websockets", "ccxt", "binance",
    "socket", "http.client", "httpx", "ftplib", "smtplib", "subprocess",
)
FORBIDDEN_TEXT = (
    "x-mbx-apikey", "/fapi/v1/order", "/fapi/v2/account",
    "/fapi/v2/balance", "/fapi/v1/leverage", "/api/v3/order",
    "/api/v3/account", "/api/v3/userdata", "api_secret",
)


def _is_module(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def _call_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parent = _call_name(func.value)
        return f"{parent}.{func.attr}" if parent else func.attr
    return ""


class ResearchOnlySafetyTests(unittest.TestCase):
    def test_research_only_configuration(self) -> None:
        config = json.loads((ROOT / "config" / "research_mode.json").read_text(encoding="utf-8"))
        self.assertEqual(config["mode"], "research_only")
        self.assertIs(config["allow_live_trading"], False)
        self.assertIs(config["allow_private_api"], False)

    def test_only_public_klines_endpoints_declared(self) -> None:
        for relative, constant_name in (
            ("src/eth_research/data.py", "BASE_URL"),
            ("scripts/diagnose_live_api.py", "TARGET_ENDPOINT"),
        ):
            with self.subTest(source=relative):
                tree = ast.parse((ROOT / relative).read_text(encoding="utf-8-sig"))
                values = [node.value.value for node in ast.walk(tree)
                          if isinstance(node, (ast.Assign, ast.AnnAssign))
                          and isinstance(node.value, ast.Constant)
                          and isinstance(node.value.value, str)
                          and any(isinstance(target, ast.Name) and target.id == constant_name
                                  for target in (node.targets if isinstance(node, ast.Assign) else [node.target]))]
                self.assertEqual(values, [PUBLIC_KLINES])

    def test_no_unapproved_network_transports_or_auth_endpoints(self) -> None:
        for directory in TRACKED:
            for path in directory.rglob("*.py"):
                relative = path.relative_to(ROOT).as_posix()
                tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=relative)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        modules = [item.name for item in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        modules = [node.module] if node.module else []
                    else:
                        modules = []
                    for module in modules:
                        if any(_is_module(module, banned) for banned in FORBIDDEN_NETWORK_MODULES):
                            self.fail(f"Unreviewed network/process module {module} in {relative}:{node.lineno}")
                        if _is_module(module, "urllib.request") and relative not in APPROVED_NETWORK_FILES:
                            self.fail(f"Unapproved network client import in {relative}:{node.lineno}")
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        val = node.value.lower()
                        for marker in FORBIDDEN_TEXT:
                            self.assertNotIn(marker, val, f"Forbidden endpoint/secret marker in {relative}:{node.lineno}")
                    if not isinstance(node, ast.Call):
                        continue
                    called = _call_name(node.func)
                    if called in {"eval", "exec", "__import__", "os.system", "os.popen", "importlib.import_module"}:
                        self.fail(f"Dynamic execution needs explicit security review: {relative}:{node.lineno}")
                    if called not in {"urllib.request.Request", "urllib.request.urlopen"}:
                        continue
                    self.assertIn(relative, APPROVED_NETWORK_FILES, f"Network access from {relative}:{node.lineno}")
                    kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg is not None}
                    self.assertNotIn("data", kwargs, f"Potential implicit POST in {relative}:{node.lineno}")
                    self.assertEqual(len(node.args) <= 1, True, f"Unexpected network arguments in {relative}:{node.lineno}")
                    if "method" in kwargs:
                        method = kwargs["method"]
                        self.assertIsInstance(method, ast.Constant)
                        self.assertEqual(method.value, "GET")


if __name__ == "__main__":
    unittest.main()
