"""Unit and causality tests for the 18-feature extraction pipeline."""

import unittest
from eth_research.data import Candle, SealedWindowViolationError
from eth_research.features import (
    calculate_true_range,
    calculate_atr_series,
    calculate_ema_series,
    calculate_er_series,
    calculate_midpoint_32_series,
    extract_features,
)


def create_dummy_candle(
    open_time: int,
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    volume: float = 100.0,
    interval_ms: int = 15 * 60 * 1000,
) -> Candle:
    return Candle(
        open_time=open_time,
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=volume,
        close_time=open_time + interval_ms - 1,
        quote_volume=volume * close_p,
        trades=50,
        taker_buy_base=volume / 2,
        taker_buy_quote=(volume * close_p) / 2,
    )


class TestFeaturePipeline(unittest.TestCase):
    def test_true_range_calculation(self):
        # Bar 1 (no prev)
        c1 = create_dummy_candle(0, 100.0, 105.0, 95.0, 102.0)
        tr1 = calculate_true_range(c1, None)
        self.assertEqual(tr1, 10.0)

        # Bar 2 with gap up
        c2 = create_dummy_candle(900000, 108.0, 112.0, 107.0, 110.0)
        tr2 = calculate_true_range(c2, c1)
        # H - L = 5, |H - C_prev| = |112 - 102| = 10, |L - C_prev| = |107 - 102| = 5
        self.assertEqual(tr2, 10.0)

    def test_atr_series(self):
        candles = []
        for i in range(10):
            candles.append(create_dummy_candle(i * 900000, 100.0, 102.0, 98.0, 100.0))
        atr = calculate_atr_series(candles, 7)
        self.assertIsNone(atr[5])
        self.assertIsNotNone(atr[6])
        self.assertAlmostEqual(atr[6], 4.0)

    def test_ema_series(self):
        values = [10.0, 11.0, 12.0, 13.0, 14.0]
        ema = calculate_ema_series(values, 3)
        # period 3 SMA for index 2: (10 + 11 + 12)/3 = 11.0
        self.assertIsNone(ema[0])
        self.assertIsNone(ema[1])
        self.assertAlmostEqual(ema[2], 11.0)
        # index 3: alpha = 2 / (3 + 1) = 0.5; ema[3] = 0.5 * 13 + 0.5 * 11.0 = 12.0
        self.assertAlmostEqual(ema[3], 12.0)

    def test_er_series(self):
        # Monotonic line: ER should be 1.0
        candles = [
            create_dummy_candle(i * 900000, 100.0 + i, 100.0 + i + 0.5, 100.0 + i - 0.5, 100.0 + i)
            for i in range(10)
        ]
        er = calculate_er_series(candles, 6)
        self.assertIsNone(er[5])
        self.assertAlmostEqual(er[6], 1.0)

    def test_midpoint_32_series(self):
        candles = []
        for i in range(40):
            candles.append(create_dummy_candle(i * 900000, 100.0, 100.0 + i, 90.0, 95.0))
        mid = calculate_midpoint_32_series(candles)
        self.assertIsNone(mid[30])
        # At index 31: window 0..31. Max high is 100 + 31 = 131. Min low is 90. Midpoint = (131 + 90)/2 = 110.5
        self.assertAlmostEqual(mid[31], 110.5)

    def test_causality_and_no_future_leakage(self):
        # 15m candles: 150 candles * 15m = 2250 minutes = 37.5 hours.
        # 4H candles require period 28 for ATR28 -> at least 35 4H candles (140 hours).
        # We need historical 4H candles covering prior period for 4H warmup.
        start_t = 1600000000000  # Year 2020 UTC
        four_h_step = 14400000
        fifteen_m_step = 900000

        # Create 50 4H candles starting earlier so 4H ATR28 and ER6 are warmed up
        start_4h_t = start_t - 40 * four_h_step
        candles_4h = [
            create_dummy_candle(
                start_4h_t + j * four_h_step,
                2000.0 + (j % 10),
                2010.0 + (j % 10),
                1990.0 + (j % 10),
                2002.0 + (j % 10),
                interval_ms=four_h_step,
            )
            for j in range(50)
        ]

        candles_15m = [
            create_dummy_candle(
                start_t + i * fifteen_m_step,
                2000.0 + (i % 5),
                2005.0 + (i % 5),
                1995.0,
                2001.0 + (i % 5),
            )
            for i in range(150)
        ]

        rows = extract_features(candles_15m, candles_4h, warmup_bars=100)
        self.assertTrue(len(rows) > 0)

        for row in rows:
            # 18 features exactly
            self.assertEqual(len(row.features), 18)
            for f in row.features:
                self.assertTrue(isinstance(f, float))

            # The label corresponds to t+1 direction (next candle close > next candle open)
            if row.index + 1 < len(candles_15m):
                next_c = candles_15m[row.index + 1]
                expected_label = 1 if next_c.close > next_c.open else 0
                self.assertEqual(row.label, expected_label)
                self.assertEqual(row.next_close, next_c.close)
            else:
                self.assertIsNone(row.label)

    def test_v23_sealed_gate_blocks_feature_extraction(self):
        # If candles touch V23 window, extract_features must raise SealedWindowViolationError
        v23_start = 1751662800000
        candles_15m = [
            create_dummy_candle(v23_start + i * 900000, 2000.0, 2005.0, 1995.0, 2000.0)
            for i in range(5)
        ]
        candles_4h = [
            create_dummy_candle(v23_start, 2000.0, 2010.0, 1990.0, 2000.0, interval_ms=14400000)
        ]
        with self.assertRaises(SealedWindowViolationError):
            extract_features(candles_15m, candles_4h, warmup_bars=0)


if __name__ == "__main__":
    unittest.main()
