"""Causal Feature Engineering for ETHUSDT Futures Quantitative Research.

Implements the exact 18 features defined in V21/V22 methodology:
Features:
1. 1-bar return / ATR7
2. 3-bar return / ATR7
3. 6-bar return / ATR7
4. 12-bar return / ATR7
5. ER6
6. ER12
7. ER24
8. current 15m candle body / ATR7
9. current 15m candle range / ATR7
10. ATR7 / price (close)
11. ATR7 / ATR28
12. (EMA9 - EMA21) / ATR7
13. EMA21 4-bar slope / ATR7
14. 32-bar midpoint migration over 8 bars / ATR7
15. (close - 32-bar midpoint) / ATR7
16. 4H ER6
17. (4H close - EMA13) / 4H ATR14
18. 4H ATR7 / ATR28

Strict Causal Rules:
- Calculated ONLY on completed candles up to bar index t.
- Target is strictly the direction of the NEXT 15m candle (t+1 close > t+1 open).
- Higher timeframe (4H) bars are strictly those fully closed before or at the 15m bar close.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from eth_research.data import Candle, VALID_TIMEFRAMES, check_v23_sealed_overlap


def calculate_true_range(current: Candle, prev: Optional[Candle]) -> float:
    """True Range = max(H - L, |H - C_prev|, |L - C_prev|)."""
    if prev is None:
        return current.high - current.low
    return max(
        current.high - current.low,
        abs(current.high - prev.close),
        abs(current.low - prev.close),
    )


def calculate_atr_series(candles: List[Candle], period: int) -> List[Optional[float]]:
    """Compute simple rolling mean True Range (as documented in V22 reconstruction artifact)."""
    n = len(candles)
    if n == 0:
        return []
    trs: List[float] = []
    for i in range(n):
        prev = candles[i - 1] if i > 0 else None
        trs.append(calculate_true_range(candles[i], prev))

    atr: List[Optional[float]] = [None] * n
    if n < period:
        return atr

    # Rolling simple mean of TR over period
    window_sum = sum(trs[:period])
    atr[period - 1] = window_sum / period
    for i in range(period, n):
        window_sum += trs[i] - trs[i - period]
        atr[i] = window_sum / period
    return atr


def calculate_ema_series(values: List[float], period: int) -> List[Optional[float]]:
    """Compute standard recursive EMA: alpha = 2 / (period + 1).

    Initializes at index period - 1 with the simple moving average.
    """
    n = len(values)
    ema: List[Optional[float]] = [None] * n
    if n < period:
        return ema

    alpha = 2.0 / (period + 1.0)
    sma = sum(values[:period]) / period
    ema[period - 1] = sma

    curr = sma
    for i in range(period, n):
        curr = alpha * values[i] + (1.0 - alpha) * curr
        ema[i] = curr
    return ema


def calculate_er_series(candles: List[Candle], period: int) -> List[Optional[float]]:
    """Kaufman Efficiency Ratio = |Close_t - Close_{t-period}| / sum(|Close_i - Close_{i-1}|, i=t-period+1..t)."""
    n = len(candles)
    er: List[Optional[float]] = [None] * n
    if n <= period:
        return er

    for i in range(period, n):
        net_change = abs(candles[i].close - candles[i - period].close)
        path_length = sum(
            abs(candles[j].close - candles[j - 1].close)
            for j in range(i - period + 1, i + 1)
        )
        if path_length <= 1e-12:
            er[i] = 0.0
        else:
            er[i] = net_change / path_length
    return er


def calculate_midpoint_32_series(candles: List[Candle]) -> List[Optional[float]]:
    """Midpoint of 32-bar window: (max(High_32) + min(Low_32)) / 2."""
    n = len(candles)
    mid: List[Optional[float]] = [None] * n
    if n < 32:
        return mid

    for i in range(31, n):
        window = candles[i - 31 : i + 1]
        highest = max(c.high for c in window)
        lowest = min(c.low for c in window)
        mid[i] = (highest + lowest) / 2.0
    return mid


@dataclass(frozen=True)
class FeatureRow:
    index: int
    open_time_utc_ms: int
    close_time_utc_ms: int
    close_price: float
    features: List[float]  # Exactly 18 features
    label: Optional[int]   # 1 if next candle close > next candle open, else 0 (None if last bar)
    next_open: Optional[float]
    next_high: Optional[float]
    next_low: Optional[float]
    next_close: Optional[float]


def build_4h_context_lookup(
    candles_4h: List[Candle],
) -> Tuple[List[int], List[Optional[float]], List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """Precompute 4H features and return aligned by 4H close_time."""
    closes_4h = [c.close for c in candles_4h]
    close_times_4h = [c.close_time for c in candles_4h]

    er6_4h = calculate_er_series(candles_4h, 6)
    ema13_4h = calculate_ema_series(closes_4h, 13)
    atr7_4h = calculate_atr_series(candles_4h, 7)
    atr14_4h = calculate_atr_series(candles_4h, 14)
    atr28_4h = calculate_atr_series(candles_4h, 28)

    return close_times_4h, er6_4h, ema13_4h, atr7_4h, atr14_4h, atr28_4h


def extract_features(
    candles_15m: List[Candle],
    candles_4h: List[Candle],
    warmup_bars: int = 100,
) -> List[FeatureRow]:
    """Extract causal 18-feature vectors for 15m series with completed 4H context.

    Ensures no future data leakage:
    At candle t (15m):
    - Uses only 15m candles 0..t.
    - Uses only 4H candles with close_time <= candles_15m[t].close_time.
    - Label is computed from candles_15m[t+1] if available.
    """
    n_15m = len(candles_15m)
    if n_15m == 0:
        return []

    # Defensive V23 containment: ensure no input candle enters V23 sealed period
    for c in candles_15m:
        check_v23_sealed_overlap(c.open_time, c.close_time)
    for c in candles_4h:
        check_v23_sealed_overlap(c.open_time, c.close_time)

    # 15m core series
    closes_15m = [c.close for c in candles_15m]
    atr7_15m = calculate_atr_series(candles_15m, 7)
    atr28_15m = calculate_atr_series(candles_15m, 28)
    er6_15m = calculate_er_series(candles_15m, 6)
    er12_15m = calculate_er_series(candles_15m, 12)
    er24_15m = calculate_er_series(candles_15m, 24)
    ema9_15m = calculate_ema_series(closes_15m, 9)
    ema21_15m = calculate_ema_series(closes_15m, 21)
    mid32_15m = calculate_midpoint_32_series(candles_15m)

    # 4H context lookup
    (
        close_times_4h,
        er6_4h,
        ema13_4h,
        atr7_4h,
        atr14_4h,
        atr28_4h,
    ) = build_4h_context_lookup(candles_4h)

    rows: List[FeatureRow] = []
    htf_idx = 0
    n_4h = len(candles_4h)

    for t in range(n_15m):
        c_15m = candles_15m[t]

        # Advance 4H pointer causally: latest 4H candle fully completed before or exactly at 15m close
        while htf_idx + 1 < n_4h and candles_4h[htf_idx + 1].close_time <= c_15m.close_time:
            htf_idx += 1

        # Check warmup requirement
        if t < warmup_bars:
            continue

        # Check required series availability at 15m
        a7 = atr7_15m[t]
        a28 = atr28_15m[t]
        e6 = er6_15m[t]
        e12 = er12_15m[t]
        e24 = er24_15m[t]
        m9 = ema9_15m[t]
        m21 = ema21_15m[t]
        m21_prev4 = ema21_15m[t - 4] if t >= 4 else None
        mid = mid32_15m[t]
        mid_prev8 = mid32_15m[t - 8] if t >= 8 else None

        if None in (a7, a28, e6, e12, e24, m9, m21, m21_prev4, mid, mid_prev8) or a7 <= 1e-12:
            continue

        # Check 4H context availability
        if n_4h == 0 or candles_4h[htf_idx].close_time > c_15m.close_time:
            continue

        htf_er6 = er6_4h[htf_idx]
        htf_ema13 = ema13_4h[htf_idx]
        htf_atr7 = atr7_4h[htf_idx]
        htf_atr14 = atr14_4h[htf_idx]
        htf_atr28 = atr28_4h[htf_idx]

        if None in (htf_er6, htf_ema13, htf_atr7, htf_atr14, htf_atr28) or htf_atr14 <= 1e-12 or htf_atr28 <= 1e-12:
            continue

        # Construct 18 features:
        # 1. 1-bar return / ATR7
        f1 = (c_15m.close - candles_15m[t - 1].close) / a7
        # 2. 3-bar return / ATR7
        f2 = (c_15m.close - candles_15m[t - 3].close) / a7
        # 3. 6-bar return / ATR7
        f3 = (c_15m.close - candles_15m[t - 6].close) / a7
        # 4. 12-bar return / ATR7
        f4 = (c_15m.close - candles_15m[t - 12].close) / a7
        # 5. ER6
        f5 = e6
        # 6. ER12
        f6 = e12
        # 7. ER24
        f7 = e24
        # 8. current 15m candle body / ATR7
        f8 = (c_15m.close - c_15m.open) / a7
        # 9. current 15m candle range / ATR7
        f9 = (c_15m.high - c_15m.low) / a7
        # 10. ATR7 / price
        f10 = a7 / c_15m.close
        # 11. ATR7 / ATR28
        f11 = a7 / a28
        # 12. (EMA9 - EMA21) / ATR7
        f12 = (m9 - m21) / a7
        # 13. EMA21 4-bar slope / ATR7
        f13 = (m21 - m21_prev4) / a7
        # 14. 32-bar midpoint migration over 8 bars / ATR7
        f14 = (mid - mid_prev8) / a7
        # 15. (close - 32-bar midpoint) / ATR7
        f15 = (c_15m.close - mid) / a7
        # 16. 4H ER6
        f16 = htf_er6
        # 17. (4H close - EMA13) / 4H ATR14
        f17 = (candles_4h[htf_idx].close - htf_ema13) / htf_atr14
        # 18. 4H ATR7 / ATR28
        f18 = htf_atr7 / htf_atr28

        features = [f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12, f13, f14, f15, f16, f17, f18]

        # Target label: next 15m candle close > next 15m candle open
        label: Optional[int] = None
        next_o: Optional[float] = None
        next_h: Optional[float] = None
        next_l: Optional[float] = None
        next_c: Optional[float] = None

        if t + 1 < n_15m:
            next_candle = candles_15m[t + 1]
            label = 1 if next_candle.close > next_candle.open else 0
            next_o = next_candle.open
            next_h = next_candle.high
            next_l = next_candle.low
            next_c = next_candle.close

        rows.append(
            FeatureRow(
                index=t,
                open_time_utc_ms=c_15m.open_time,
                close_time_utc_ms=c_15m.close_time,
                close_price=c_15m.close,
                features=features,
                label=label,
                next_open=next_o,
                next_high=next_h,
                next_low=next_l,
                next_close=next_c,
            )
        )

    return rows
