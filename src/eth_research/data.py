"""Historical Market Data Infrastructure for ETHUSDT Futures Quantitative Research.

Guarantees:
1. Purely causal market data ingestion (public Binance Futures USD-M endpoints).
2. Strict candle completion checks and native 4H Binance bucket alignment.
3. Sorted UTC millisecond timestamps with explicit Europe/Istanbul conversions.
4. Duplicate detection, gap detection, and OHLC integrity checks.
5. Absolute containment and programmatic blocking of the sealed V23 test window.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import json
import logging
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Fallback for Windows systems without the tzdata package installed:
try:
    from zoneinfo import ZoneInfo
    ISTANBUL_TZ: datetime.tzinfo = ZoneInfo("Europe/Istanbul")
except Exception:
    # Europe/Istanbul is permanently UTC+03:00 without daylight saving shifts since 2016
    ISTANBUL_TZ = datetime.timezone(datetime.timedelta(hours=3), name="Europe/Istanbul")

UTC_TZ = datetime.timezone.utc

# V23 Sealed Window (July 5, 2025 00:00:00 to July 11, 2025 23:59:59 Europe/Istanbul)
# 2025-07-05 00:00:00+03:00 -> 2025-07-04 21:00:00 UTC -> 1751662800000 ms
# 2025-07-11 23:59:59+03:00 -> 2025-07-11 20:59:59 UTC -> 1752267599000 ms
# Any candle whose open time or close time falls inside this window is strictly forbidden.
V23_START_MS: int = 1751662800000
V23_END_MS: int = 1752267599999

VALID_TIMEFRAMES = {
    "15m": 15 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


class SealedWindowViolationError(PermissionError):
    """Raised when an attempt is made to access, download, or inspect sealed V23 data."""


class CandleIntegrityError(ValueError):
    """Raised when OHLC consistency or timestamp validation fails."""


@dataclass(frozen=True)
class Candle:
    open_time: int  # UTC ms
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int  # UTC ms
    quote_volume: float
    trades: int
    taker_buy_base: float
    taker_buy_quote: float

    @property
    def is_valid_ohlc(self) -> bool:
        if not (self.high >= self.low and self.high >= self.open and self.high >= self.close):
            return False
        if not (self.low <= self.open and self.low <= self.close):
            return False
        if any(math.isnan(x) or math.isinf(x) or x <= 0 for x in (self.open, self.high, self.low, self.close)):
            return False
        return True

    @property
    def open_dt_utc(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.open_time / 1000.0, tz=UTC_TZ)

    @property
    def open_dt_istanbul(self) -> datetime.datetime:
        return self.open_dt_utc.astimezone(ISTANBUL_TZ)


def check_v23_sealed_overlap(start_ms: Optional[int], end_ms: Optional[int]) -> None:
    """Ensure no requested or processed interval intersects the sealed V23 test window."""
    if start_ms is None and end_ms is None:
        return
    s = start_ms if start_ms is not None else 0
    e = end_ms if end_ms is not None else 0x7FFFFFFFFFFFFFFF
    if max(s, V23_START_MS) <= min(e, V23_END_MS):
        raise SealedWindowViolationError(
            f"Access Denied: Requested range [{s}, {e}] overlaps with the sealed V23 test window "
            f"[{V23_START_MS}, {V23_END_MS}] (2025-07-05 00:00 to 2025-07-11 23:59:59 Istanbul). "
            "Under research protocol, V23 data cannot be accessed or inspected."
        )


def validate_candle_sequence(candles: List[Candle], timeframe: str) -> None:
    """Validate sorting, uniqueness, completeness, and non-overlap of candle series."""
    if timeframe not in VALID_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    step_ms = VALID_TIMEFRAMES[timeframe]

    for i, c in enumerate(candles):
        if not c.is_valid_ohlc:
            raise CandleIntegrityError(f"Invalid OHLC relationship at bar {i}, open_time={c.open_time}: {c}")

        # Check V23 contamination
        check_v23_sealed_overlap(c.open_time, c.close_time)

        # Native 4H Binance bucket alignment: open_time % step_ms == 0
        if c.open_time % step_ms != 0:
            raise CandleIntegrityError(
                f"Candle open_time {c.open_time} is not aligned with {timeframe} interval (mod {step_ms} != 0)"
            )

        if i > 0:
            prev = candles[i - 1]
            if c.open_time <= prev.open_time:
                raise CandleIntegrityError(
                    f"Duplicate or non-ascending timestamp at index {i}: current={c.open_time}, prev={prev.open_time}"
                )
            if c.open_time != prev.open_time + step_ms:
                gap_bars = (c.open_time - prev.open_time) // step_ms - 1
                raise CandleIntegrityError(
                    f"Data gap detected before open_time {c.open_time}: missing {gap_bars} {timeframe} candles"
                )


def parse_binance_kline_raw(row: list) -> Candle:
    """Parse raw Binance API kline array into Candle dataclass."""
    return Candle(
        open_time=int(row[0]),
        open=float(row[1]),
        high=float(row[2]),
        low=float(row[3]),
        close=float(row[4]),
        volume=float(row[5]),
        close_time=int(row[6]),
        quote_volume=float(row[7]),
        trades=int(row[8]),
        taker_buy_base=float(row[9]),
        taker_buy_quote=float(row[10]),
    )


class BinanceFuturesDataClient:
    """Public market data client for Binance USD-M Futures with caching and safety gates."""

    BASE_URL = "https://fapi.binance.com/fapi/v1/klines"

    def __init__(self, cache_dir: str | Path = "data/raw"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_klines_chunk(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000,
        max_retries: int = 3,
        backoff_sec: float = 1.0,
    ) -> List[Candle]:
        """Fetch a single paginated chunk of public klines."""
        check_v23_sealed_overlap(start_time, end_time)

        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1000),
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ETH-Quant-Research/1.0",
                "Accept": "application/json",
            },
        )

        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"Binance API returned HTTP {resp.status}")
                    data = json.loads(resp.read().decode("utf-8"))
                    candles = [parse_binance_kline_raw(r) for r in data]
                    # Verify no returned candle violates V23 sealed gate
                    for c in candles:
                        check_v23_sealed_overlap(c.open_time, c.close_time)
                    return candles
            except urllib.error.HTTPError as e:
                if e.code == 429:  # Rate limited
                    retry_after = float(e.headers.get("Retry-After", backoff_sec * (2**attempt)))
                    time.sleep(retry_after)
                elif attempt == max_retries - 1:
                    raise
                else:
                    time.sleep(backoff_sec * (2**attempt))
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(backoff_sec * (2**attempt))
        return []

    def fetch_range(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
        cache: bool = True,
    ) -> List[Candle]:
        """Fetch full chronological range with automatic pagination and local disk caching."""
        check_v23_sealed_overlap(start_ms, end_ms)

        cache_file = self.cache_dir / f"{symbol}_{interval}_{start_ms}_{end_ms}.json"
        if cache and cache_file.exists():
            return self.load_candles_from_json(cache_file)

        step_ms = VALID_TIMEFRAMES[interval]
        all_candles: List[Candle] = []
        curr_start = start_ms

        while curr_start <= end_ms:
            # Check overlap again defensively
            check_v23_sealed_overlap(curr_start, end_ms)
            chunk = self.fetch_klines_chunk(
                symbol=symbol,
                interval=interval,
                start_time=curr_start,
                end_time=end_ms,
                limit=1000,
            )
            if not chunk:
                break

            for c in chunk:
                if c.open_time <= end_ms:
                    if not all_candles or c.open_time > all_candles[-1].open_time:
                        all_candles.append(c)

            last_open = chunk[-1].open_time
            next_start = last_open + step_ms
            if next_start <= curr_start:
                break
            curr_start = next_start
            time.sleep(0.05)  # Respect API rate limits

        validate_candle_sequence(all_candles, interval)

        if cache and all_candles:
            self.save_candles_to_json(all_candles, cache_file, symbol, interval)

        return all_candles

    @staticmethod
    def save_candles_to_json(
        candles: List[Candle],
        filepath: Path,
        symbol: str,
        interval: str,
    ) -> None:
        """Save raw candle data with metadata, provenance, and SHA-256."""
        payload = {
            "symbol": symbol,
            "interval": interval,
            "retrieved_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "candle_count": len(candles),
            "start_time_utc": candles[0].open_dt_utc.isoformat() if candles else None,
            "end_time_utc": candles[-1].open_dt_utc.isoformat() if candles else None,
            "data": [asdict(c) for c in candles],
        }
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        checksum = hashlib.sha256(encoded).hexdigest()
        payload["sha256"] = checksum
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @staticmethod
    def load_candles_from_json(filepath: Path) -> List[Candle]:
        """Load candles from local cache file with V23 integrity check."""
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
        candles = [Candle(**item) for item in payload["data"]]
        for c in candles:
            check_v23_sealed_overlap(c.open_time, c.close_time)
        return candles
