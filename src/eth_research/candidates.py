"""Candidate Trading Strategy Engines and Portability Interfaces.

Includes:
- Candidate A: Baseline V22-R (15m holding)
- Candidate B: Macro 4H Regime Confirmation (HTF filter)
- Candidate C: High-Conviction Gating (narrow spread, extreme edge)
- Candidate D: Volatility-Gated Tradeability Filter (ATR threshold)
- Candidate E: Volatility Expansion with Multi-Bar Holding
- Non-overlapping (Purged) Portfolio Simulator to eliminate position overlap bias.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional, Sequence, Tuple
from eth_research.policy import PolicyResult


@dataclasses.dataclass(frozen=True)
class CandidateDecision:
    bar_index: int
    timestamp_utc_ms: int
    policy_direction: str  # 'UP', 'DOWN', or 'NO_TRADE'
    tradeable: bool
    rejection_reason: str
    suggested_holding_bars: int
    model_probability: float
    model_spread: float
    market_regime: str
    estimated_cost_pct: float
    expected_edge_pct: float


class CandidateStrategyEngine:
    """Portable decision layer evaluating research candidates without modifying frozen V22-R."""

    def __init__(
        self,
        strategy_id: str,
        holding_bars: int = 1,
        min_atr_price_ratio: float = 0.0,
        require_htf_alignment: bool = False,
        min_probability_edge: float = 0.05,  # 0.55 / 0.45 threshold
        max_spread: float = 0.06,
        roundtrip_cost_pct: float = 0.12,
    ):
        self.strategy_id = strategy_id
        self.holding_bars = holding_bars
        self.min_atr_price_ratio = min_atr_price_ratio
        self.require_htf_alignment = require_htf_alignment
        self.min_probability_edge = min_probability_edge
        self.max_spread = max_spread
        self.roundtrip_cost_pct = roundtrip_cost_pct

    def evaluate_signal(
        self,
        bar_index: int,
        timestamp_utc_ms: int,
        policy_res: PolicyResult,
        features: Sequence[float],
    ) -> CandidateDecision:
        """Evaluate whether a baseline model signal satisfies the candidate strategy criteria."""
        direction = policy_res.direction
        p_avg = policy_res.average
        spread = policy_res.spread

        if direction not in ("UP", "DOWN"):
            return CandidateDecision(
                bar_index=bar_index,
                timestamp_utc_ms=timestamp_utc_ms,
                policy_direction="NO_TRADE",
                tradeable=False,
                rejection_reason=policy_res.reason,
                suggested_holding_bars=0,
                model_probability=p_avg,
                model_spread=spread,
                market_regime="NEUTRAL",
                estimated_cost_pct=self.roundtrip_cost_pct,
                expected_edge_pct=0.0,
            )

        # 1. Spread filter
        if spread > self.max_spread:
            return CandidateDecision(
                bar_index=bar_index,
                timestamp_utc_ms=timestamp_utc_ms,
                policy_direction="NO_TRADE",
                tradeable=False,
                rejection_reason=f"SPREAD_EXCEEDED ({spread:.4f} > {self.max_spread:.4f})",
                suggested_holding_bars=0,
                model_probability=p_avg,
                model_spread=spread,
                market_regime="DISAGREEMENT",
                estimated_cost_pct=self.roundtrip_cost_pct,
                expected_edge_pct=0.0,
            )

        # 2. Probability edge filter
        edge = abs(p_avg - 0.50)
        if edge < self.min_probability_edge:
            return CandidateDecision(
                bar_index=bar_index,
                timestamp_utc_ms=timestamp_utc_ms,
                policy_direction="NO_TRADE",
                tradeable=False,
                rejection_reason=f"INSUFFICIENT_PROBABILITY_EDGE ({p_avg:.4f})",
                suggested_holding_bars=0,
                model_probability=p_avg,
                model_spread=spread,
                market_regime="WEAK_SIGNAL",
                estimated_cost_pct=self.roundtrip_cost_pct,
                expected_edge_pct=0.0,
            )

        # 3. Macro 4H trend alignment (Feature 17 is at index 16)
        # Feature 17 = (4H close - 4H EMA13) / 4H ATR14
        htf_trend = features[16]
        if self.require_htf_alignment:
            if direction == "UP" and htf_trend <= 0:
                return CandidateDecision(
                    bar_index=bar_index,
                    timestamp_utc_ms=timestamp_utc_ms,
                    policy_direction="NO_TRADE",
                    tradeable=False,
                    rejection_reason="HTF_MACRO_COUNTERTREND (UP vs 4H Downtrend)",
                    suggested_holding_bars=0,
                    model_probability=p_avg,
                    model_spread=spread,
                    market_regime="COUNTER_TREND",
                    estimated_cost_pct=self.roundtrip_cost_pct,
                    expected_edge_pct=0.0,
                )
            elif direction == "DOWN" and htf_trend >= 0:
                return CandidateDecision(
                    bar_index=bar_index,
                    timestamp_utc_ms=timestamp_utc_ms,
                    policy_direction="NO_TRADE",
                    tradeable=False,
                    rejection_reason="HTF_MACRO_COUNTERTREND (DOWN vs 4H Uptrend)",
                    suggested_holding_bars=0,
                    model_probability=p_avg,
                    model_spread=spread,
                    market_regime="COUNTER_TREND",
                    estimated_cost_pct=self.roundtrip_cost_pct,
                    expected_edge_pct=0.0,
                )

        # 4. Volatility tradeability gate (Feature 10: ATR7/price at index 9)
        atr_ratio = features[9]
        if atr_ratio < self.min_atr_price_ratio:
            return CandidateDecision(
                bar_index=bar_index,
                timestamp_utc_ms=timestamp_utc_ms,
                policy_direction="NO_TRADE",
                tradeable=False,
                rejection_reason=f"LOW_VOLATILITY_TRAP (ATR/P {atr_ratio:.5f} < {self.min_atr_price_ratio:.5f})",
                suggested_holding_bars=0,
                model_probability=p_avg,
                model_spread=spread,
                market_regime="COMPRESSED_VOL",
                estimated_cost_pct=self.roundtrip_cost_pct,
                expected_edge_pct=0.0,
            )

        regime_label = "EXPANDING_VOL" if atr_ratio >= 0.0020 else "NORMAL_VOL"

        return CandidateDecision(
            bar_index=bar_index,
            timestamp_utc_ms=timestamp_utc_ms,
            policy_direction=direction,
            tradeable=True,
            rejection_reason="PASSED_CANDIDATE_GATES",
            suggested_holding_bars=self.holding_bars,
            model_probability=p_avg,
            model_spread=spread,
            market_regime=regime_label,
            estimated_cost_pct=self.roundtrip_cost_pct,
            expected_edge_pct=abs(p_avg - 0.50) * 0.5, # conservative estimate
        )
