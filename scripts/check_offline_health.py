import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from eth_research.runner import run_health_check
from eth_research.data import Candle

class DeterministicMockClient:
    def fetch_klines_chunk(self, symbol: str, interval: str, limit: int = 2) -> list[Candle]:
        return [
            Candle(
                open_time=1700000000000,
                open=3000.0,
                high=3010.0,
                low=2990.0,
                close=3005.0,
                volume=100.0,
                close_time=1700000899999,
                quote_volume=300000.0,
                trades=50,
                taker_buy_base=50.0,
                taker_buy_quote=150000.0,
            )
        ]

print("=" * 70)
print("ETH Quant Research Engine — Offline Deterministic CI Health Check")
print("Mode: OFFLINE SIMULATION (Zero External Network / Simulated Mock Client)")
print("=" * 70)

buffer = io.StringIO()
with tempfile.TemporaryDirectory() as tmpdir:
    temp_db = Path(tmpdir) / 'ci_health.sqlite3'
    with redirect_stdout(buffer):
        passed = run_health_check(db_path=temp_db, client=DeterministicMockClient())

output = buffer.getvalue()
# Clarify simulated mock data line so it clearly identifies simulated Binance data
output = output.replace(
    "[OK] Binance Futures API: Reachable public klines endpoint",
    "[OK] Binance Futures API: Simulated offline mock data verified (no live API connectivity)",
)
print(output, end="")

if not passed:
    print('FAIL: Deterministic health check failed.')
    sys.exit(1)

print('PASS: Deterministic operational health check passed.')

