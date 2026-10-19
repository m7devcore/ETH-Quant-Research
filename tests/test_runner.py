"""Deterministic Tests for Persistent State Manager and Paper-Trading Runner (Phase 5B-Ops Task 3B)."""

import datetime
import os
import sqlite3
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from eth_research.data import (
    BinanceFuturesDataClient,
    Candle,
    check_v23_sealed_overlap,
)
from eth_research.dynamic_portfolio import DynamicStrategyConfig
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


def make_mock_candle(
    open_time: int,
    step_ms: int = 15 * 60 * 1000,
    open_p: float = 3000.0,
    high_p: float = 3010.0,
    low_p: float = 2990.0,
    close_p: float = 3005.0,
    volume: float = 100.0,
) -> Candle:
    """Construct an aligned mock candle outside V23 and Phase 5C."""
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


class TestPersistentStateManager(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_state.sqlite3"
        self.state_manager = PersistentStateManager(self.db_path)

    def tearDown(self) -> None:
        self.state_manager.close()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_initial_state_persistence(self) -> None:
        """Verify empty DB properly initializes and subsequent loads match."""
        with self.assertRaises(StateIntegrityError):
            self.state_manager.load_portfolio_state()

        state_1 = self.state_manager.initialize_portfolio_if_empty(initial_equity=12000.0)
        self.assertEqual(state_1.equity, 12000.0)
        self.assertIsNone(state_1.active_position)

        state_2 = self.state_manager.load_portfolio_state()
        self.assertEqual(state_2.equity, 12000.0)
        self.assertEqual(state_2.total_trades_count, 0)

        events = self.state_manager.get_audit_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_name"], "PORTFOLIO_INITIALIZED")
        self.assertEqual(events[0]["event_type"], "OFFLINE_TEST")

    def test_restart_and_state_recovery(self) -> None:
        """Verify that recreating the state manager on an existing file preserves data."""
        self.state_manager.initialize_portfolio_if_empty(initial_equity=10000.0)

        with self.state_manager._get_connection() as conn:
            conn.execute(
                "UPDATE portfolio_state SET equity = 10500.0, total_trades_count = 1 WHERE id = 1"
            )

        new_manager = PersistentStateManager(self.db_path)
        recovered_state = new_manager.load_portfolio_state()

        self.assertEqual(recovered_state.equity, 10500.0)
        self.assertEqual(recovered_state.total_trades_count, 1)

    def test_corrupted_persistent_state(self) -> None:
        """Ensure invalid or deleted portfolio triggers exception, NOT a silent reset."""
        self.state_manager.initialize_portfolio_if_empty()

        with self.state_manager._get_connection() as conn:
            conn.execute("UPDATE portfolio_state SET equity = -500.0 WHERE id = 1")

        with self.assertRaisesRegex(StateIntegrityError, "Corrupted equity values"):
            self.state_manager.load_portfolio_state()

        with self.state_manager._get_connection() as conn:
            conn.execute("DELETE FROM portfolio_state")

        with self.assertRaisesRegex(StateIntegrityError, "Portfolio state row does not exist"):
            self.state_manager.load_portfolio_state()

    def test_atomic_transaction_and_duplicate_prevention(self) -> None:
        """Verify atomic commit_state_transition idempotency and constraints."""
        self.state_manager.initialize_portfolio_if_empty(10000.0)

        st = PortfolioState(
            equity=10000.0,
            peak_equity=10000.0,
            initial_equity=10000.0,
            active_position=None,
            last_processed_candle_open_ms=1000,
            total_trades_count=0,
        )
        c_dict = {
            "timeframe": "15m",
            "open_time_ms": 1000,
            "close_time_ms": 1900,
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
        }
        sig = {
            "open_time_ms": 1000,
            "close_price": 1,
            "atr7": 1,
            "p_avg": 0.5,
            "spread": 0,
            "min_distance": 0,
            "direction": "NO_TRADE",
            "reason": "NO",
        }

        self.state_manager.commit_state_transition(st, c_dict, sig, None, "OFFLINE_TEST", "CANDLE_PROCESSED")

        events = self.state_manager.get_audit_events()
        self.assertEqual(len(events), 2)  # Init + Candle

        # Try duplicating exact candle
        self.state_manager.commit_state_transition(st, c_dict, sig, None, "OFFLINE_TEST", "CANDLE_PROCESSED")

        events2 = self.state_manager.get_audit_events()
        self.assertEqual(len(events2), 2)

    def test_audit_event_types(self) -> None:
        """Ensure invalid event types are blocked."""
        with self.assertRaisesRegex(ValueError, "Invalid event_type"):
            self.state_manager.record_audit_event(
                event_type="INVALID_TYPE",
                event_name="TEST_EVENT",
                candle_open_ms=None,
                payload={},
            )

        self.state_manager.record_audit_event("LATE_CATCHUP", "DELAYED_SIGNAL", 20000, {})
        events = self.state_manager.get_audit_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "LATE_CATCHUP")


