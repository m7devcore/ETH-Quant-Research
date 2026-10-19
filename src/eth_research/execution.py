"""Portable Economic Execution Simulator for ETHUSDT Quantitative Research.

Features:
- Long (UP) and Short (DOWN) trade simulation.
- Execution timing at next completed candle open (or with latency/slippage).
- Configurable maker/taker fee rates on entry and exit.
- Bid-ask spread and slippage modeling.
- Funding rate impact modeling (where applicable).
- Deterministic mark-to-market PnL, equity curve, and max drawdown tracking.
- Portable, clean Python dataclass interface callable by any AI agent or external engine.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclasses.dataclass(frozen=True)
class ExecutionConfig:
    scenario_name: str
    entry_fee_rate: float  # e.g., 0.0002 for 0.02% maker, 0.0005 for 0.05% taker
    exit_fee_rate: float   # e.g., 0.0002 for maker, 0.0005 for taker
    half_spread_pct: float # half of bid-ask spread as percentage of price (e.g., 0.01% = 0.0001)
    slippage_pct: float    # execution slippage percentage (e.g., 0.01% = 0.0001)
    maker_fill_rate: float = 1.0  # fill probability for maker orders (1.0 = filled, <1.0 = partial/missed)
    latency_ms: int = 0    # execution delay
    funding_rate_pct: float = 0.0 # 8h funding rate pro-rated (0.0 for 1-candle 15m hold unless crossing funding)
    initial_equity: float = 10000.0
    position_size_usd: float = 10000.0  # 1.0x unleveraged position size relative to initial equity


@dataclasses.dataclass(frozen=True)
class TradeRecord:
    trade_id: int
    bar_index: int
    timestamp_utc_ms: int
    datetime_utc: str
    datetime_istanbul: str
    direction: str  # 'UP' or 'DOWN'
    signal_close: float
    nominal_entry: float
    effective_entry: float
    nominal_exit: float
    effective_exit: float
    is_filled: bool
    gross_return_pct: float
    total_cost_pct: float
    net_return_pct: float
    entry_fee_cost_pct: float
    exit_fee_cost_pct: float
    spread_cost_pct: float
    slippage_cost_pct: float
    funding_cost_pct: float
    mfe_pct: float
    mae_pct: float
    is_hit: bool
    net_pnl_usd: float
    equity_after_usd: float
    drawdown_pct: float


@dataclasses.dataclass(frozen=True)
class SimulationSummary:
    scenario_name: str
    total_signals: int
    filled_trades: int
    fill_rate_pct: float
    gross_pnl_pct: float
    net_pnl_pct: float
    net_pnl_usd: float
    avg_gross_return_pct: float
    avg_net_return_pct: float
    gross_win_rate_pct: float
    net_win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    expected_value_usd_per_trade: float
    breakeven_roundtrip_cost_pct: float
    up_trades_count: int
    up_net_pnl_pct: float
    down_trades_count: int
    down_net_pnl_pct: float
    avg_mfe_pct: float
    avg_mae_pct: float
    worst_trade_net_pct: float
    best_trade_net_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class ExecutionSimulator:
    """Deterministic, portable execution simulator for directional 1-candle strategies."""

    def __init__(self, config: ExecutionConfig):
        self.config = config

    def simulate(
        self,
        signals: Sequence[Dict[str, Any]],
    ) -> Tuple[List[TradeRecord], SimulationSummary]:
        """Simulate execution on a chronological sequence of signals.

        Expected signal dictionary keys:
        - bar_index (int)
        - timestamp_utc_ms (int)
        - datetime_utc (str)
        - datetime_istanbul (str)
        - policy_direction ('UP' or 'DOWN')
        - close_price (float)
        - next_open (float)
        - next_high (float)
        - next_low (float)
        - next_close (float)
        - actual_next_direction ('UP' or 'DOWN')
        """
        trades: List[TradeRecord] = []
        equity = self.config.initial_equity
        peak_equity = equity

        total_signals = len(signals)
        filled_count = 0

        gross_returns: List[float] = []
        net_returns: List[float] = []
        up_net_returns: List[float] = []
        down_net_returns: List[float] = []
        mfes: List[float] = []
        maes: List[float] = []

        gross_wins: float = 0.0
        gross_losses: float = 0.0
        net_wins: float = 0.0
        net_losses: float = 0.0

        for i, sig in enumerate(signals):
            direction = sig["policy_direction"]
            if direction not in ("UP", "DOWN"):
                continue

            # Fill simulation: check maker fill rate
            is_filled = True
            if self.config.maker_fill_rate < 1.0:
                # Deterministic fill check: if maker, does price test beyond limit?
                # For Long (UP): maker limit at next_open. Fills if next_low <= next_open.
                # For Short (DOWN): maker limit at next_open. Fills if next_high >= next_open.
                next_open = sig["next_open"]
                next_low = sig["next_low"]
                next_high = sig["next_high"]
                if direction == "UP" and next_low > next_open:
                    is_filled = False
                elif direction == "DOWN" and next_high < next_open:
                    is_filled = False

            if not is_filled:
                continue

            filled_count += 1
            nominal_entry = sig["next_open"]
            nominal_exit = sig["next_close"]
            next_high = sig["next_high"]
            next_low = sig["next_low"]

            # Effective entry price after spread and slippage:
            # Long enters at Ask = Price * (1 + half_spread + slippage)
            # Short enters at Bid = Price * (1 - half_spread - slippage)
            cost_factor_entry = self.config.half_spread_pct + self.config.slippage_pct
            cost_factor_exit = self.config.half_spread_pct + self.config.slippage_pct

            if direction == "UP":
                effective_entry = nominal_entry * (1.0 + cost_factor_entry)
                effective_exit = nominal_exit * (1.0 - cost_factor_exit)
                gross_ret_pct = (nominal_exit - nominal_entry) / nominal_entry * 100.0
                raw_net_ratio = (effective_exit / effective_entry) - 1.0
                # Excursion relative to nominal entry
                mfe = max(0.0, (next_high - nominal_entry) / nominal_entry * 100.0)
                mae = max(0.0, (nominal_entry - next_low) / nominal_entry * 100.0)
            else:  # DOWN (Short)
                effective_entry = nominal_entry * (1.0 - cost_factor_entry)
                effective_exit = nominal_exit * (1.0 + cost_factor_exit)
                gross_ret_pct = (nominal_entry - nominal_exit) / nominal_entry * 100.0
                raw_net_ratio = 1.0 - (effective_exit / effective_entry)
                mfe = max(0.0, (nominal_entry - next_low) / nominal_entry * 100.0)
                mae = max(0.0, (next_high - nominal_entry) / nominal_entry * 100.0)

            # Transaction fees: applied as percentage of nominal value
            entry_fee_pct = self.config.entry_fee_rate * 100.0
            exit_fee_pct = self.config.exit_fee_rate * 100.0
            spread_cost_pct = (2.0 * self.config.half_spread_pct) * 100.0
            slippage_cost_pct = (2.0 * self.config.slippage_pct) * 100.0
            funding_cost_pct = self.config.funding_rate_pct * 100.0

            total_costs_pct = (
                entry_fee_pct
                + exit_fee_pct
                + spread_cost_pct
                + slippage_cost_pct
                + funding_cost_pct
            )

            # Net return is gross return minus exact frictional drag
            # More precisely: net_ret_pct = gross_ret_pct - total_costs_pct
            net_ret_pct = gross_ret_pct - total_costs_pct

            # PnL accounting
            position_size = self.config.position_size_usd
            net_pnl = position_size * (net_ret_pct / 100.0)
            equity += net_pnl
            if equity > peak_equity:
                peak_equity = equity
            dd_pct = (peak_equity - equity) / peak_equity * 100.0 if peak_equity > 0 else 0.0

            gross_returns.append(gross_ret_pct)
            net_returns.append(net_ret_pct)
            mfes.append(mfe)
            maes.append(mae)

            if direction == "UP":
                up_net_returns.append(net_ret_pct)
            else:
                down_net_returns.append(net_ret_pct)

            if gross_ret_pct > 0:
                gross_wins += gross_ret_pct
            else:
                gross_losses += abs(gross_ret_pct)

            if net_ret_pct > 0:
                net_wins += net_ret_pct
            else:
                net_losses += abs(net_ret_pct)

            is_hit = sig.get("actual_next_direction") == direction

            trades.append(
                TradeRecord(
                    trade_id=filled_count,
                    bar_index=sig.get("bar_index", i),
                    timestamp_utc_ms=sig["timestamp_utc_ms"],
                    datetime_utc=sig.get("datetime_utc", ""),
                    datetime_istanbul=sig.get("datetime_istanbul", ""),
                    direction=direction,
                    signal_close=sig["close_price"],
                    nominal_entry=nominal_entry,
                    effective_entry=effective_entry,
                    nominal_exit=nominal_exit,
                    effective_exit=effective_exit,
                    is_filled=is_filled,
                    gross_return_pct=gross_ret_pct,
                    total_cost_pct=total_costs_pct,
                    net_return_pct=net_ret_pct,
                    entry_fee_cost_pct=entry_fee_pct,
                    exit_fee_cost_pct=exit_fee_pct,
                    spread_cost_pct=spread_cost_pct,
                    slippage_cost_pct=slippage_cost_pct,
                    funding_cost_pct=funding_cost_pct,
                    mfe_pct=mfe,
                    mae_pct=mae,
                    is_hit=is_hit,
                    net_pnl_usd=net_pnl,
                    equity_after_usd=equity,
                    drawdown_pct=dd_pct,
                )
            )

        # Aggregate metrics
        gross_pnl_pct = sum(gross_returns)
        net_pnl_pct = sum(net_returns)
        net_pnl_usd = equity - self.config.initial_equity
        avg_gross = sum(gross_returns) / len(gross_returns) if gross_returns else 0.0
        avg_net = sum(net_returns) / len(net_returns) if net_returns else 0.0
        gross_win_rate = (
            sum(1 for r in gross_returns if r > 0) / len(gross_returns) * 100.0
            if gross_returns
            else 0.0
        )
        net_win_rate = (
            sum(1 for r in net_returns if r > 0) / len(net_returns) * 100.0
            if net_returns
            else 0.0
        )
        profit_factor = (
            (net_wins / net_losses) if net_losses > 1e-12 else (math.inf if net_wins > 0 else 0.0)
        )
        max_dd = max((t.drawdown_pct for t in trades), default=0.0)
        ev_usd = net_pnl_usd / filled_count if filled_count > 0 else 0.0
        be_cost = avg_gross  # breakeven roundtrip cost is exactly the average gross return

        summary = SimulationSummary(
            scenario_name=self.config.scenario_name,
            total_signals=total_signals,
            filled_trades=filled_count,
            fill_rate_pct=filled_count / total_signals * 100.0 if total_signals > 0 else 0.0,
            gross_pnl_pct=gross_pnl_pct,
            net_pnl_pct=net_pnl_pct,
            net_pnl_usd=net_pnl_usd,
            avg_gross_return_pct=avg_gross,
            avg_net_return_pct=avg_net,
            gross_win_rate_pct=gross_win_rate,
            net_win_rate_pct=net_win_rate,
            profit_factor=profit_factor,
            max_drawdown_pct=max_dd,
            expected_value_usd_per_trade=ev_usd,
            breakeven_roundtrip_cost_pct=be_cost,
            up_trades_count=len(up_net_returns),
            up_net_pnl_pct=sum(up_net_returns),
            down_trades_count=len(down_net_returns),
            down_net_pnl_pct=sum(down_net_returns),
            avg_mfe_pct=sum(mfes) / len(mfes) if mfes else 0.0,
            avg_mae_pct=sum(maes) / len(maes) if maes else 0.0,
            worst_trade_net_pct=min(net_returns, default=0.0),
            best_trade_net_pct=max(net_returns, default=0.0),
        )

        return trades, summary
