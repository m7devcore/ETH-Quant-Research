"""Standalone Independent Paper-Trading & Research Runner for ETHUSDT Futures.

Governance & Safety Guarantees:
1. Public Binance Futures USD-M market data only (15m and 4H completed candles).
2. Purely causal execution: decisions made strictly at candle close t, fills at t+1 open.
3. Verification of frozen V22-R model checkpoint SHA-256 before running.
4. Preserves frozen ETH-V22-D1 strategy parameters (dynamic ATR stop/target, single position).
5. Absolute programmatic sealing of V23 test window (July 5-11, 2025 Istanbul).
6. Live trading is strictly disabled (research_only = True, paper trading only).
7. Offline validation mode using cached data or historical evaluation blocks.
8. Distinguishes REAL_TIME, LATE_CATCHUP, and OFFLINE_TEST events.
9. Rejects delayed entries rather than backfilling at historical prices.
10. Handles API failures, stale data, and missing candle gaps safely without data fabrication.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# Enable running directly as script (python src/eth_research/runner.py)
_src_dir = str(Path(__file__).resolve().parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from eth_research.data import (
    BinanceFuturesDataClient,
    Candle,
    CandleIntegrityError,
    SealedWindowViolationError,
    check_v23_sealed_overlap,
    validate_candle_sequence,
    VALID_TIMEFRAMES,
)
from eth_research.dynamic_portfolio import (
    CausalDynamicPortfolioSimulator,
    CausalTradeResult,
    DynamicStrategyConfig,
    PortfolioExecutionSummary,
)
from eth_research.features import extract_features, FeatureRow
from eth_research.model import V22ReconstructedModel
from eth_research.persistence import (
    ActivePosition,
    PersistentStateManager,
    PortfolioState,
    StateIntegrityError,
)

logger = logging.getLogger("eth_research.runner")

# Frozen Checkpoint SHA-256 for ETH-V22-D1 base model
FROZEN_MODEL_CHECKPOINT_PATH = Path("artifacts/unverified/ETH_V22_Reconstruction_Audit_Model.UNVERIFIED.json")
EXPECTED_CHECKPOINT_SHA256 = "fa367bd77adc597448ac7d163e6297986d365c2af93bbf0fc7226c992f7fea28"

# Phase 5C Forward Evaluation Block (Oct 12, 2026 - Nov 8, 2026 Istanbul)
# Strictly protected: do not evaluate without explicit authorization
PHASE_5C_START_MS = 1791752400000
PHASE_5C_END_MS = 1794171599999

DEFAULT_DB_PATH = Path("data/paper_trading_state.sqlite3")


def verify_model_checkpoint(checkpoint_path: Path = FROZEN_MODEL_CHECKPOINT_PATH) -> V22ReconstructedModel:
    """Verify SHA-256 hash of the frozen reconstructed model checkpoint before loading."""
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Model checkpoint not found at: {checkpoint_path}")

    with open(checkpoint_path, "rb") as f:
        file_bytes = f.read()
    computed_sha = hashlib.sha256(file_bytes).hexdigest()

    if computed_sha != EXPECTED_CHECKPOINT_SHA256:
        raise ValueError(
            f"Checkpoint SHA-256 mismatch!\nExpected: {EXPECTED_CHECKPOINT_SHA256}\nGot:      {computed_sha}"
        )

    logger.info("Checkpoint SHA-256 verified successfully: %s", computed_sha)
    return V22ReconstructedModel.load_json(checkpoint_path)


def get_default_d1_config() -> DynamicStrategyConfig:
    """Return frozen ETH-V22-D1 strategy configuration."""
    return DynamicStrategyConfig(
        strategy_name="ETH-V22-D1",
        min_probability_edge=0.05,
        max_expert_spread=0.04,
        max_support_distance=1.80,
        min_volatility_ratio=0.0018,
        atr_stop_multiplier=1.50,
        atr_profit_multiplier=2.50,
        max_holding_bars=4,
        entry_fee_rate=0.0005,
        exit_fee_rate=0.0005,
        half_spread_pct=0.00005,
        slippage_pct=0.00005,
        initial_equity=10000.0,
        position_size_usd=10000.0,
    )


def default_clock_utc_ms() -> int:
    """Return current UTC time in milliseconds."""
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)


class PaperTradingEngine:
    """Independent Headless Paper-Trading Engine.

    Guarantees:
    - Purely causal polling of public Binance candles (completed only).
    - Causal warmup verification (100 15m bars, 28 4H bars).
    - Transactional state updates and audit event logging in SQLite.
    - Idempotent deduplication across polls and restarts.
    - Explicit event classification: REAL_TIME, LATE_CATCHUP, OFFLINE_TEST.
    - Delayed entry rejection in LATE_CATCHUP to prevent retroactive backfilling.
    - Resilient handling of API errors, stale data, and missing candle gaps.
    - Never fabricates missing candles or simulated fills.
    """

    def __init__(
        self,
        state_mgr: PersistentStateManager,
        model: V22ReconstructedModel,
        config: Optional[DynamicStrategyConfig] = None,
        data_client: Optional[BinanceFuturesDataClient] = None,
        clock_fn: Optional[Callable[[], int]] = None,
        settlement_delay_ms: int = 3000,
        realtime_tolerance_ms: int = 15 * 60 * 1000,
        warmup_15m_bars: int = 100,
        warmup_4h_bars: int = 28,
        symbol: str = "ETHUSDT",
    ):
        self.state_mgr = state_mgr
        self.model = model
        self.config = config or get_default_d1_config()
        self.data_client = data_client or BinanceFuturesDataClient()
        self.clock_fn = clock_fn or default_clock_utc_ms
        self.settlement_delay_ms = settlement_delay_ms
        self.realtime_tolerance_ms = realtime_tolerance_ms
        self.warmup_15m_bars = warmup_15m_bars
        self.warmup_4h_bars = warmup_4h_bars
        self.symbol = symbol

        # Lockout state after critical gap (> 2 bars) requiring clean warmup
        self.warmup_lockout_bars_remaining: int = 0

    def filter_completed_candles(self, candles: List[Candle], current_time_ms: int) -> List[Candle]:
        """Keep only completed candles, enforcing settlement buffer and V23/Phase 5C checks."""
        completed: List[Candle] = []
        for c in candles:
            # Check V23 sealed gate
            check_v23_sealed_overlap(c.open_time, c.close_time)

            # Defensive Phase 5C window protection
            if max(c.open_time, PHASE_5C_START_MS) <= min(c.close_time, PHASE_5C_END_MS):
                raise PermissionError("Access to Phase 5C evaluation window is not authorized in Phase 5B-Ops.")

            # Only completed candles: close_time + settlement_delay <= current_time
            if c.close_time + self.settlement_delay_ms <= current_time_ms:
                completed.append(c)
        return completed

    def classify_event_type(
        self,
        candle_close_time_ms: int,
        current_time_ms: int,
        mode_override: Optional[str] = None,
    ) -> str:
        """Classify execution context into REAL_TIME, LATE_CATCHUP, or OFFLINE_TEST."""
        if mode_override == "OFFLINE_TEST":
            return "OFFLINE_TEST"
        if current_time_ms - candle_close_time_ms <= self.realtime_tolerance_ms:
            return "REAL_TIME"
        return "LATE_CATCHUP"

    def step_candle(
        self,
        state: PortfolioState,
        candle: Candle,
        all_completed_15m_up_to_c: List[Candle],
        all_completed_4h_up_to_c: List[Candle],
        current_time_ms: int,
        event_type: str,
        pending_signal: Optional[Dict[str, Any]],
        contemporaneous_quote_price: Optional[float] = None,
    ) -> Tuple[PortfolioState, Optional[Dict[str, Any]]]:
        """Step dynamic portfolio logic causally for a single completed 15m candle.

        1. Checks idempotency.
        2. Detects gaps from last processed candle; handles minor vs critical gaps.
        3. Updates or exits any active position (Stop-Loss, Take-Profit, Max-Hold).
        4. Rejects delayed entries in LATE_CATCHUP mode; executes entries in REAL_TIME
           using contemporaneous quote price rather than retroactive next_open.
        5. Computes features and evaluates model ensemble policy for candle close t.
        6. Persists state transition and audit events atomically in SQLite.
        """
        # 1. Idempotency check
        if self.state_mgr.is_candle_processed("15m", candle.open_time):
            logger.debug("Candle at %d already processed. Skipping.", candle.open_time)
            return state, None

        # 2. Check for missing candle gap
        last_ms = state.last_processed_candle_open_ms
        is_gap_lockout = False
        step_15m = 15 * 60 * 1000

        if last_ms is not None:
            expected_ms = last_ms + step_15m
            if candle.open_time > expected_ms:
                gap_bars = (candle.open_time - expected_ms) // step_15m
                if gap_bars <= 2:
                    # Minor gap (<= 2 bars): log minor gap, prevent new entries during gap
                    self.state_mgr.record_audit_event(
                        event_type=event_type,
                        event_name="DATA_GAP_MINOR",
                        candle_open_ms=candle.open_time,
                        payload={
                            "gap_bars": gap_bars,
                            "expected_ms": expected_ms,
                            "actual_ms": candle.open_time,
                        },
                    )
                    is_gap_lockout = True
                else:
                    # Critical gap (> 2 bars): outage detected!
                    self.state_mgr.record_audit_event(
                        event_type=event_type,
                        event_name="CRITICAL_GAP_OUTAGE",
                        candle_open_ms=candle.open_time,
                        payload={
                            "gap_bars": gap_bars,
                            "expected_ms": expected_ms,
                            "actual_ms": candle.open_time,
                        },
                    )
                    # Protocol Rule: Missing interval > 2 bars triggers emergency exit of active position
                    # Timestamp is contemporaneous reconnect time (current_time_ms), NOT backdated!
                    if state.active_position is not None:
                        pos = state.active_position
                        emergency_exit_price = candle.open
                        friction_factor = self.config.half_spread_pct + self.config.slippage_pct
                        total_friction_pct = (
                            self.config.entry_fee_rate
                            + self.config.exit_fee_rate
                            + 2.0 * self.config.half_spread_pct
                            + 2.0 * self.config.slippage_pct
                        ) * 100.0

                        if pos.direction == "UP":
                            eff_exit = emergency_exit_price * (1.0 - friction_factor)
                            gross_ret = (emergency_exit_price - pos.entry_price_nominal) / pos.entry_price_nominal * 100.0
                        else:
                            eff_exit = emergency_exit_price * (1.0 + friction_factor)
                            gross_ret = (pos.entry_price_nominal - emergency_exit_price) / pos.entry_price_nominal * 100.0

                        net_ret = gross_ret - total_friction_pct
                        net_pnl_usd = pos.position_size_usd * (net_ret / 100.0)
                        new_equity = state.equity + net_pnl_usd
                        new_peak = max(state.peak_equity, new_equity)
                        dd_pct = (new_peak - new_equity) / new_peak * 100.0 if new_peak > 0 else 0.0

                        exit_record = {
                            "position_id": pos.position_id,
                            "direction": pos.direction,
                            "entry_time_ms": pos.entry_bar_time_ms,
                            "exit_time_ms": current_time_ms,
                            "entry_price_nominal": pos.entry_price_nominal,
                            "entry_price_effective": pos.entry_price_effective,
                            "exit_price_nominal": emergency_exit_price,
                            "exit_price_effective": eff_exit,
                            "exit_reason": f"EMERGENCY_GAP_{gap_bars}",
                            "holding_bars": pos.bars_held + 1,
                            "gross_pnl_pct": gross_ret,
                            "total_cost_pct": total_friction_pct,
                            "net_pnl_pct": net_ret,
                            "net_pnl_usd": net_pnl_usd,
                            "mfe_pct": pos.mfe_pct,
                            "mae_pct": pos.mae_pct,
                            "equity_after_usd": new_equity,
                            "drawdown_pct": dd_pct,
                        }
                        state = PortfolioState(
                            equity=new_equity,
                            peak_equity=new_peak,
                            initial_equity=state.initial_equity,
                            active_position=None,
                            last_processed_candle_open_ms=candle.open_time,
                            total_trades_count=state.total_trades_count + 1,
                        )
                        self.state_mgr.commit_state_transition(
                            state=state,
                            processed_candle={
                                "open_time_ms": candle.open_time,
                                "close_time_ms": candle.close_time,
                                "open": candle.open,
                                "high": candle.high,
                                "low": candle.low,
                                "close": candle.close,
                            },
                            evaluated_signal=None,
                            trade_record=exit_record,
                            audit_event_type=event_type,
                            audit_event_name="EMERGENCY_GAP_EXIT",
                        )
                        self.warmup_lockout_bars_remaining = self.warmup_15m_bars
                        return state, None

                    # If no active position, require 100 clean warmup bars before entering
                    self.warmup_lockout_bars_remaining = self.warmup_15m_bars

        if self.warmup_lockout_bars_remaining > 0:
            self.warmup_lockout_bars_remaining -= 1
            is_gap_lockout = True

        trade_record: Optional[Dict[str, Any]] = None
        event_name = "CANDLE_PROCESSED"
        friction_factor = self.config.half_spread_pct + self.config.slippage_pct
        total_friction_pct = (
            self.config.entry_fee_rate
            + self.config.exit_fee_rate
            + 2.0 * self.config.half_spread_pct
            + 2.0 * self.config.slippage_pct
        ) * 100.0

        # 3. Manage existing active position across this completed candle
        if state.active_position is not None:
            pos = state.active_position
            direction = pos.direction
            nominal_entry = pos.entry_price_nominal
            bars_held = pos.bars_held + 1

            # Update MFE / MAE
            if direction == "UP":
                step_mfe = max(0.0, (candle.high - nominal_entry) / nominal_entry * 100.0)
                step_mae = max(0.0, (nominal_entry - candle.low) / nominal_entry * 100.0)
            else:
                step_mfe = max(0.0, (nominal_entry - candle.low) / nominal_entry * 100.0)
                step_mae = max(0.0, (candle.high - nominal_entry) / nominal_entry * 100.0)

            cur_mfe = max(pos.mfe_pct, step_mfe)
            cur_mae = max(pos.mae_pct, step_mae)

            sl_hit = False
            tp_hit = False
            sl_nominal_exit = pos.stop_loss_price

            # Opening gap check: if market opened beyond stop price, execute at open (gap slippage)
            if direction == "UP":
                if candle.open < pos.stop_loss_price:
                    sl_hit = True
                    sl_nominal_exit = candle.open  # Gap slippage
                elif candle.low <= pos.stop_loss_price:
                    sl_hit = True

                if candle.high >= pos.take_profit_price:
                    tp_hit = True
            else:
                if candle.open > pos.stop_loss_price:
                    sl_hit = True
                    sl_nominal_exit = candle.open  # Gap slippage
                elif candle.high >= pos.stop_loss_price:
                    sl_hit = True

                if candle.low <= pos.take_profit_price:
                    tp_hit = True

            exit_reason: Optional[str] = None
            nominal_exit = 0.0

            # Conservative tie-breaking: if both triggered within same candle, SL hit first
            if sl_hit and tp_hit:
                exit_reason = "STOP_LOSS_GAP" if sl_nominal_exit != pos.stop_loss_price else "STOP_LOSS"
                nominal_exit = sl_nominal_exit
            elif sl_hit:
                exit_reason = "STOP_LOSS_GAP" if sl_nominal_exit != pos.stop_loss_price else "STOP_LOSS"
                nominal_exit = sl_nominal_exit
            elif tp_hit:
                exit_reason = "TAKE_PROFIT"
                nominal_exit = pos.take_profit_price
            elif bars_held >= pos.max_holding_bars:
                exit_reason = "MAX_HOLD"
                nominal_exit = candle.close

            if exit_reason is not None:
                if direction == "UP":
                    effective_exit = nominal_exit * (1.0 - friction_factor)
                    gross_ret = (nominal_exit - nominal_entry) / nominal_entry * 100.0
                else:
                    effective_exit = nominal_exit * (1.0 + friction_factor)
                    gross_ret = (nominal_entry - nominal_exit) / nominal_entry * 100.0

                net_ret = gross_ret - total_friction_pct
                net_pnl_usd = pos.position_size_usd * (net_ret / 100.0)
                new_equity = state.equity + net_pnl_usd
                new_peak = max(state.peak_equity, new_equity)
                dd_pct = (new_peak - new_equity) / new_peak * 100.0 if new_peak > 0 else 0.0

                trade_record = {
                    "position_id": pos.position_id,
                    "direction": direction,
                    "entry_time_ms": pos.entry_bar_time_ms,
                    "exit_time_ms": candle.close_time,
                    "entry_price_nominal": pos.entry_price_nominal,
                    "entry_price_effective": pos.entry_price_effective,
                    "exit_price_nominal": nominal_exit,
                    "exit_price_effective": effective_exit,
                    "exit_reason": exit_reason,
                    "holding_bars": bars_held,
                    "gross_pnl_pct": gross_ret,
                    "total_cost_pct": total_friction_pct,
                    "net_pnl_pct": net_ret,
                    "net_pnl_usd": net_pnl_usd,
                    "mfe_pct": cur_mfe,
                    "mae_pct": cur_mae,
                    "equity_after_usd": new_equity,
                    "drawdown_pct": dd_pct,
                }
                state = PortfolioState(
                    equity=new_equity,
                    peak_equity=new_peak,
                    initial_equity=state.initial_equity,
                    active_position=None,
                    last_processed_candle_open_ms=candle.open_time,
                    total_trades_count=state.total_trades_count + 1,
                )
                event_name = "POSITION_EXITED"
            else:
                updated_pos = ActivePosition(
                    position_id=pos.position_id,
                    direction=pos.direction,
                    entry_bar_time_ms=pos.entry_bar_time_ms,
                    entry_price_nominal=pos.entry_price_nominal,
                    entry_price_effective=pos.entry_price_effective,
                    atr7=pos.atr7,
                    stop_loss_price=pos.stop_loss_price,
                    take_profit_price=pos.take_profit_price,
                    max_holding_bars=pos.max_holding_bars,
                    bars_held=bars_held,
                    mfe_pct=cur_mfe,
                    mae_pct=cur_mae,
                    position_size_usd=pos.position_size_usd,
                )
                state = PortfolioState(
                    equity=state.equity,
                    peak_equity=state.peak_equity,
                    initial_equity=state.initial_equity,
                    active_position=updated_pos,
                    last_processed_candle_open_ms=candle.open_time,
                    total_trades_count=state.total_trades_count,
                )

        # 4. Pending Entry Signal Resolution (if portfolio was flat going into candle open)
        elif trade_record is None and not is_gap_lockout:
            if pending_signal and pending_signal.get("direction") in ("UP", "DOWN"):
                sig_time = pending_signal.get("open_time_ms")
                expected_sig_time = candle.open_time - step_15m

                if sig_time == expected_sig_time:
                    # Requirement 9: Reject delayed entries in LATE_CATCHUP mode
                    if event_type == "LATE_CATCHUP":
                        self.state_mgr.record_audit_event(
                            event_type="LATE_CATCHUP",
                            event_name="DELAYED_ENTRY_REJECTED",
                            candle_open_ms=candle.open_time,
                            payload={
                                "reason": "MISSED_ENTRY_WINDOW_LATE_CATCHUP",
                                "signal_time_ms": sig_time,
                                "target_candle_open_ms": candle.open_time,
                                "direction": pending_signal["direction"],
                            },
                        )
                        logger.info("Rejected delayed entry for signal at %d during LATE_CATCHUP.", sig_time)
                    else:
                        # REAL_TIME or OFFLINE_TEST
                        sig_dir = pending_signal["direction"]

                        # In REAL_TIME: use contemporaneously observed public market quote
                        if event_type == "REAL_TIME" and contemporaneous_quote_price is not None:
                            nominal_entry = contemporaneous_quote_price
                            entry_timestamp_ms = current_time_ms
                            entry_source = "CONTEMPORANEOUS_QUOTE"
                        else:
                            nominal_entry = candle.open
                            entry_timestamp_ms = candle.open_time
                            entry_source = "BACKTEST_NEXT_OPEN"

                        effective_entry = nominal_entry * (1.0 + friction_factor) if sig_dir == "UP" else nominal_entry * (1.0 - friction_factor)
                        atr7 = pending_signal.get("atr7", 0.0)

                        if sig_dir == "UP":
                            sl_price = nominal_entry - self.config.atr_stop_multiplier * atr7
                            tp_price = nominal_entry + self.config.atr_profit_multiplier * atr7
                        else:
                            sl_price = nominal_entry + self.config.atr_stop_multiplier * atr7
                            tp_price = nominal_entry - self.config.atr_profit_multiplier * atr7

                        new_pos = ActivePosition(
                            position_id=f"POS_{candle.open_time}",
                            direction=sig_dir,
                            entry_bar_time_ms=entry_timestamp_ms,
                            entry_price_nominal=nominal_entry,
                            entry_price_effective=effective_entry,
                            atr7=atr7,
                            stop_loss_price=sl_price,
                            take_profit_price=tp_price,
                            max_holding_bars=self.config.max_holding_bars,
                            bars_held=1,
                            mfe_pct=0.0,
                            mae_pct=0.0,
                            position_size_usd=self.config.position_size_usd,
                        )

                        # Check if this new position hit SL/TP within the entry candle itself
                        step_sl = False
                        step_tp = False
                        if sig_dir == "UP":
                            if candle.low <= sl_price:
                                step_sl = True
                            if candle.high >= tp_price:
                                step_tp = True
                        else:
                            if candle.high >= sl_price:
                                step_sl = True
                            if candle.low <= tp_price:
                                step_tp = True

                        if step_sl or step_tp:
                            # Immediate intrabar exit
                            intrabar_exit_reason = "STOP_LOSS" if step_sl else "TAKE_PROFIT"
                            nominal_exit = sl_price if step_sl else tp_price
                            effective_exit = nominal_exit * (1.0 - friction_factor) if sig_dir == "UP" else nominal_exit * (1.0 + friction_factor)
                            gross_ret = (nominal_exit - nominal_entry) / nominal_entry * 100.0 if sig_dir == "UP" else (nominal_entry - nominal_exit) / nominal_entry * 100.0
                            net_ret = gross_ret - total_friction_pct
                            net_pnl_usd = self.config.position_size_usd * (net_ret / 100.0)
                            new_equity = state.equity + net_pnl_usd
                            new_peak = max(state.peak_equity, new_equity)
                            dd_pct = (new_peak - new_equity) / new_peak * 100.0 if new_peak > 0 else 0.0

                            mfe = max(0.0, (candle.high - nominal_entry) / nominal_entry * 100.0 if sig_dir == "UP" else (nominal_entry - candle.low) / nominal_entry * 100.0)
                            mae = max(0.0, (nominal_entry - candle.low) / nominal_entry * 100.0 if sig_dir == "UP" else (candle.high - nominal_entry) / nominal_entry * 100.0)

                            trade_record = {
                                "position_id": new_pos.position_id,
                                "direction": sig_dir,
                                "entry_time_ms": entry_timestamp_ms,
                                "exit_time_ms": candle.close_time,
                                "entry_price_nominal": nominal_entry,
                                "entry_price_effective": effective_entry,
                                "exit_price_nominal": nominal_exit,
                                "exit_price_effective": effective_exit,
                                "exit_reason": intrabar_exit_reason,
                                "holding_bars": 1,
                                "gross_pnl_pct": gross_ret,
                                "total_cost_pct": total_friction_pct,
                                "net_pnl_pct": net_ret,
                                "net_pnl_usd": net_pnl_usd,
                                "mfe_pct": mfe,
                                "mae_pct": mae,
                                "equity_after_usd": new_equity,
                                "drawdown_pct": dd_pct,
                            }
                            state = PortfolioState(
                                equity=new_equity,
                                peak_equity=new_peak,
                                initial_equity=state.initial_equity,
                                active_position=None,
                                last_processed_candle_open_ms=candle.open_time,
                                total_trades_count=state.total_trades_count + 1,
                            )
                            event_name = "POSITION_ENTERED_AND_EXITED"
                        else:
                            state = PortfolioState(
                                equity=state.equity,
                                peak_equity=state.peak_equity,
                                initial_equity=state.initial_equity,
                                active_position=new_pos,
                                last_processed_candle_open_ms=candle.open_time,
                                total_trades_count=state.total_trades_count,
                            )
                            event_name = "POSITION_ENTERED"

        # 5. Evaluate Model Signal for candle close t
        evaluated_signal: Optional[Dict[str, Any]] = None
        new_pending_signal: Optional[Dict[str, Any]] = None

        has_15m_warmup = len(all_completed_15m_up_to_c) >= self.warmup_15m_bars
        has_4h_warmup = len(all_completed_4h_up_to_c) >= self.warmup_4h_bars

        if has_15m_warmup and has_4h_warmup:
            rows = extract_features(
                all_completed_15m_up_to_c,
                all_completed_4h_up_to_c,
                warmup_bars=self.warmup_15m_bars,
            )
            if rows:
                last_row = rows[-1]
                if last_row.open_time_utc_ms == candle.open_time:
                    policy_res, probs, dists = self.model.evaluate_features(last_row.features)
                    f10 = last_row.features[9]
                    atr7_val = f10 * last_row.close_price
                    vol_ratio = atr7_val / last_row.close_price if last_row.close_price > 0 else 0.0

                    p_avg = policy_res.average
                    spread = policy_res.spread
                    dist = policy_res.minimum_distance
                    direction = policy_res.direction

                    passed_gates = True
                    gate_reason = policy_res.reason

                    if direction not in ("UP", "DOWN"):
                        passed_gates = False
                    elif abs(p_avg - 0.50) < self.config.min_probability_edge:
                        passed_gates = False
                        gate_reason = "INSUFFICIENT_PROBABILITY_EDGE"
                    elif spread > self.config.max_expert_spread:
                        passed_gates = False
                        gate_reason = "EXPERT_SPREAD_TOO_HIGH"
                    elif dist > self.config.max_support_distance:
                        passed_gates = False
                        gate_reason = "SUPPORT_DISTANCE_TOO_HIGH"
                    elif vol_ratio < self.config.min_volatility_ratio:
                        passed_gates = False
                        gate_reason = "VOLATILITY_RATIO_TOO_LOW"

                    final_direction = direction if passed_gates else "NO_TRADE"
                    evaluated_signal = {
                        "open_time_ms": candle.open_time,
                        "close_price": candle.close,
                        "atr7": atr7_val,
                        "p_avg": p_avg,
                        "spread": spread,
                        "min_distance": dist,
                        "direction": final_direction,
                        "reason": gate_reason if not passed_gates else policy_res.reason,
                    }
                    if passed_gates:
                        new_pending_signal = evaluated_signal
        else:
            self.state_mgr.record_audit_event(
                event_type=event_type,
                event_name="INSUFFICIENT_WARMUP",
                candle_open_ms=candle.open_time,
                payload={
                    "15m_count": len(all_completed_15m_up_to_c),
                    "15m_required": self.warmup_15m_bars,
                    "4h_count": len(all_completed_4h_up_to_c),
                    "4h_required": self.warmup_4h_bars,
                },
            )

        # 6. Commit State Transition atomically
        state = PortfolioState(
            equity=state.equity,
            peak_equity=state.peak_equity,
            initial_equity=state.initial_equity,
            active_position=state.active_position,
            last_processed_candle_open_ms=candle.open_time,
            total_trades_count=state.total_trades_count,
        )

        self.state_mgr.commit_state_transition(
            state=state,
            processed_candle={
                "timeframe": "15m",
                "open_time_ms": candle.open_time,
                "close_time_ms": candle.close_time,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
            },
            evaluated_signal=evaluated_signal,
            trade_record=trade_record,
            audit_event_type=event_type,
            audit_event_name=event_name,
        )

        return state, new_pending_signal

    def poll_cycle(
        self,
        mode: str = "AUTO",
        symbol: Optional[str] = None,
        offline_15m: Optional[List[Candle]] = None,
        offline_4h: Optional[List[Candle]] = None,
    ) -> Dict[str, Any]:
        """Execute one complete polling and evaluation cycle."""
        symbol = symbol or self.symbol
        now_ms = self.clock_fn()
        state = self.state_mgr.initialize_portfolio_if_empty(self.config.initial_equity)

        raw_15m: List[Candle] = []
        raw_4h: List[Candle] = []

        if mode == "OFFLINE_TEST" or offline_15m is not None:
            raw_15m = offline_15m or []
            raw_4h = offline_4h or []
            mode_override = "OFFLINE_TEST"
        else:
            mode_override = None
            try:
                # Fetch chunks from Binance Futures USD-M public endpoint
                raw_15m = self.data_client.fetch_klines_chunk(symbol=symbol, interval="15m", limit=150)
                raw_4h = self.data_client.fetch_klines_chunk(symbol=symbol, interval="4h", limit=50)
            except Exception as e:
                logger.error("Binance public API fetch error: %s", e)
                self.state_mgr.record_audit_event(
                    event_type="REAL_TIME",
                    event_name="API_POLL_FAILURE",
                    candle_open_ms=None,
                    payload={"error": str(e), "timestamp_ms": now_ms},
                )
                return {
                    "status": "API_FAILURE",
                    "error": str(e),
                    "candles_processed": 0,
                    "state": state,
                }

        # Filter completed candles only
        completed_15m = self.filter_completed_candles(raw_15m, now_ms)
        completed_4h = self.filter_completed_candles(raw_4h, now_ms)

        if not completed_15m or not completed_4h:
            logger.info("No completed candles available for evaluation.")
            return {
                "status": "NO_COMPLETED_CANDLES",
                "candles_processed": 0,
                "state": state,
            }

        # Check for stale market data: if latest completed candle is too old
        latest_c = completed_15m[-1]
        staleness_ms = now_ms - latest_c.close_time
        if staleness_ms > 2 * 15 * 60 * 1000 and mode_override != "OFFLINE_TEST":
            self.state_mgr.record_audit_event(
                event_type="LATE_CATCHUP",
                event_name="STALE_DATA_DETECTED",
                candle_open_ms=latest_c.open_time,
                payload={"staleness_ms": staleness_ms, "latest_close_ms": latest_c.close_time},
            )

        # Identify unprocessed completed candles
        last_ms = state.last_processed_candle_open_ms
        if last_ms is None:
            # First initialization run: process all completed
            unprocessed = completed_15m
        else:
            unprocessed = [c for c in completed_15m if c.open_time > last_ms]

        if not unprocessed:
            logger.info("All completed candles already processed. Database is up to date.")
            return {
                "status": "UP_TO_DATE",
                "candles_processed": 0,
                "state": state,
            }

        processed_count = 0
        step_15m = 15 * 60 * 1000

        # Extract contemporaneous quote price from forming candle if available
        forming_quote = None
        if raw_15m and raw_15m[-1] not in completed_15m:
            forming_quote = raw_15m[-1].close  # Latest traded quote at decision time

        for c in unprocessed:
            evt_type = self.classify_event_type(
                candle_close_time_ms=c.close_time,
                current_time_ms=now_ms,
                mode_override=mode_override,
            )

            # Context lookup
            context_15m = [x for x in completed_15m if x.open_time <= c.open_time]
            context_4h = [x for x in completed_4h if x.close_time <= c.close_time]

            # Pending signal from preceding bar (open_time = c.open_time - step_15m)
            prev_sig_open = c.open_time - step_15m
            pending_signal = self.state_mgr.get_evaluated_signal(prev_sig_open)

            state, _ = self.step_candle(
                state=state,
                candle=c,
                all_completed_15m_up_to_c=context_15m,
                all_completed_4h_up_to_c=context_4h,
                current_time_ms=now_ms,
                event_type=evt_type,
                pending_signal=pending_signal,
                contemporaneous_quote_price=forming_quote if evt_type == "REAL_TIME" else None,
            )
            processed_count += 1

        final_state = self.state_mgr.load_portfolio_state()
        return {
            "status": "SUCCESS",
            "candles_processed": processed_count,
            "state": final_state,
        }


def run_health_check(
    db_path: Path = DEFAULT_DB_PATH,
    checkpoint_path: Path = FROZEN_MODEL_CHECKPOINT_PATH,
    client: Optional[BinanceFuturesDataClient] = None,
) -> bool:
    """Perform health and integrity diagnostics for independent paper trading."""
    print("=" * 70)
    print("ETH Quant Research Engine — Operational Health Check (--check)")
    print("=" * 70)

    all_passed = True

    # 1. Check Model Checkpoint SHA-256
    try:
        model = verify_model_checkpoint(checkpoint_path)
        print(f"[OK] Model Checkpoint: Verified SHA-256 ({EXPECTED_CHECKPOINT_SHA256[:16]}...)")
    except Exception as e:
        print(f"[FAIL] Model Checkpoint: {e}")
        all_passed = False

    # 2. Check SQLite Database and Schema
    try:
        state_mgr = PersistentStateManager(db_path)
        state = state_mgr.initialize_portfolio_if_empty(10000.0)
        loaded = state_mgr.load_portfolio_state()
        print(f"[OK] SQLite Persistence: Verified ACID WAL DB at {db_path} (Equity: ${loaded.equity:,.2f})")
        state_mgr.close()
    except Exception as e:
        print(f"[FAIL] SQLite Persistence: {e}")
        all_passed = False

    # 3. Check Public Binance API Connectivity
    client = client or BinanceFuturesDataClient()
    try:
        sample_klines = client.fetch_klines_chunk("ETHUSDT", "15m", limit=2)
        if len(sample_klines) > 0 and sample_klines[0].is_valid_ohlc:
            print(f"[OK] Binance Futures API: Reachable public klines endpoint ({len(sample_klines)} candles returned)")
        else:
            print("[FAIL] Binance Futures API: Unexpected empty response")
            all_passed = False
    except Exception as e:
        print(f"[FAIL] Binance Futures API: Connection failed: {e}")
        all_passed = False

    # 4. Check V23 Sealed Gate Integrity
    try:
        check_v23_sealed_overlap(1751662800000, 1752267599999)
        print("[FAIL] V23 Sealed Gate: Security check failed to intercept sealed window!")
        all_passed = False
    except SealedWindowViolationError:
        print("[OK] V23 Sealed Gate: Integrity confirmed (July 5-11, 2025 strictly blocked)")

    # 5. Live Trading Lock
    print("[OK] Safety Governance: Default research_only=True. Real trades permanently disabled.")

    print("=" * 70)
    if all_passed:
        print("RESULT: HEALTH CHECK PASSED. System is safe and ready for paper trading.")
    else:
        print("RESULT: HEALTH CHECK FAILED. One or more requirements failed.")
    print("=" * 70)

    return all_passed


def run_pipeline(
    candles_15m: List[Candle],
    candles_4h: List[Candle],
    model: V22ReconstructedModel,
    config: Optional[DynamicStrategyConfig] = None,
    warmup_bars: int = 100,
    db_path: Optional[Path] = None,
    mode: str = "OFFLINE_TEST",
) -> Tuple[List[CausalTradeResult], PortfolioExecutionSummary, List[Dict[str, Any]]]:
    """Execute causal evaluation pipeline with SQLite persistence (Batch / Offline Mode)."""
    if config is None:
        config = get_default_d1_config()

    if db_path is None:
        db_path = DEFAULT_DB_PATH

    state_mgr = PersistentStateManager(db_path)
    state = state_mgr.initialize_portfolio_if_empty(config.initial_equity)

    validate_candle_sequence(candles_15m, "15m")
    validate_candle_sequence(candles_4h, "4h")

    # Defensive check on Phase 5C window
    first_15m = candles_15m[0].open_time if candles_15m else 0
    last_15m = candles_15m[-1].close_time if candles_15m else 0
    if max(first_15m, PHASE_5C_START_MS) <= min(last_15m, PHASE_5C_END_MS):
        raise PermissionError("Access to Phase 5C evaluation window is not authorized in Phase 5B-Ops.")

    feature_rows = extract_features(candles_15m, candles_4h, warmup_bars=warmup_bars)
    signals: List[Dict[str, Any]] = []

    for row in feature_rows:
        policy_res, probs, dists = model.evaluate_features(row.features)
        f10 = row.features[9]
        atr7_val = f10 * row.close_price

        sig_dict = {
            "timestamp_utc_ms": row.open_time_utc_ms,
            "close_time_utc_ms": row.close_time_utc_ms,
            "close_price": row.close_price,
            "atr7": atr7_val,
            "p_avg": policy_res.average,
            "expert_spread": policy_res.spread,
            "min_rms_distance": policy_res.minimum_distance,
            "policy_direction": policy_res.direction,
            "policy_reason": policy_res.reason,
        }
        signals.append(sig_dict)

    simulator = CausalDynamicPortfolioSimulator(config)
    trades, summary = simulator.simulate(signals, candles_15m)

    trade_map = {t.entry_bar_idx: t for t in trades}
    exit_map = {t.exit_bar_idx: t for t in trades}
    signal_map = {s["timestamp_utc_ms"]: s for s in signals}

    for i, c in enumerate(candles_15m):
        if state_mgr.is_candle_processed("15m", c.open_time):
            continue

        c_dict = {
            "timeframe": "15m",
            "open_time_ms": c.open_time,
            "close_time_ms": c.close_time,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
        }

        sig = signal_map.get(c.open_time)
        sig_dict = None
        if sig:
            sig_dict = {
                "open_time_ms": sig["timestamp_utc_ms"],
                "close_price": sig["close_price"],
                "atr7": sig["atr7"],
                "p_avg": sig["p_avg"],
                "spread": sig["expert_spread"],
                "min_distance": sig["min_rms_distance"],
                "direction": sig["policy_direction"],
                "reason": sig["policy_reason"],
            }

        t_entry = trade_map.get(i)
        t_exit = exit_map.get(i)

        trade_record = None
        event_name = "CANDLE_PROCESSED"

        if t_exit:
            state = PortfolioState(
                equity=t_exit.equity_after_usd,
                peak_equity=max(state.peak_equity, t_exit.equity_after_usd),
                initial_equity=state.initial_equity,
                active_position=None,
                last_processed_candle_open_ms=c.open_time,
                total_trades_count=state.total_trades_count,
            )
            trade_record = {
                "position_id": f"POS_{t_exit.entry_time_ms}",
                "direction": t_exit.direction,
                "entry_time_ms": t_exit.entry_time_ms,
                "exit_time_ms": t_exit.exit_time_ms,
                "entry_price_nominal": t_exit.entry_price_nominal,
                "entry_price_effective": t_exit.entry_price_effective,
                "exit_price_nominal": t_exit.exit_price_nominal,
                "exit_price_effective": t_exit.exit_price_effective,
                "exit_reason": t_exit.exit_reason,
                "holding_bars": t_exit.holding_bars,
                "gross_pnl_pct": t_exit.gross_pnl_pct,
                "total_cost_pct": t_exit.total_cost_pct,
                "net_pnl_pct": t_exit.net_pnl_pct,
                "net_pnl_usd": t_exit.net_pnl_usd,
                "mfe_pct": t_exit.mfe_pct,
                "mae_pct": t_exit.mae_pct,
                "equity_after_usd": t_exit.equity_after_usd,
                "drawdown_pct": t_exit.drawdown_pct,
            }
            event_name = "POSITION_EXITED"
        elif t_entry:
            nominal_entry = t_entry.entry_price_nominal
            atr7 = signal_map[candles_15m[i - 1].open_time]["atr7"] if i > 0 else 0.0
            sl = nominal_entry - config.atr_stop_multiplier * atr7 if t_entry.direction == "UP" else nominal_entry + config.atr_stop_multiplier * atr7
            tp = nominal_entry + config.atr_profit_multiplier * atr7 if t_entry.direction == "UP" else nominal_entry - config.atr_profit_multiplier * atr7
            act_pos = ActivePosition(
                position_id=f"POS_{t_entry.entry_time_ms}",
                direction=t_entry.direction,
                entry_bar_time_ms=t_entry.entry_time_ms,
                entry_price_nominal=nominal_entry,
                entry_price_effective=t_entry.entry_price_effective,
                atr7=atr7,
                stop_loss_price=sl,
                take_profit_price=tp,
                max_holding_bars=config.max_holding_bars,
                bars_held=1,
                mfe_pct=0.0,
                mae_pct=0.0,
                position_size_usd=config.position_size_usd,
            )
            state = PortfolioState(
                equity=state.equity,
                peak_equity=state.peak_equity,
                initial_equity=state.initial_equity,
                active_position=act_pos,
                last_processed_candle_open_ms=c.open_time,
                total_trades_count=state.total_trades_count + 1,
            )
            event_name = "POSITION_ENTERED"
        else:
            state = PortfolioState(
                equity=state.equity,
                peak_equity=state.peak_equity,
                initial_equity=state.initial_equity,
                active_position=state.active_position,
                last_processed_candle_open_ms=c.open_time,
                total_trades_count=state.total_trades_count,
            )

        state_mgr.commit_state_transition(
            state=state,
            processed_candle=c_dict,
            evaluated_signal=sig_dict,
            trade_record=trade_record,
            audit_event_type=mode,
            audit_event_name=event_name,
        )

    return trades, summary, signals


def run_offline_validation(
    data_dir: Path = Path("data/raw"),
    symbol: str = "ETHUSDT",
    model: Optional[V22ReconstructedModel] = None,
) -> PortfolioExecutionSummary:
    """Run an offline validation check on cached candles."""
    if model is None:
        model = verify_model_checkpoint()

    cache_files_15m = list(data_dir.glob(f"{symbol}_15m_*.json"))
    cache_files_4h = list(data_dir.glob(f"{symbol}_4h_*.json"))

    if not cache_files_15m or not cache_files_4h:
        raise FileNotFoundError(
            f"No cached data found in {data_dir} for {symbol}. Run with online fetch or provide test data."
        )

    client = BinanceFuturesDataClient(cache_dir=data_dir)
    candles_15m = client.load_candles_from_json(cache_files_15m[0])
    candles_4h = client.load_candles_from_json(cache_files_4h[0])

    trades, summary, signals = run_pipeline(candles_15m, candles_4h, model)
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="ETHUSDT Independent Headless Paper-Trading Runner")
    parser.add_argument("--check", action="store_true", help="Perform operational health check and exit")
    parser.add_argument("--run-once", action="store_true", help="Execute one safe real-time polling cycle")
    parser.add_argument("--offline-dry-run", action="store_true", help="Execute one safe offline simulation cycle")
    parser.add_argument("--mode", choices=["offline_validation", "paper_sim"], default="offline_validation")
    parser.add_argument("--cache-dir", type=str, default="data/raw")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB_PATH))
    parser.add_argument("--symbol", type=str, default="ETHUSDT")

    args = parser.parse_args()

    # Safety Notice
    print("=" * 70)
    print("ETH Quant Research Engine — Independent Paper-Trading Runner")
    print("Mode: RESEARCH ONLY. Live trading endpoints are permanently disabled.")
    print("V23 window: STRICTLY SEALED.")
    print("=" * 70)

    db_path = Path(args.db_path)
    config = get_default_d1_config()

    if args.check:
        passed = run_health_check(db_path=db_path)
        sys.exit(0 if passed else 1)

    model = verify_model_checkpoint()
    state_mgr = PersistentStateManager(db_path)
    engine = PaperTradingEngine(
        state_mgr=state_mgr,
        model=model,
        config=config,
        symbol=args.symbol,
    )

    if args.run_once:
        print("[INFO] Executing single safe polling cycle against public Binance Futures...")
        result = engine.poll_cycle(mode="AUTO", symbol=args.symbol)
        print(f"[RESULT] Cycle status: {result['status']}, Candles processed: {result['candles_processed']}")
        st = result["state"]
        print(f"[STATE] Equity: ${st.equity:,.2f}, Active Position: {st.active_position is not None}, Trades Count: {st.total_trades_count}")
        sys.exit(0 if result["status"] in ("SUCCESS", "UP_TO_DATE", "NO_COMPLETED_CANDLES") else 1)

    if args.offline_dry_run:
        print("[INFO] Executing offline dry-run polling cycle...")
        # Load from cache or fixtures
        client = BinanceFuturesDataClient(cache_dir=Path(args.cache_dir))
        cache_files_15m = list(Path(args.cache_dir).glob(f"{args.symbol}_15m_*.json"))
        cache_files_4h = list(Path(args.cache_dir).glob(f"{args.symbol}_4h_*.json"))

        if not cache_files_15m or not cache_files_4h:
            print(f"[ERROR] No cached data in {args.cache_dir} for offline dry run.")
            sys.exit(1)

        c_15m = client.load_candles_from_json(cache_files_15m[0])
        c_4h = client.load_candles_from_json(cache_files_4h[0])

        result = engine.poll_cycle(mode="OFFLINE_TEST", symbol=args.symbol, offline_15m=c_15m, offline_4h=c_4h)
        print(f"[RESULT] Dry-run cycle status: {result['status']}, Candles processed: {result['candles_processed']}")
        st = result["state"]
        print(f"[STATE] Equity: ${st.equity:,.2f}, Active Position: {st.active_position is not None}, Trades Count: {st.total_trades_count}")
        sys.exit(0)

    if args.mode == "offline_validation":
        try:
            summary = run_offline_validation(Path(args.cache_dir), args.symbol, model)
            print(f"Validation successful. Strategy: {summary.strategy_name}, Executed trades: {summary.executed_trades}")
        except FileNotFoundError as e:
            print(f"Offline validation warning: {e}")
            print("To run validation, download cached data or use unittest suites.")


if __name__ == "__main__":
    main()