class TestPaperTradingEngineOperational(unittest.TestCase):
    """Operational unit tests with mocked clocks and market data for Task 3B."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "engine_test.sqlite3"
        self.state_mgr = PersistentStateManager(self.db_path)
        self.model = verify_model_checkpoint()
        self.config = get_default_d1_config()

        # Base timestamp: 2025-08-01 00:00:00 UTC (1754092800000 ms)
        # Fully aligned to 15m and 4H, strictly outside sealed V23 and Phase 5C
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

    def test_filter_completed_candles_with_settlement_buffer(self) -> None:
        """Ensure forming candles and settlement delay are respected."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
            settlement_delay_ms=3000,
        )

        c1 = make_mock_candle(self.base_time_ms)  # closes at base + 900000 - 1
        c2 = make_mock_candle(self.base_time_ms + 900000)

        # Clock is 1 second after c1 close (settlement delay is 3s, so not yet completed)
        now = c1.close_time + 1000
        completed = engine.filter_completed_candles([c1, c2], now)
        self.assertEqual(len(completed), 0)

        # Clock is 4 seconds after c1 close (now completed)
        now = c1.close_time + 4000
        completed = engine.filter_completed_candles([c1, c2], now)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].open_time, c1.open_time)

    def test_insufficient_warmup_records_audit_and_no_trades(self) -> None:
        """Ensure feature evaluation is blocked without 100 15m bars and 28 4H bars."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )

        # Provide only 50 15m candles (< 100) and 5 4H candles (< 28)
        c_15m = [make_mock_candle(self.base_time_ms + i * 900000) for i in range(50)]
        c_4h = [make_mock_candle(self.base_time_ms + i * 14400000, step_ms=14400000) for i in range(5)]

        self.simulated_clock_ms = c_15m[-1].close_time + 10000

        res = engine.poll_cycle(mode="OFFLINE_TEST", offline_15m=c_15m, offline_4h=c_4h)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["candles_processed"], 50)

        state = self.state_mgr.load_portfolio_state()
        self.assertEqual(state.total_trades_count, 0)
        self.assertIsNone(state.active_position)

        # Check audit events for INSUFFICIENT_WARMUP
        events = self.state_mgr.get_audit_events(limit=200)
        warmup_events = [e for e in events if e["event_name"] == "INSUFFICIENT_WARMUP"]
        self.assertTrue(len(warmup_events) > 0)
        self.assertEqual(warmup_events[0]["payload"]["15m_count"], 1)

    def test_delayed_entry_rejected_in_late_catchup(self) -> None:
        """Requirement 9: Reject delayed entries rather than backfilling at historical prices."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )
        state = self.state_mgr.initialize_portfolio_if_empty(10000.0)

        # Simulate a completed candle t that generated an UP entry signal
        t_open = self.base_time_ms
        c_t = make_mock_candle(t_open)

        # Mock signal in DB from bar t
        with self.state_mgr._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO evaluated_signals VALUES (
                    ?, 3000.0, 15.0, 0.60, 0.02, 1.20, 'UP', 'PASSED_ALL_GATES', '2025-08-01T00:00:00Z'
                )
                """,
                (t_open,),
            )

        # Next candle t+1
        c_t1 = make_mock_candle(t_open + 900000)

        # Set clock 2 hours in the future (causing LATE_CATCHUP classification)
        self.simulated_clock_ms = c_t1.close_time + 2 * 60 * 60 * 1000

        state_after, _ = engine.step_candle(
            state=state,
            candle=c_t1,
            all_completed_15m_up_to_c=[c_t, c_t1],
            all_completed_4h_up_to_c=[],
            current_time_ms=self.simulated_clock_ms,
            event_type="LATE_CATCHUP",
            pending_signal={
                "open_time_ms": t_open,
                "direction": "UP",
                "atr7": 15.0,
            },
        )

        # Verify entry was rejected and portfolio remained flat!
        self.assertIsNone(state_after.active_position)
        self.assertEqual(state_after.total_trades_count, 0)
        self.assertEqual(len(self.state_mgr.get_trade_ledger()), 0)

        # Verify audit log recorded DELAYED_ENTRY_REJECTED
        events = self.state_mgr.get_audit_events()
        rejections = [e for e in events if e["event_name"] == "DELAYED_ENTRY_REJECTED"]
        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0]["payload"]["reason"], "MISSED_ENTRY_WINDOW_LATE_CATCHUP")
        self.assertEqual(rejections[0]["event_type"], "LATE_CATCHUP")

    def test_real_time_entry_and_stop_loss_exit(self) -> None:
        """Verify real-time entry and dynamic ATR Stop-Loss execution."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )
        state = self.state_mgr.initialize_portfolio_if_empty(10000.0)

        t_open = self.base_time_ms
        c_t = make_mock_candle(t_open)

        # Candle t+1 arrives in REAL_TIME
        c_t1_open = t_open + 900000
        # Candle t+1 trades between 2995 and 3005 (does not hit SL 2977.5 or TP 3037.5)
        c_t1 = make_mock_candle(c_t1_open, open_p=3000.0, high_p=3005.0, low_p=2995.0, close_p=3000.0)

        clock_now = c_t1.close_time + 5000  # Within real-time window

        state_1, _ = engine.step_candle(
            state=state,
            candle=c_t1,
            all_completed_15m_up_to_c=[c_t, c_t1],
            all_completed_4h_up_to_c=[],
            current_time_ms=clock_now,
            event_type="REAL_TIME",
            pending_signal={
                "open_time_ms": t_open,
                "direction": "UP",
                "atr7": 15.0,
            },
        )

        # Active position should now be entered
        self.assertIsNotNone(state_1.active_position)
        pos = state_1.active_position
        self.assertEqual(pos.direction, "UP")
        self.assertEqual(pos.entry_price_nominal, 3000.0)
        self.assertEqual(pos.stop_loss_price, 3000.0 - 1.5 * 15.0)  # 2977.5
        self.assertEqual(pos.take_profit_price, 3000.0 + 2.5 * 15.0)  # 3037.5

        # Candle t+2 drops to 2970.0 (hits Stop Loss 2977.5)
        c_t2_open = c_t1_open + 900000
        c_t2 = make_mock_candle(c_t2_open, open_p=2990.0, high_p=2992.0, low_p=2970.0, close_p=2972.0)

        state_2, _ = engine.step_candle(
            state=state_1,
            candle=c_t2,
            all_completed_15m_up_to_c=[c_t, c_t1, c_t2],
            all_completed_4h_up_to_c=[],
            current_time_ms=c_t2.close_time + 5000,
            event_type="REAL_TIME",
            pending_signal=None,
        )

        # Position should now be exited via STOP_LOSS
        self.assertIsNone(state_2.active_position)
        self.assertEqual(state_2.total_trades_count, 1)

        trades = self.state_mgr.get_trade_ledger()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["exit_reason"], "STOP_LOSS")
        self.assertEqual(trades[0]["exit_price_nominal"], 2977.5)
        self.assertTrue(trades[0]["net_pnl_usd"] < 0)  # Loss recorded

    def test_critical_gap_triggers_emergency_exit(self) -> None:
        """Requirement 6 & 7: Outage gap (> 2 bars) triggers emergency exit without data fabrication."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )
        state = self.state_mgr.initialize_portfolio_if_empty(10000.0)

        # Create active position in DB
        t_open = self.base_time_ms
        c_t = make_mock_candle(t_open)
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

        # Next candle arrives after a 4-bar outage (gap = 3 missing bars > 2 bars)
        # Expected was t_open + 900000. We jump 4 * 900000
        outage_candle_open = t_open + 4 * 900000
        c_outage = make_mock_candle(outage_candle_open, open_p=2950.0)

        state_after, _ = engine.step_candle(
            state=st_pos,
            candle=c_outage,
            all_completed_15m_up_to_c=[c_t, c_outage],
            all_completed_4h_up_to_c=[],
            current_time_ms=c_outage.close_time + 5000,
            event_type="LATE_CATCHUP",
            pending_signal=None,
        )

        # Active position must be exited immediately due to emergency gap
        self.assertIsNone(state_after.active_position)
        trades = self.state_mgr.get_trade_ledger()
        self.assertEqual(len(trades), 1)
        self.assertTrue(trades[0]["exit_reason"].startswith("EMERGENCY_GAP_"))

        # Verify no fabricated candles exist in DB (only t_open and outage_candle_open)
        self.assertEqual(self.state_mgr.get_processed_candles_count("15m"), 2)

    def test_idempotent_polling(self) -> None:
        """Requirement 5: Duplicate polling cycles must be completely idempotent."""
        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            clock_fn=self.clock_fn,
        )

        # Create 110 completed 15m candles and 30 completed 4H candles
        c_15m = [make_mock_candle(self.base_time_ms + i * 900000) for i in range(110)]
        c_4h = [make_mock_candle(self.base_time_ms + i * 14400000, step_ms=14400000) for i in range(30)]

        self.simulated_clock_ms = c_15m[-1].close_time + 10000

        # Run cycle 1
        res1 = engine.poll_cycle(mode="OFFLINE_TEST", offline_15m=c_15m, offline_4h=c_4h)
        self.assertEqual(res1["status"], "SUCCESS")
        self.assertEqual(res1["candles_processed"], 110)

        # Run cycle 2 with exact same data
        res2 = engine.poll_cycle(mode="OFFLINE_TEST", offline_15m=c_15m, offline_4h=c_4h)
        self.assertEqual(res2["status"], "UP_TO_DATE")
        self.assertEqual(res2["candles_processed"], 0)

        # Total processed candles count must still be 110
        self.assertEqual(self.state_mgr.get_processed_candles_count("15m"), 110)

    def test_api_failure_graceful_handling(self) -> None:
        """Requirement 6: API failures must be handled safely without crashing."""
        mock_client = MagicMock()
        mock_client.fetch_klines_chunk.side_effect = urllib.error.URLError("Simulated connection timeout")

        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            data_client=mock_client,
            clock_fn=self.clock_fn,
        )

        # Execute polling cycle - should NOT raise exception
        res = engine.poll_cycle(mode="AUTO")
        self.assertEqual(res["status"], "API_FAILURE")
        self.assertIn("Simulated connection timeout", res["error"])

        # Check that API_POLL_FAILURE was logged in audit events
        events = self.state_mgr.get_audit_events()
        api_events = [e for e in events if e["event_name"] == "API_POLL_FAILURE"]
        self.assertEqual(len(api_events), 1)

    def test_stale_data_audit_logging(self) -> None:
        """Requirement 6: Stale data (> 30 min old) triggers an audit event."""
        c1 = make_mock_candle(self.base_time_ms)
        mock_client = MagicMock()
        mock_client.fetch_klines_chunk.return_value = [c1]

        # Clock is 3 hours ahead of candle close
        self.simulated_clock_ms = c1.close_time + 3 * 60 * 60 * 1000

        engine = PaperTradingEngine(
            state_mgr=self.state_mgr,
            model=self.model,
            data_client=mock_client,
            clock_fn=self.clock_fn,
        )

        res = engine.poll_cycle(mode="AUTO")
        self.assertEqual(res["status"], "SUCCESS")

        events = self.state_mgr.get_audit_events()
        stale_events = [e for e in events if e["event_name"] == "STALE_DATA_DETECTED"]
        self.assertEqual(len(stale_events), 1)


class TestPaperTradingCLI(unittest.TestCase):
    """Test CLI commands and flags (--check, --offline-dry-run, --run-once)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "cli_test.sqlite3"

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_health_check_passes(self) -> None:
        """Verify --check logic with mocked data client."""
        mock_client = MagicMock()
        mock_candle = make_mock_candle(1754092800000)
        mock_client.fetch_klines_chunk.return_value = [mock_candle, mock_candle]

        passed = run_health_check(db_path=self.db_path, client=mock_client)
        self.assertTrue(passed)

    def test_health_check_fails_on_corrupt_checkpoint(self) -> None:
        """Verify --check fails when model checkpoint is missing or corrupt."""
        bad_path = Path(self.temp_dir.name) / "corrupt_model.json"
        with open(bad_path, "w") as f:
            f.write('{"corrupted": true}')

        mock_client = MagicMock()
        mock_candle = make_mock_candle(1754092800000)
        mock_client.fetch_klines_chunk.return_value = [mock_candle, mock_candle]

        passed = run_health_check(db_path=self.db_path, checkpoint_path=bad_path, client=mock_client)
        self.assertFalse(passed)


if __name__ == "__main__":
    unittest.main()
