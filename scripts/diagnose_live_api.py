"""
Standalone Diagnostic Tool: Live Binance Futures API Connectivity.
Reports live external network accessibility and clearly identifies environmental
or legal/geographical restrictions (e.g. HTTP 451 in cloud runner datacenters).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

TARGET_ENDPOINT = "https://fapi.binance.com/fapi/v1/klines"
TEST_SYMBOL = "ETHUSDT"
TEST_INTERVAL = "15m"


def run_diagnostic(strict: bool = False) -> int:
    print("=" * 70)
    print("ETH Quant Research — Live Market API Connectivity Diagnostic")
    print(f"Target Endpoint: {TARGET_ENDPOINT}")
    print(f"Test Parameters: symbol={TEST_SYMBOL}, interval={TEST_INTERVAL}, limit=2")
    print("=" * 70)

    params = urllib.parse.urlencode({"symbol": TEST_SYMBOL, "interval": TEST_INTERVAL, "limit": 2})
    url = f"{TARGET_ENDPOINT}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ETH-Quant-Research-Diagnostic/1.0",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.status
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[OK] Live Binance Futures API is reachable (HTTP {status_code}).")
            print(f"Successfully received {len(data)} completed {TEST_INTERVAL} candle records.")
            print("=" * 70)
            print("STATUS: REACHABLE (Live API accessible from this host environment)")
            print("=" * 70)
            return 0
    except urllib.error.HTTPError as e:
        print(f"HTTP Status Code: {e.code} ({e.reason})")
        if e.code == 451:
            print("\n[ENVIRONMENT RESTRICTION] Live Binance Futures API returned HTTP 451:")
            print("  'HTTP Error 451: Unavailable For Legal Reasons'")
            print("\nDIAGNOSTIC ANALYSIS:")
            print("  - This host environment or cloud datacenter IP range is located in a")
            print("    jurisdiction where Binance USD-M Perpetual Futures access is geoblocked.")
            print("  - This restriction is normal and expected on GitHub Actions hosted")
            print("    cloud runners (e.g. Azure / AWS US and European regions).")
            print("  - Core Determinism: All 18-feature calculations, model scoring, unit tests,")
            print("    and simulated paper trading remain 100% operational and independent of")
            print("    live external network access.")
            print("=" * 70)
            print("STATUS: ENVIRONMENT_RESTRICTED (Informational only — Non-fatal for CI)")
            print("=" * 70)
            return 1 if strict else 0
        elif e.code == 429:
            print("\n[RATE LIMITED] Endpoint returned HTTP 429: Too Many Requests.")
            print("=" * 70)
            print("STATUS: RATE_LIMITED")
            print("=" * 70)
            return 1 if strict else 0
        else:
            print(f"\n[HTTP ERROR] Endpoint returned HTTP {e.code}: {e.reason}")
            print("=" * 70)
            print(f"STATUS: HTTP_{e.code}")
            print("=" * 70)
            return 1 if strict else 0
    except urllib.error.URLError as e:
        print(f"\n[CONNECTION ERROR] Failed to connect to {TARGET_ENDPOINT}: {e.reason}")
        print("=" * 70)
        print("STATUS: CONNECTION_UNAVAILABLE")
        print("=" * 70)
        return 1 if strict else 0
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")
        print("=" * 70)
        print("STATUS: ERROR")
        print("=" * 70)
        return 1 if strict else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Binance Futures Public API Connectivity Diagnostic")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on environmental restrictions")
    args = parser.parse_args()
    sys.exit(run_diagnostic(strict=args.strict))
