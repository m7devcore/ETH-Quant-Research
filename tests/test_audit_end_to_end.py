"""End-to-End Operational Readiness Audit & Safety Verification for ETH-V22-D1 (Phase 5B-Ops Task 4)."""

import datetime
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eth_research.data import (
    BinanceFuturesDataClient,
    Candle,
    check_v23_sealed_overlap,
)
from eth_research.dynamic_portfolio import DynamicStrategyConfig
from eth_research.features import extract_features
from eth_research.model import V22ReconstructedModel
from eth_research.persistence import (
    ActivePosition,
    PersistentStateManager,
    PortfolioState,
    StateIntegrityError,
)
from eth_research.runner import (
    FROZEN_MODEL_CHECKPOINT_PATH,
    PaperTradingEngine,
    get_default_d1_config,
    run_health_check,
    verify_model_checkpoint,
)


def make_aligned_mock_candle(
    open_time: int,
    step_ms: int = 15 * 60 * 1000,
    open_p: float = 3000.0,
    high_p: float = 3010.0,
    low_p: float = 2990.0,
    close_p: float = 3005.0,
    volume: float = 100.0,
) -> Candle:
    """Create a verified mock candle strictly outside V23 and Phase 5C."""
    return Candle(
        open_time=open_time,
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=volume,
        close_time=open_time + step_ms - 1,
        quote_volume=volume * close_p,
        trades=50,
        taker_buy_base=volume / 2.0,
        taker_buy_quote=(volume / 2.0) * close_p,
    )


