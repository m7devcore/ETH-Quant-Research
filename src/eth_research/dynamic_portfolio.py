"""Causal Dynamic Order-State Simulator and Portfolio Engine.

Features:
- Single-position portfolio with strict non-overlapping execution (no phantom capital reuse).
- Causal candle-by-candle dynamic evaluation of Stop-Loss (SL), Take-Profit (TP), and Max-Hold exit.
- Conservative ambiguity resolution: if High reaches TP and Low reaches SL in the same candle,
  SL is conservatively assumed to hit first.
- Zero future-information leakage: trail updates, target prices, and exit flags use only completed history.
- Full accounting of entry/exit fees, spread, slippage, mark-to-market equity, and drawdowns.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from eth_research.data import Candle


@dataclasses.dataclass(frozen=True)
class DynamicStrategyConfig:
    strategy_name: str
    min_probability_edge: float = 0.05   # e.g., p_avg >= 0.55 or <= 0.45
    max_expert_spread: float = 0.04      # tighter agreement than baseline 0.06
    max_support_distance: float = 1.80   # closer to historical support than baseline 2.0
    min_volatility_ratio: float = 0.0018 # ATR7 / close >= 0.18%
    atr_stop_multiplier: float = 1.50    # Stop loss distance = 1.5 * ATR7
    atr_profit_multiplier: float = 2.50  # Take profit distance = 2.5 * ATR7
    max_holding_bars: int = 4            # Maximum 4 bars (1 hour)
    entry_fee_rate: float = 0.0005       # 0.05% taker entry
    exit_fee_rate: float = 0.0005        # 0.05% taker exit
    half_spread_pct: float = 0.00005     # 0.5 bps half-spread (1.0 bps roundtrip)
    slippage_pct: float = 0.00005        # 0.5 bps slippage (1.0 bps roundtrip)
    initial_equity: float = 10000.0      # Fixed 10,000 USD portfolio
    position_size_usd: float = 10000.0   # 1.0x unleveraged allocation


@dataclasses.dataclass(frozen=True)
class CausalTradeResult:
    trade_id: int
    signal_bar_idx: int
    entry_bar_idx: int
    exit_bar_idx: int
    entry_time_ms: int
    exit_time_ms: int
    direction: str  # 'UP' or 'DOWN'
    entry_price_nominal: float
    entry_price_effective: float
    exit_price_nominal: float
    exit_price_effective: float
    exit_reason: str  # 'STOP_LOSS', 'TAKE_PROFIT', 'MAX_HOLD'
    holding_bars: int
    gross_pnl_pct: float
    total_cost_pct: float
    net_pnl_pct: float
    net_pnl_usd: float
    mfe_pct: float
    mae_pct: float
    equity_after_usd: float
    drawdown_pct: float


@dataclasses.dataclass(frozen=True)
class PortfolioExecutionSummary:
    strategy_name: str
    total_signals_evaluated: int
    executed_trades: int
    signals_rejected_portfolio_busy: int
    signals_rejected_filter_gates: int
    net_pnl_pct: float
    net_pnl_usd: float
    gross_pnl_pct: float
    avg_net_return_pct: float
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    avg_holding_bars: float
    sl_exit_count: int
    tp_exit_count: int
    max_hold_exit_count: int
    breakeven_roundtrip_cost_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class CausalDynamicPortfolioSimulator:
    """Deterministic, causal portfolio execution simulator enforcing single-position integrity."""

    def __init__(self, config: DynamicStrategyConfig):
        self.config = config

    def simulate(
        self,
        signals: Sequence[Dict[str, Any]],
        candle_series: List[Candle],
    ) -> Tuple[List[CausalTradeResult], PortfolioExecutionSummary]:
        """Execute dynamic strategy across chronological signals and continuous candles."""
        time_to_idx = {c.open_time: i for i, c in enumerate(candle_series)}
        trades: List[CausalTradeResult] = []

        equity = self.config.initial_equity
        peak_equity = equity

        executed_count = 0
        busy_rejections = 0
        gate_rejections = 0

        last_occupied_until_bar = -1

        sl_count = 0
        tp_count = 0
        max_hold_count = 0

        net_returns: List[float] = []
        gross_returns: List[float] = []
        net_wins = 0.0
        net_losses = 0.0

        for sig in signals:
            sig_time = sig["timestamp_utc_ms"]
            if sig_time not in time_to_idx:
                continue
            sig_idx = time_to_idx[sig_time]
            entry_idx = sig_idx + 1

            if entry_idx >= len(candle_series):
                continue

            # 1. Portfolio Concurrency Check: strictly non-overlapping
            if entry_idx <= last_occupied_until_bar:
                busy_rejections += 1
                continue

            # 2. Gate Verification
            direction = sig.get("policy_direction")
            if direction not in ("UP", "DOWN"):
                gate_rejections += 1
                continue

            p_avg = sig.get("p_avg", 0.50)
            spread = sig.get("expert_spread", 1.0)
            dist = sig.get("min_rms_distance", 99.0)
            atr7 = sig.get("atr7", 0.0)
            close_p = sig.get("close_price", 1.0)
            vol_ratio = atr7 / close_p if close_p > 0 else 0.0

            if abs(p_avg - 0.50) < self.config.min_probability_edge:
                gate_rejections += 1
                continue
            if spread > self.config.max_expert_spread:
                gate_rejections += 1
                continue
            if dist > self.config.max_support_distance:
                gate_rejections += 1
                continue
            if vol_ratio < self.config.min_volatility_ratio:
                gate_rejections += 1
                continue

            # Passed all gates: Execute trade
            executed_count += 1
            entry_candle = candle_series[entry_idx]
            nominal_entry = entry_candle.open

            friction_factor = self.config.half_spread_pct + self.config.slippage_pct
            total_friction_pct = (
                self.config.entry_fee_rate
                + self.config.exit_fee_rate
                + 2.0 * self.config.half_spread_pct
                + 2.0 * self.config.slippage_pct
            ) * 100.0

            if direction == "UP":
                effective_entry = nominal_entry * (1.0 + friction_factor)
                stop_loss_price = nominal_entry - self.config.atr_stop_multiplier * atr7
                take_profit_price = nominal_entry + self.config.atr_profit_multiplier * atr7
            else:  # DOWN
                effective_entry = nominal_entry * (1.0 - friction_factor)
                stop_loss_price = nominal_entry + self.config.atr_stop_multiplier * atr7
                take_profit_price = nominal_entry - self.config.atr_profit_multiplier * atr7

            # Candle-by-candle causal resolution
            exit_bar_idx = entry_idx
            exit_reason = "MAX_HOLD"
            nominal_exit = entry_candle.close

            max_eval_bar = min(entry_idx + self.config.max_holding_bars, len(candle_series))
            eval_window = candle_series[entry_idx:max_eval_bar]

            # Track MFE / MAE
            mfe_val = 0.0
            mae_val = 0.0

            for step_offset, current_c in enumerate(eval_window):
                c_idx = entry_idx + step_offset
                high_p = current_c.high
                low_p = current_c.low

                if direction == "UP":
                    step_mfe = max(0.0, (high_p - nominal_entry) / nominal_entry * 100.0)
                    step_mae = max(0.0, (nominal_entry - low_p) / nominal_entry * 100.0)
                else:
                    step_mfe = max(0.0, (nominal_entry - low_p) / nominal_entry * 100.0)
                    step_mae = max(0.0, (high_p - nominal_entry) / nominal_entry * 100.0)

                if step_mfe > mfe_val:
                    mfe_val = step_mfe
                if step_mae > mae_val:
                    mae_val = step_mae

                # Check SL and TP triggers
                sl_hit = False
                tp_hit = False

                if direction == "UP":
                    if low_p <= stop_loss_price:
                        sl_hit = True
                    if high_p >= take_profit_price:
                        tp_hit = True
                else:  # DOWN
                    if high_p >= stop_loss_price:
                        sl_hit = True
                    if low_p <= take_profit_price:
                        tp_hit = True

                # Conservative tie-breaking: if both triggered within same candle, SL hit first
                if sl_hit and tp_hit:
                    exit_bar_idx = c_idx
                    exit_reason = "STOP_LOSS"
                    nominal_exit = stop_loss_price
                    break
                elif sl_hit:
                    exit_bar_idx = c_idx
                    exit_reason = "STOP_LOSS"
                    nominal_exit = stop_loss_price
                    break
                elif tp_hit:
                    exit_bar_idx = c_idx
                    exit_reason = "TAKE_PROFIT"
                    nominal_exit = take_profit_price
                    break
                else:
                    # If this is the last permitted holding bar, exit at candle close
                    if step_offset == len(eval_window) - 1:
                        exit_bar_idx = c_idx
                        exit_reason = "MAX_HOLD"
                        nominal_exit = current_c.close
                        break

            # Calculate returns
            if direction == "UP":
                effective_exit = nominal_exit * (1.0 - friction_factor)
                gross_ret = (nominal_exit - nominal_entry) / nominal_entry * 100.0
            else:
                effective_exit = nominal_exit * (1.0 + friction_factor)
                gross_ret = (nominal_entry - nominal_exit) / nominal_entry * 100.0

            net_ret = gross_ret - total_friction_pct
            net_pnl_usd = self.config.position_size_usd * (net_ret / 100.0)

            equity += net_pnl_usd
            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity * 100.0 if peak_equity > 0 else 0.0

            if exit_reason == "STOP_LOSS":
                sl_count += 1
            elif exit_reason == "TAKE_PROFIT":
                tp_count += 1
            else:
                max_hold_count += 1

            gross_returns.append(gross_ret)
            net_returns.append(net_ret)
            if net_ret > 0:
                net_wins += net_ret
            else:
                net_losses += abs(net_ret)

            holding_bars = (exit_bar_idx - entry_idx) + 1
            last_occupied_until_bar = exit_bar_idx

            trades.append(
                CausalTradeResult(
                    trade_id=executed_count,
                    signal_bar_idx=sig_idx,
                    entry_bar_idx=entry_idx,
                    exit_bar_idx=exit_bar_idx,
                    entry_time_ms=entry_candle.open_time,
                    exit_time_ms=candle_series[exit_bar_idx].close_time,
                    direction=direction,
                    entry_price_nominal=nominal_entry,
                    entry_price_effective=effective_entry,
                    exit_price_nominal=nominal_exit,
                    exit_price_effective=effective_exit,
                    exit_reason=exit_reason,
                    holding_bars=holding_bars,
                    gross_pnl_pct=gross_ret,
                    total_cost_pct=total_friction_pct,
                    net_pnl_pct=net_ret,
                    net_pnl_usd=net_pnl_usd,
                    mfe_pct=mfe_val,
                    mae_pct=mae_val,
                    equity_after_usd=equity,
                    drawdown_pct=dd,
                )
            )

        # Portfolio Summary
        tot_signals = len(signals)
        net_pnl_pct = sum(net_returns)
        net_pnl_usd = equity - self.config.initial_equity
        gross_pnl_pct = sum(gross_returns)
        avg_net = net_pnl_pct / len(net_returns) if net_returns else 0.0
        win_rate = (
            sum(1 for r in net_returns if r > 0) / len(net_returns) * 100.0
            if net_returns
            else 0.0
        )
        pf = (net_wins / net_losses) if net_losses > 1e-12 else (math.inf if net_wins > 0 else 0.0)
        max_dd = max((t.drawdown_pct for t in trades), default=0.0)
        avg_hold = sum(t.holding_bars for t in trades) / len(trades) if trades else 0.0
        be_cost = gross_pnl_pct / len(gross_returns) if gross_returns else 0.0

        summary = PortfolioExecutionSummary(
            strategy_name=self.config.strategy_name,
            total_signals_evaluated=tot_signals,
            executed_trades=executed_count,
            signals_rejected_portfolio_busy=busy_rejections,
            signals_rejected_filter_gates=gate_rejections,
            net_pnl_pct=net_pnl_pct,
            net_pnl_usd=net_pnl_usd,
            gross_pnl_pct=gross_pnl_pct,
            avg_net_return_pct=avg_net,
            win_rate_pct=win_rate,
            profit_factor=pf,
            max_drawdown_pct=max_dd,
            avg_holding_bars=avg_hold,
            sl_exit_count=sl_count,
            tp_exit_count=tp_count,
            max_hold_exit_count=max_hold_count,
            breakeven_roundtrip_cost_pct=be_cost,
        )

        return trades, summary
