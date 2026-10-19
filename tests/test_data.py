"""Unit tests for public market data pipeline and V23 sealed containment."""

import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eth_research.data import (
    ISTANBUL_TZ,
    UTC_TZ,
    V23_END_MS,
    V23_START_MS,
    BinanceFuturesDataClient,
    Candle,
    CandleIntegrityError,
    SealedWindowViolationError,
    check_v23_sealed_overlap,
    validate_candle_sequence,
)


class TestDataInfrastructure(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def create_mock_candle(
        self,
        open_time: int,
        interval_ms: int = 15 * 60 * 1000,
        open_p: float = 3000.0,
        high_p: float = 3010.0,
        low_p: float = 2995.0,
        close_p: float = 3005.0,
    ) -> Candle:
        return Candle(
            open_time=open_time,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=100.0,
            close_time=open_time + interval_ms - 1,
            quote_volume=300000.0,
            trades=500,
            taker_buy_base=50.0,
            taker_buy_quote=150000.0,
        )

    def test_v23_sealed_boundary_exact(self):
        """Verify the exact mathematical boundaries of the sealed V23 window (July 5–11, 2025 Istanbul)."""
        dt_start = datetime.datetime(2025, 7, 5, 0, 0, 0, tzinfo=ISTANBUL_TZ)
        dt_end = datetime.datetime(2025, 7, 11, 23, 59, 59, tzinfo=ISTANBUL_TZ)
        self.assertEqual(int(dt_start.timestamp() * 1000), V23_START_MS)
        self.assertEqual(int(dt_end.timestamp() * 1000), V23_END_MS - 999)  # within the 1-second second ceiling

    def test_v23_sealed_overlap_protection(self):
        """Ensure check_v23_sealed_overlap strictly blocks any request entering the sealed period."""
        # Clean range completely before V23
        check_v23_sealed_overlap(1700000000000, 1710000000000)

        # Clean range completely after V23
        check_v23_sealed_overlap(V23_END_MS + 1000, V23_END_MS + 2000000)

        # Range overlapping beginning of V23
        with self.assertRaises(SealedWindowViolationError):
            check_v23_sealed_overlap(V23_START_MS - 1000, V23_START_MS + 1000)

        # Range completely inside V23
        with self.assertRaises(SealedWindowViolationError):
            check_v23_sealed_overlap(V23_START_MS + 5000, V23_END_MS - 5000)

        # Range enclosing V23
        with self.assertRaises(SealedWindowViolationError):
            check_v23_sealed_overlap(V23_START_MS - 10000, V23_END_MS + 10000)

    def test_candle_ohlc_integrity(self):
        """Verify detection of invalid high/low/open/close relationships."""
        step = 15 * 60 * 1000
        base_time = 1600000000000 - (1600000000000 % step)

        # High is below open
        c_bad_high = self.create_mock_candle(base_time, high_p=2990.0, open_p=3000.0)
        self.assertFalse(c_bad_high.is_valid_ohlc)

        # Low is above close
        c_bad_low = self.create_mock_candle(base_time, low_p=3010.0, close_p=3000.0)
        self.assertFalse(c_bad_low.is_valid_ohlc)

        # Valid candle
        c_good = self.create_mock_candle(base_time)
        self.assertTrue(c_good.is_valid_ohlc)

    def test_candle_sequence_validation(self):
        """Test sequence validation: duplicate times, unaligned times, and missing bar gaps."""
        step = 15 * 60 * 1000
        base_time = 1600000000000 - (1600000000000 % step)

        c1 = self.create_mock_candle(base_time)
        c2 = self.create_mock_candle(base_time + step)
        c3 = self.create_mock_candle(base_time + 2 * step)

        # Valid sequence of 3 candles
        validate_candle_sequence([c1, c2, c3], "15m")

        # Duplicate timestamp
        with self.assertRaises(CandleIntegrityError):
            validate_candle_sequence([c1, c1, c3], "15m")

        # Gap in sequence (missing c2)
        with self.assertRaises(CandleIntegrityError):
            validate_candle_sequence([c1, c3], "15m")

        # Misaligned timestamp (not divisible by interval)
        c_misaligned = self.create_mock_candle(base_time + 12345)
        with self.assertRaises(CandleIntegrityError):
            validate_candle_sequence([c_misaligned], "15m")

    def test_native_4h_bucket_alignment(self):
        """Ensure 4H candles strictly enforce 4-hour modulo alignment."""
        step_4h = 4 * 60 * 60 * 1000
        base_time = 1600000000000 - (1600000000000 % step_4h)
        c_4h = self.create_mock_candle(base_time, interval_ms=step_4h)
        validate_candle_sequence([c_4h], "4h")

        # Misaligned 4h (e.g. offset by 15 mins)
        c_4h_bad = self.create_mock_candle(base_time + 15 * 60 * 1000, interval_ms=step_4h)
        with self.assertRaises(CandleIntegrityError):
            validate_candle_sequence([c_4h_bad], "4h")

    def test_save_and_load_cache_integrity(self):
        """Test roundtrip serialization and hash verification."""
        step = 15 * 60 * 1000
        base_time = 1600000000000 - (1600000000000 % step)
        candles = [self.create_mock_candle(base_time + i * step) for i in range(5)]

        client = BinanceFuturesDataClient(cache_dir=self.cache_dir)
        filepath = self.cache_dir / "ETHUSDT_15m_test.json"

        client.save_candles_to_json(candles, filepath, "ETHUSDT", "15m")
        self.assertTrue(filepath.exists())

        loaded = client.load_candles_from_json(filepath)
        self.assertEqual(len(loaded), 5)
        self.assertEqual(loaded[0].open_time, base_time)
        self.assertEqual(loaded[-1].close_time, base_time + 4 * step + step - 1)

    def test_v23_detection_inside_cached_data(self):
        """Ensure loading cached data containing V23 timestamps immediately raises SealedWindowViolationError."""
        c_v23 = self.create_mock_candle(V23_START_MS)
        client = BinanceFuturesDataClient(cache_dir=self.cache_dir)
        filepath = self.cache_dir / "tainted_cache.json"

        # Manually write tainted payload
        payload = {
            "symbol": "ETHUSDT",
            "interval": "15m",
            "data": [c_v23.__dict__],
        }
        with open(filepath, "w") as f:
            json.dump(payload, f)

        with self.assertRaises(SealedWindowViolationError):
            client.load_candles_from_json(filepath)


if __name__ == "__main__":
    unittest.main()