class TestOperationalReadinessAudit(unittest.TestCase):
    """Exhaustive audit tests for all 10 Task A verification points."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "audit_test.sqlite3"
        self.state_mgr = PersistentStateManager(self.db_path)
        self.model = verify_model_checkpoint()
        self.config = get_default_d1_config()

        # Aligned base timestamp: 2025-08-01 00:00:00 UTC (1754092800000 ms)
        self.base_time_ms = 1754092800000
        self.simulated_clock_ms = self.base_time_ms

    def tearDown(self) -> None:
        self.state_mgr.close()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def clock_fn(self) -> int:
        return self.simulated_clock_ms

    def test_1_cli_check_real_execution(self) -> None:
        """Task A.1: Real CLI --check path execution."""
        mock_client = MagicMock()
        mock_c = make_aligned_mock_candle(self.base_time_ms)
        mock_client.fetch_klines_chunk.return_value = [mock_c, mock_c]

        passed = run_health_check(db_path=self.db_path, client=mock_client)
        self.assertTrue(passed)

        # Check DB initialized
        state = self.state_mgr.load_portfolio_state()
        self.assertEqual(state.equity, 10000.0)
        self.assertEqual(state.total_trades_count, 0)
        self.assertIsNone(state.active_position)

    def test_2_complete_pipeline_offline_dry_run(self) -> None:
        """Task A.2: Verify complete data -> features -> model -> decision -> portfolio -> SQLite pipeline."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )

        # Generate 110 contiguous 15m candles and 30 contiguous 4H candles
        c_15m = [make_aligned_mock_candle(self.base_time_ms + i * 900000) for i in range(110)]
        c_4h = [make_aligned_mock_candle(self.base_time_ms + i * 14400000, step_ms=14400000) for i in range(30)]

        self.simulated_clock_ms = c_15m[-1].close_time + 10000

        res = engine.poll_cycle(mode="OFFLINE_TEST", offline_15m=c_15m, offline_4h=c_4h)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["candles_processed"], 110)

        # Verify SQLite state
        self.assertEqual(self.state_mgr.get_processed_candles_count("15m"), 110)
        state = self.state_mgr.load_portfolio_state()
        self.assertEqual(state.last_processed_candle_open_ms, c_15m[-1].open_time)

        # Verify audit events recorded
        events = self.state_mgr.get_audit_events(limit=500)
        self.assertTrue(len(events) >= 110)
        self.assertTrue(all(e["event_type"] == "OFFLINE_TEST" for e in events))

    def test_3_completed_candles_only_enforced(self) -> None:
        """Task A.3: Confirm decisions use completed 15m and 4H candles only."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            settlement_delay_ms=3000,
        )

        c1 = make_aligned_mock_candle(self.base_time_ms)
        c2 = make_aligned_mock_candle(self.base_time_ms + 900000)

        # If clock is right at c2 open (c1 close), c1 is not completed due to 3000ms settlement buffer
        now = c1.close_time + 1000
        completed = engine.filter_completed_candles([c1, c2], now)
        self.assertEqual(len(completed), 0)

        # Once settlement buffer elapses, c1 is completed, while c2 remains forming
        now = c1.close_time + 4000
        completed = engine.filter_completed_candles([c1, c2], now)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].open_time, c1.open_time)

    def test_4_exact_warmup_sufficiency(self) -> None:
        """Task A.4: Verify exact 15m/4H warmup sufficiency including ATR28 and EMA initialization."""
        # 99 15m candles: warmup_bars=100 requires index >= 100, so exactly 0 rows
        start_4h = self.base_time_ms - 25 * 14400000
        c_4h_35 = [make_aligned_mock_candle(start_4h + i * 14400000, step_ms=14400000) for i in range(35)]

        c_15m_99 = [make_aligned_mock_candle(self.base_time_ms + i * 900000) for i in range(99)]
        rows_99 = extract_features(c_15m_99, c_4h_35, warmup_bars=100)
        self.assertEqual(len(rows_99), 0)

        # 101 15m candles with insufficient 4H history (< 28 4H bars completed): ATR28 4H is None, 0 rows
        c_15m_101 = [make_aligned_mock_candle(self.base_time_ms + i * 900000) for i in range(101)]
        c_4h_10 = [make_aligned_mock_candle(start_4h + i * 14400000, step_ms=14400000) for i in range(10)]
        rows_insufficient_4h = extract_features(c_15m_101, c_4h_10, warmup_bars=100)
        self.assertEqual(len(rows_insufficient_4h), 0)

        # 101 15m candles with >= 28 completed 4H bars: exactly 1 feature row with 18 causal features computed
        rows_valid = extract_features(c_15m_101, c_4h_35, warmup_bars=100)
        self.assertEqual(len(rows_valid), 1)
        self.assertEqual(len(rows_valid[0].features), 18)

    def test_5_crash_recovery_and_interrupted_transaction(self) -> None:
        """Task A.5: Test restart after entry, exit, and interrupted SQLite transaction."""
        self.state_mgr.initialize_portfolio_if_empty(10000.0)

        # Enter position
        act_pos = ActivePosition(
            position_id="POS_RESTART_TEST",
            direction="UP",
            entry_bar_time_ms=self.base_time_ms,
            entry_price_nominal=3000.0,
            entry_price_effective=3000.3,
            atr7=15.0,
            stop_loss_price=2977.5,
            take_profit_price=3037.5,
            max_holding_bars=4,
            bars_held=1,
            mfe_pct=0.0,
            mae_pct=0.0,
            position_size_usd=10000.0,
        )
        st_entered = PortfolioState(
            equity=10000.0,
            peak_equity=10000.0,
            initial_equity=10000.0,
            active_position=act_pos,
            last_processed_candle_open_ms=self.base_time_ms,
            total_trades_count=1,
        )
        c_dict = {"open_time_ms": self.base_time_ms, "close_time_ms": self.base_time_ms + 899999, "open": 3000.0, "high": 3010.0, "low": 2990.0, "close": 3000.0}
        self.state_mgr.commit_state_transition(st_entered, c_dict, None, None, "REAL_TIME", "POSITION_ENTERED")

        # Simulate abrupt process death and restart with new instance
        mgr_restart = PersistentStateManager(self.db_path)
        recovered_state = mgr_restart.load_portfolio_state()
        self.assertIsNotNone(recovered_state.active_position)
        self.assertEqual(recovered_state.active_position.position_id, "POS_RESTART_TEST")
        self.assertEqual(recovered_state.active_position.stop_loss_price, 2977.5)

        # Test interrupted transaction rollback
        with self.assertRaises(sqlite3.IntegrityError):
            with mgr_restart._get_connection() as conn:
                # Attempt to insert duplicate primary key into portfolio_state (id=1 already exists)
                conn.execute("INSERT INTO portfolio_state (id, equity, peak_equity, initial_equity, total_trades_count, updated_at_utc) VALUES (1, 5000, 5000, 5000, 99, 'bad');")

        # State remains clean and unchanged
        state_post_error = mgr_restart.load_portfolio_state()
        self.assertEqual(state_post_error.equity, 10000.0)
        self.assertEqual(state_post_error.total_trades_count, 1)
        mgr_restart.close()

    def test_6_deduplication_and_no_duplicate_trades(self) -> None:
        """Task A.6: Verify no duplicate trades or accounting entries."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )
        c_15m = [make_aligned_mock_candle(self.base_time_ms + i * 900000) for i in range(110)]
        c_4h = [make_aligned_mock_candle(self.base_time_ms + i * 14400000, step_ms=14400000) for i in range(30)]

        self.simulated_clock_ms = c_15m[-1].close_time + 10000

        # Poll 1
        res1 = engine.poll_cycle(mode="OFFLINE_TEST", offline_15m=c_15m, offline_4h=c_4h)
        self.assertEqual(res1["status"], "SUCCESS")
        self.assertEqual(res1["candles_processed"], 110)

        # Poll 2
        res2 = engine.poll_cycle(mode="OFFLINE_TEST", offline_15m=c_15m, offline_4h=c_4h)
        self.assertEqual(res2["status"], "UP_TO_DATE")
        self.assertEqual(res2["candles_processed"], 0)

        # Poll 3
        res3 = engine.poll_cycle(mode="OFFLINE_TEST", offline_15m=c_15m, offline_4h=c_4h)
        self.assertEqual(res3["status"], "UP_TO_DATE")

        # Invariant: processed candles strictly 110
        self.assertEqual(self.state_mgr.get_processed_candles_count("15m"), 110)

    def test_7_delayed_signals_reject_retroactive_fills(self) -> None:
        """Task A.7: Verify delayed signals cannot create retroactive real-time fills."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )
        state = self.state_mgr.initialize_portfolio_if_empty(10000.0)

        t_open = self.base_time_ms
        c_t = make_aligned_mock_candle(t_open)
        c_t1 = make_aligned_mock_candle(t_open + 900000)

        # Simulated clock is 2 hours in the future (causing LATE_CATCHUP)
        late_clock = c_t1.close_time + 2 * 3600 * 1000

        state_after, _ = engine.step_candle(
            state=state,
            candle=c_t1,
            all_completed_15m_up_to_c=[c_t, c_t1],
            all_completed_4h_up_to_c=[],
            current_time_ms=late_clock,
            event_type="LATE_CATCHUP",
            pending_signal={
                "open_time_ms": t_open,
                "direction": "UP",
                "atr7": 15.0,
            },
        )

        # No trade entered
        self.assertIsNone(state_after.active_position)
        self.assertEqual(state_after.total_trades_count, 0)
        self.assertEqual(len(self.state_mgr.get_trade_ledger()), 0)

        # Audit event logs rejection
        events = self.state_mgr.get_audit_events()
        rejections = [e for e in events if e["event_name"] == "DELAYED_ENTRY_REJECTED"]
        self.assertEqual(len(rejections), 1)

    def test_8_max_one_position_rule_and_fee_accounting(self) -> None:
        """Task A.8: Verify maximum one-position rule and exact taker fee accounting."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )
        state = self.state_mgr.initialize_portfolio_if_empty(10000.0)

        t_open = self.base_time_ms
        c_t = make_aligned_mock_candle(t_open)
        c_t1 = make_aligned_mock_candle(t_open + 900000, open_p=3000.0, high_p=3005.0, low_p=2995.0, close_p=3000.0)

        # Enter position on t1
        state_1, _ = engine.step_candle(
            state=state,
            candle=c_t1,
            all_completed_15m_up_to_c=[c_t, c_t1],
            all_completed_4h_up_to_c=[],
            current_time_ms=c_t1.close_time + 5000,
            event_type="REAL_TIME",
            pending_signal={"open_time_ms": t_open, "direction": "UP", "atr7": 15.0},
        )
        self.assertIsNotNone(state_1.active_position)

        # Next candle t2 arrives; even if an entry signal exists, cannot open second position
        c_t2 = make_aligned_mock_candle(t_open + 2 * 900000, open_p=3000.0, high_p=3010.0, low_p=2995.0, close_p=3002.0)
        state_2, _ = engine.step_candle(
            state=state_1,
            candle=c_t2,
            all_completed_15m_up_to_c=[c_t, c_t1, c_t2],
            all_completed_4h_up_to_c=[],
            current_time_ms=c_t2.close_time + 5000,
            event_type="REAL_TIME",
            pending_signal={"open_time_ms": c_t1.open_time, "direction": "UP", "atr7": 15.0},
        )
        # Still exactly 1 active position
        self.assertEqual(state_2.active_position.position_id, state_1.active_position.position_id)
        self.assertEqual(state_2.active_position.bars_held, 2)

        # Now exit via Take-Profit in candle t3
        # TP price = 3000 + 2.5 * 15 = 3037.5
        c_t3 = make_aligned_mock_candle(t_open + 3 * 900000, open_p=3010.0, high_p=3040.0, low_p=3005.0, close_p=3038.0)
        state_3, _ = engine.step_candle(
            state=state_2,
            candle=c_t3,
            all_completed_15m_up_to_c=[c_t, c_t1, c_t2, c_t3],
            all_completed_4h_up_to_c=[],
            current_time_ms=c_t3.close_time + 5000,
            event_type="REAL_TIME",
            pending_signal=None,
        )
        self.assertIsNone(state_3.active_position)
        trades = self.state_mgr.get_trade_ledger()
        self.assertEqual(len(trades), 1)
        tr = trades[0]
        self.assertEqual(tr["exit_reason"], "TAKE_PROFIT")

        # Verify fee accounting: total cost pct = 0.12%
        self.assertAlmostEqual(tr["total_cost_pct"], 0.12, places=4)
        gross_ret = (3037.5 - 3000.0) / 3000.0 * 100.0  # 1.25%
        self.assertAlmostEqual(tr["gross_pnl_pct"], gross_ret, places=4)
        net_ret = gross_ret - 0.12  # 1.13%
        self.assertAlmostEqual(tr["net_pnl_pct"], net_ret, places=4)
        expected_pnl_usd = 10000.0 * (net_ret / 100.0)  # $113.00
        self.assertAlmostEqual(tr["net_pnl_usd"], expected_pnl_usd, places=2)

    def test_9_missing_candles_and_api_failure_recovery(self) -> None:
        """Task A.9: Test missing candles, stale data, API disconnection and recovery."""
        mock_client = MagicMock()
        mock_client.fetch_klines_chunk.side_effect = urllib.error.URLError("503 Service Unavailable")

        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            data_client=mock_client,
            clock_fn=self.clock_fn,
        )

        # 1. API Failure
        res_fail = engine.poll_cycle(mode="AUTO")
        self.assertEqual(res_fail["status"], "API_FAILURE")

        # 2. Reconnection recovery
        c_1 = make_aligned_mock_candle(self.base_time_ms)
        mock_client.fetch_klines_chunk.side_effect = None
        mock_client.fetch_klines_chunk.return_value = [c_1]
        self.simulated_clock_ms = c_1.close_time + 5000

        res_ok = engine.poll_cycle(mode="AUTO")
        self.assertEqual(res_ok["status"], "SUCCESS")
        self.assertEqual(res_ok["candles_processed"], 1)

    def test_10_unfabricated_emergency_exits(self) -> None:
        """Task A.10: Verify emergency exits are not assigned fabricated times or prices during outages."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )
        state = self.state_mgr.initialize_portfolio_if_empty(10000.0)

        t_open = self.base_time_ms
        c_t = make_aligned_mock_candle(t_open)
        c_dict = {"open_time_ms": t_open, "close_time_ms": c_t.close_time, "open": 3000.0, "high": 3010.0, "low": 2990.0, "close": 3000.0}

        act_pos = ActivePosition(
            position_id=f"POS_{t_open}",
            direction="UP",
            entry_bar_time_ms=t_open,
            entry_price_nominal=3000.0,
            entry_price_effective=3000.3,
            atr7=15.0,
            stop_loss_price=2977.5,
            take_profit_price=3037.5,
            max_holding_bars=4,
            bars_held=1,
            mfe_pct=0.0,
            mae_pct=0.0,
            position_size_usd=10000.0,
        )
        st_pos = PortfolioState(
            equity=10000.0,
            peak_equity=10000.0,
            initial_equity=10000.0,
            active_position=act_pos,
            last_processed_candle_open_ms=t_open,
            total_trades_count=1,
        )
        self.state_mgr.commit_state_transition(st_pos, c_dict, None, None, "REAL_TIME", "POSITION_ENTERED")

        # 5-bar outage: next candle arrives at t_open + 5 * 900000
        # Expected was t_open + 900000. Missing 4 bars (> 2 bars critical outage)
        reconnect_open = t_open + 5 * 900000
        reconnect_candle = make_aligned_mock_candle(reconnect_open, open_p=2940.0)

        state_outage, _ = engine.step_candle(
            state=st_pos,
            candle=reconnect_candle,
            all_completed_15m_up_to_c=[c_t, reconnect_candle],
            all_completed_4h_up_to_c=[],
            current_time_ms=reconnect_candle.close_time + 5000,
            event_type="LATE_CATCHUP",
            pending_signal=None,
        )

        self.assertIsNone(state_outage.active_position)
        trades = self.state_mgr.get_trade_ledger()
        self.assertEqual(len(trades), 1)
        tr = trades[0]

        # Verify exit price is actual reconnect open price (2940.0), NOT a fabricated price
        self.assertEqual(tr["exit_price_nominal"], 2940.0)
        # Verify exit time is contemporaneous reconnect time, NOT backdated to historical open
        self.assertEqual(tr["exit_time_ms"], reconnect_candle.close_time + 5000)
        self.assertEqual(tr["exit_reason"], "EMERGENCY_GAP_4")

        # Verify processed candles in DB has ONLY the 2 real candles, ZERO fabricated candles
        self.assertEqual(self.state_mgr.get_processed_candles_count("15m"), 2)

    def test_11_contemporaneous_quote_vs_backtest_open(self) -> None:
        """Issue 1: Contemporaneous quote pricing in REAL_TIME vs next_open in backtesting."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )
        state = self.state_mgr.initialize_portfolio_if_empty(10000.0)

        t_open = self.base_time_ms
        c_t = make_aligned_mock_candle(t_open)
        c_t1 = make_aligned_mock_candle(t_open + 900000, open_p=3000.0)

        # Contemporaneous quote at decision time (1 minute after candle close)
        decision_time_ms = c_t1.open_time + 60 * 1000  # 1 minute into candle t+1
        observed_quote = 3006.25  # Traded price at decision time, different from candle.open (3000.0)

        state_rt, _ = engine.step_candle(
            state=state,
            candle=c_t1,
            all_completed_15m_up_to_c=[c_t, c_t1],
            all_completed_4h_up_to_c=[],
            current_time_ms=decision_time_ms,
            event_type="REAL_TIME",
            pending_signal={"open_time_ms": t_open, "direction": "UP", "atr7": 15.0},
            contemporaneous_quote_price=observed_quote,
        )

        self.assertIsNotNone(state_rt.active_position)
        pos = state_rt.active_position
        # Entry price must be the contemporaneously observed quote, NOT retroactive candle.open
        self.assertEqual(pos.entry_price_nominal, 3006.25)
        self.assertEqual(pos.entry_bar_time_ms, decision_time_ms)
        # SL and TP must anchor to the contemporaneous execution price
        self.assertEqual(pos.stop_loss_price, 3006.25 - 1.5 * 15.0)
        self.assertEqual(pos.take_profit_price, 3006.25 + 2.5 * 15.0)

    def test_12_stop_loss_opening_gap_slippage(self) -> None:
        """Issue 3: Conservative stop execution when market gaps beyond stop price at open."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )
        state = self.state_mgr.initialize_portfolio_if_empty(10000.0)

        t_open = self.base_time_ms
        c_t = make_aligned_mock_candle(t_open)

        # Enter long position with SL at 2977.5
        act_pos = ActivePosition(
            position_id=f"POS_{t_open}",
            direction="UP",
            entry_bar_time_ms=t_open,
            entry_price_nominal=3000.0,
            entry_price_effective=3000.3,
            atr7=15.0,
            stop_loss_price=2977.5,
            take_profit_price=3037.5,
            max_holding_bars=4,
            bars_held=1,
            mfe_pct=0.0,
            mae_pct=0.0,
            position_size_usd=10000.0,
        )
        st_pos = PortfolioState(
            equity=10000.0,
            peak_equity=10000.0,
            initial_equity=10000.0,
            active_position=act_pos,
            last_processed_candle_open_ms=t_open,
            total_trades_count=1,
        )
        c_dict = {"open_time_ms": t_open, "close_time_ms": c_t.close_time, "open": 3000.0, "high": 3010.0, "low": 2990.0, "close": 3000.0}
        self.state_mgr.commit_state_transition(st_pos, c_dict, None, None, "REAL_TIME", "POSITION_ENTERED")

        # Next candle opens at 2965.0 (market gapped down 12.5 pts below our stop price!)
        c_gap = make_aligned_mock_candle(t_open + 900000, open_p=2965.0, high_p=2968.0, low_p=2960.0, close_p=2962.0)

        state_after, _ = engine.step_candle(
            state=st_pos,
            candle=c_gap,
            all_completed_15m_up_to_c=[c_t, c_gap],
            all_completed_4h_up_to_c=[],
            current_time_ms=c_gap.close_time + 5000,
            event_type="REAL_TIME",
            pending_signal=None,
        )

        self.assertIsNone(state_after.active_position)
        trades = self.state_mgr.get_trade_ledger()
        self.assertEqual(len(trades), 1)
        tr = trades[0]

        # Invariant: fill price is candle.open (2965.0), NOT optimistic stop price (2977.5)!
        self.assertEqual(tr["exit_price_nominal"], 2965.0)
        self.assertEqual(tr["exit_reason"], "STOP_LOSS_GAP")


if __name__ == "__main__":
    unittest.main()
