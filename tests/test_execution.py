"""Unit and determinism tests for the Economic Execution Simulator."""

import unittest
from eth_research.execution import ExecutionConfig, ExecutionSimulator, TradeRecord


class TestExecutionSimulator(unittest.TestCase):
    def setUp(self):
        # Deterministic synthetic signals: 2 UP, 2 DOWN
        self.sample_signals = [
            {
                "bar_index": 0,
                "timestamp_utc_ms": 1000000,
                "datetime_utc": "2025-01-01T00:00:00Z",
                "datetime_istanbul": "2025-01-01T03:00:00+03:00",
                "policy_direction": "UP",
                "close_price": 100.0,
                "next_open": 100.0,
                "next_high": 105.0,
                "next_low": 99.0,
                "next_close": 102.0,  # +2.0% gross
                "actual_next_direction": "UP",
            },
            {
                "bar_index": 1,
                "timestamp_utc_ms": 2000000,
                "datetime_utc": "2025-01-01T00:15:00Z",
                "datetime_istanbul": "2025-01-01T03:15:00+03:00",
                "policy_direction": "UP",
                "close_price": 102.0,
                "next_open": 102.0,
                "next_high": 103.0,
                "next_low": 98.0,
                "next_close": 100.0,  # -1.96078% gross
                "actual_next_direction": "DOWN",
            },
            {
                "bar_index": 2,
                "timestamp_utc_ms": 3000000,
                "datetime_utc": "2025-01-01T00:30:00Z",
                "datetime_istanbul": "2025-01-01T03:30:00+03:00",
                "policy_direction": "DOWN",
                "close_price": 100.0,
                "next_open": 100.0,
                "next_high": 101.0,
                "next_low": 96.0,
                "next_close": 98.0,  # +2.0% gross (Short profit)
                "actual_next_direction": "DOWN",
            },
            {
                "bar_index": 3,
                "timestamp_utc_ms": 4000000,
                "datetime_utc": "2025-01-01T00:45:00Z",
                "datetime_istanbul": "2025-01-01T03:45:00+03:00",
                "policy_direction": "DOWN",
                "close_price": 98.0,
                "next_open": 98.0,
                "next_high": 101.0,
                "next_low": 97.5,
                "next_close": 100.0,  # -2.0408% gross (Short loss)
                "actual_next_direction": "UP",
            },
        ]

    def test_zero_cost_simulation(self):
        cfg = ExecutionConfig(
            scenario_name="Zero Cost",
            entry_fee_rate=0.0,
            exit_fee_rate=0.0,
            half_spread_pct=0.0,
            slippage_pct=0.0,
            initial_equity=10000.0,
            position_size_usd=10000.0,
        )
        sim = ExecutionSimulator(cfg)
        trades, summary = sim.simulate(self.sample_signals)

        self.assertEqual(len(trades), 4)
        self.assertEqual(summary.filled_trades, 4)
        self.assertAlmostEqual(trades[0].gross_return_pct, 2.0)
        self.assertAlmostEqual(trades[0].net_return_pct, 2.0)
        self.assertEqual(trades[0].total_cost_pct, 0.0)
        self.assertAlmostEqual(trades[2].gross_return_pct, 2.0)
        self.assertTrue(trades[0].is_hit)
        self.assertFalse(trades[1].is_hit)

    def test_fee_and_friction_deduction(self):
        # 0.05% entry fee, 0.05% exit fee, 0.01% half spread (0.02% roundtrip), 0.01% slippage (0.02% roundtrip)
        # Total frictional drag = 0.05 + 0.05 + 0.02 + 0.02 = 0.14%
        cfg = ExecutionConfig(
            scenario_name="Friction Test",
            entry_fee_rate=0.0005,
            exit_fee_rate=0.0005,
            half_spread_pct=0.0001,
            slippage_pct=0.0001,
            initial_equity=10000.0,
            position_size_usd=10000.0,
        )
        sim = ExecutionSimulator(cfg)
        trades, summary = sim.simulate(self.sample_signals)

        expected_drag = 0.14  # 0.14%
        self.assertAlmostEqual(trades[0].total_cost_pct, expected_drag)
        self.assertAlmostEqual(trades[0].net_return_pct, 2.0 - expected_drag)
        self.assertEqual(summary.filled_trades, 4)
        self.assertAlmostEqual(
            summary.net_pnl_pct, summary.gross_pnl_pct - (4 * expected_drag), places=5
        )

    def test_drawdown_and_equity_tracking(self):
        # Signal 1 wins (+200$), Signal 2 loses (~ -200$)
        cfg = ExecutionConfig(
            scenario_name="DD Test",
            entry_fee_rate=0.0,
            exit_fee_rate=0.0,
            half_spread_pct=0.0,
            slippage_pct=0.0,
            initial_equity=10000.0,
            position_size_usd=10000.0,
        )
        sim = ExecutionSimulator(cfg)
        trades, summary = sim.simulate(self.sample_signals[:2])

        self.assertAlmostEqual(trades[0].equity_after_usd, 10200.0)
        self.assertEqual(trades[0].drawdown_pct, 0.0)
        # Second trade loses roughly 1.96% of 10000 = ~196$
        self.assertTrue(trades[1].drawdown_pct > 0.0)
        self.assertTrue(summary.max_drawdown_pct > 0.0)

    def test_breakeven_cost_calculation(self):
        cfg = ExecutionConfig(
            scenario_name="BE Test",
            entry_fee_rate=0.0,
            exit_fee_rate=0.0,
            half_spread_pct=0.0,
            slippage_pct=0.0,
        )
        sim = ExecutionSimulator(cfg)
        _, summary = sim.simulate(self.sample_signals)
        # Breakeven cost must exactly equal average gross return
        self.assertEqual(summary.breakeven_roundtrip_cost_pct, summary.avg_gross_return_pct)


if __name__ == "__main__":
    unittest.main()
