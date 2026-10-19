"""Unit tests for causal dynamic order state transitions, ambiguity resolution, and portfolio integrity."""

import sys
from pathlib import Path

# Ensure src is on python path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import unittest
from eth_research.data import Candle
from eth_research.dynamic_portfolio import (
    CausalDynamicPortfolioSimulator,
    DynamicStrategyConfig,
)


class TestDynamicPortfolioSimulator(unittest.TestCase):
    def setUp(self):
        # 10 candles: bar 0 to 9
        # 15m intervals (900000 ms)
        self.candles = []
        base_time = 1000000000
        for i in range(10):
            t_open = base_time + i * 900000
            t_close = t_open + 899999
            # Baseline prices: 2000.0 flat
            self.candles.append(
                Candle(
                    open_time=t_open,
                    open=2000.0,
                    high=2010.0,
                    low=1990.0,
                    close=2000.0,
                    volume=100.0,
                    close_time=t_close,
                    quote_volume=200000.0,
                    trades=100,
                    taker_buy_base=50.0,
                    taker_buy_quote=100000.0,
                )
            )

    def test_conservative_intrabar_tie_breaking(self):
        # In bar 1 (entry bar), price spikes to 2050 (TP) and crashes to 1950 (SL)
        # Strategy: entry 2000, SL at 1980 (dist 20), TP at 2030 (dist 30)
        self.candles[1] = Candle(
            open_time=self.candles[1].open_time,
            open=2000.0,
            high=2050.0,  # exceeds TP 2030
            low=1950.0,   # exceeds SL 1980
            close=2020.0,
            volume=100.0,
            close_time=self.candles[1].close_time,
            quote_volume=200000.0,
            trades=100,
            taker_buy_base=50.0,
            taker_buy_quote=100000.0,
        )

        signal = {
            "timestamp_utc_ms": self.candles[0].open_time,
            "policy_direction": "UP",
            "p_avg": 0.58,
            "expert_spread": 0.02,
            "min_rms_distance": 1.0,
            "atr7": 13.33, # 1.5 * ATR7 = 20 (SL = 1980), 2.5 * ATR7 = 33.3 (TP = 2033.3)
            "close_price": 2000.0,
        }

        cfg = DynamicStrategyConfig(
            strategy_name="Tie Break Test",
            atr_stop_multiplier=1.5,
            atr_profit_multiplier=2.5,
            max_holding_bars=4,
            entry_fee_rate=0.0,
            exit_fee_rate=0.0,
            half_spread_pct=0.0,
            slippage_pct=0.0,
        )
        sim = CausalDynamicPortfolioSimulator(cfg)
        trades, summary = sim.simulate([signal], self.candles)

        self.assertEqual(len(trades), 1)
        # Critical verification: SL must be assumed to hit first!
        self.assertEqual(trades[0].exit_reason, "STOP_LOSS")
        self.assertEqual(summary.sl_exit_count, 1)
        self.assertEqual(summary.tp_exit_count, 0)

    def test_single_position_integrity_rejects_overlapping_signal(self):
        # Two signals generated back-to-back at bar 0 and bar 1
        # Signal 1 enters at bar 1 and holds until bar 4 (max hold)
        # Signal 2 enters at bar 2 -> MUST BE REJECTED because portfolio is occupied!
        sig1 = {
            "timestamp_utc_ms": self.candles[0].open_time,
            "policy_direction": "UP",
            "p_avg": 0.58,
            "expert_spread": 0.02,
            "min_rms_distance": 1.0,
            "atr7": 10.0,
            "close_price": 2000.0,
        }
        sig2 = {
            "timestamp_utc_ms": self.candles[1].open_time,
            "policy_direction": "UP",
            "p_avg": 0.59,
            "expert_spread": 0.02,
            "min_rms_distance": 1.0,
            "atr7": 10.0,
            "close_price": 2000.0,
        }

        cfg = DynamicStrategyConfig(
            strategy_name="Overlap Rejection Test",
            max_holding_bars=4,
            entry_fee_rate=0.0,
            exit_fee_rate=0.0,
            half_spread_pct=0.0,
            slippage_pct=0.0,
        )
        sim = CausalDynamicPortfolioSimulator(cfg)
        trades, summary = sim.simulate([sig1, sig2], self.candles)

        self.assertEqual(len(trades), 1)
        self.assertEqual(summary.executed_trades, 1)
        self.assertEqual(summary.signals_rejected_portfolio_busy, 1)


if __name__ == "__main__":
    unittest.main()
