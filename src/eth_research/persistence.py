"""Transactional Persistence and State Management for Paper Trading.

Guarantees:
- SQLite-backed ACID transactions with write-ahead logging (WAL).
- Append-only audit logs with UTC timestamps and event types:
  REAL_TIME, LATE_CATCHUP, OFFLINE_TEST.
- Prevents duplicate candle processing, duplicate signal generation, duplicate entries/exits.
- Corrupted/Inconsistent state triggers explicit exceptions without silent resetting.
- Stores active position, portfolio equity, closed trades, processed candles, and audit logs.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class StateIntegrityError(Exception):
    """Raised when persistent state is corrupted, inconsistent, or invalid."""


@dataclasses.dataclass(frozen=True)
class ActivePosition:
    position_id: str
    direction: str  # 'UP' or 'DOWN'
    entry_bar_time_ms: int
    entry_price_nominal: float
    entry_price_effective: float
    atr7: float
    stop_loss_price: float
    take_profit_price: float
    max_holding_bars: int
    bars_held: int
    mfe_pct: float
    mae_pct: float
    position_size_usd: float

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ActivePosition:
        return cls(**data)


@dataclasses.dataclass(frozen=True)
class PortfolioState:
    equity: float
    peak_equity: float
    initial_equity: float
    active_position: Optional[ActivePosition]
    last_processed_candle_open_ms: Optional[int]
    total_trades_count: int
    version: int = 1


class PersistentStateManager:
    """ACID-compliant SQLite state manager for independent paper-trading."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
        return self._conn

    def close(self) -> None:
        """Close lingering connections to allow safe cleanup on Windows."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            # Metadata & system settings
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS system_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            # Portfolio State (Single row)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    equity REAL NOT NULL,
                    peak_equity REAL NOT NULL,
                    initial_equity REAL NOT NULL,
                    active_position_json TEXT,
                    last_processed_candle_open_ms INTEGER,
                    total_trades_count INTEGER NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                """
            )
            # Processed candles (idempotency barrier)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_candles (
                    timeframe TEXT NOT NULL,
                    open_time_ms INTEGER NOT NULL,
                    close_time_ms INTEGER NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    processed_at_utc TEXT NOT NULL,
                    PRIMARY KEY (timeframe, open_time_ms)
                );
                """
            )
            # Signals ledger (idempotency barrier)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluated_signals (
                    open_time_ms INTEGER PRIMARY KEY,
                    close_price REAL NOT NULL,
                    atr7 REAL NOT NULL,
                    p_avg REAL NOT NULL,
                    spread REAL NOT NULL,
                    min_distance REAL NOT NULL,
                    direction TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    evaluated_at_utc TEXT NOT NULL
                );
                """
            )
            # Executed Trades ledger
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_ledger (
                    trade_id INTEGER PRIMARY KEY,
                    position_id TEXT UNIQUE NOT NULL,
                    direction TEXT NOT NULL,
                    entry_time_ms INTEGER NOT NULL,
                    exit_time_ms INTEGER NOT NULL,
                    entry_price_nominal REAL NOT NULL,
                    entry_price_effective REAL NOT NULL,
                    exit_price_nominal REAL NOT NULL,
                    exit_price_effective REAL NOT NULL,
                    exit_reason TEXT NOT NULL,
                    holding_bars INTEGER NOT NULL,
                    gross_pnl_pct REAL NOT NULL,
                    total_cost_pct REAL NOT NULL,
                    net_pnl_pct REAL NOT NULL,
                    net_pnl_usd REAL NOT NULL,
                    mfe_pct REAL NOT NULL,
                    mae_pct REAL NOT NULL,
                    equity_after_usd REAL NOT NULL,
                    drawdown_pct REAL NOT NULL,
                    recorded_at_utc TEXT NOT NULL
                );
                """
            )
            # Append-only Audit Log
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    candle_open_ms INTEGER,
                    payload_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
                """
            )
            conn.commit()

    def initialize_portfolio_if_empty(self, initial_equity: float = 10000.0) -> PortfolioState:
        """Initialize portfolio state if table is empty; otherwise validate and load existing."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM portfolio_state WHERE id = 1;")
            row = cursor.fetchone()
            if row is None:
                now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cursor.execute(
                    """
                    INSERT INTO portfolio_state (
                        id, equity, peak_equity, initial_equity,
                        active_position_json, last_processed_candle_open_ms,
                        total_trades_count, updated_at_utc
                    ) VALUES (1, ?, ?, ?, NULL, NULL, 0, ?);
                    """,
                    (initial_equity, initial_equity, initial_equity, now_utc),
                )
                self.record_audit_event_tx(
                    cursor,
                    event_type="OFFLINE_TEST",
                    event_name="PORTFOLIO_INITIALIZED",
                    candle_open_ms=None,
                    payload={"initial_equity": initial_equity},
                )
                conn.commit()
                return PortfolioState(
                    equity=initial_equity,
                    peak_equity=initial_equity,
                    initial_equity=initial_equity,
                    active_position=None,
                    last_processed_candle_open_ms=None,
                    total_trades_count=0,
                )
            else:
                return self._parse_portfolio_state_row(row)

    def load_portfolio_state(self) -> PortfolioState:
        """Load and validate current portfolio state with strict integrity checks."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM portfolio_state WHERE id = 1;")
            row = cursor.fetchone()
            if row is None:
                raise StateIntegrityError("Portfolio state row does not exist in database.")
            return self._parse_portfolio_state_row(row)

    def _parse_portfolio_state_row(self, row: sqlite3.Row) -> PortfolioState:
        equity = float(row["equity"])
        peak_equity = float(row["peak_equity"])
        initial_equity = float(row["initial_equity"])
        total_trades = int(row["total_trades_count"])
        last_ms = row["last_processed_candle_open_ms"]

        if equity <= 0 or peak_equity <= 0 or initial_equity <= 0:
            raise StateIntegrityError(f"Corrupted equity values detected: equity={equity}, peak={peak_equity}")

        active_pos_raw = row["active_position_json"]
        active_pos: Optional[ActivePosition] = None
        if active_pos_raw:
            try:
                active_pos_dict = json.loads(active_pos_raw)
                active_pos = ActivePosition.from_dict(active_pos_dict)
            except Exception as e:
                raise StateIntegrityError(f"Failed to parse active position JSON: {e}") from e

        return PortfolioState(
            equity=equity,
            peak_equity=peak_equity,
            initial_equity=initial_equity,
            active_position=active_pos,
            last_processed_candle_open_ms=last_ms,
            total_trades_count=total_trades,
        )

    def is_candle_processed(self, timeframe: str, open_time_ms: int) -> bool:
        """Check if candle was already ingested and processed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM processed_candles WHERE timeframe = ? AND open_time_ms = ?;",
                (timeframe, open_time_ms),
            )
            return cursor.fetchone() is not None

    def is_signal_evaluated(self, open_time_ms: int) -> bool:
        """Check if signal for bar t was already evaluated."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM evaluated_signals WHERE open_time_ms = ?;",
                (open_time_ms,),
            )
            return cursor.fetchone() is not None

    def get_evaluated_signal(self, open_time_ms: int) -> Optional[Dict[str, Any]]:
        """Retrieve evaluated signal dictionary for open_time_ms if present."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM evaluated_signals WHERE open_time_ms = ?;",
                (open_time_ms,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    def get_last_processed_candle(self, timeframe: str = "15m") -> Optional[Dict[str, Any]]:
        """Retrieve the most recently processed candle for timeframe."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM processed_candles WHERE timeframe = ? ORDER BY open_time_ms DESC LIMIT 1;",
                (timeframe,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    def get_processed_candles_count(self, timeframe: str = "15m") -> int:
        """Return total number of processed candles recorded for timeframe."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM processed_candles WHERE timeframe = ?;",
                (timeframe,),
            )
            return int(cursor.fetchone()[0])

    def record_audit_event_tx(
        self,
        cursor: sqlite3.Cursor,
        event_type: str,
        event_name: str,
        candle_open_ms: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        """Record an append-only audit event within an active transaction."""
        valid_types = {"REAL_TIME", "LATE_CATCHUP", "OFFLINE_TEST"}
        if event_type not in valid_types:
            raise ValueError(f"Invalid event_type '{event_type}'. Must be one of {valid_types}")

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO audit_events (
                event_type, event_name, candle_open_ms, payload_json, created_at_utc
            ) VALUES (?, ?, ?, ?, ?);
            """,
            (event_type, event_name, candle_open_ms, json.dumps(payload), now_utc),
        )

    def record_audit_event(
        self,
        event_type: str,
        event_name: str,
        candle_open_ms: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            self.record_audit_event_tx(cursor, event_type, event_name, candle_open_ms, payload)
            conn.commit()

    def commit_state_transition(
        self,
        state: PortfolioState,
        processed_candle: dict,
        evaluated_signal: Optional[dict],
        trade_record: Optional[dict],
        audit_event_type: str,
        audit_event_name: str,
    ) -> None:
        """Atomic transaction to commit a single step of the paper-trading engine."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Idempotency Check
            cursor.execute("SELECT 1 FROM processed_candles WHERE timeframe = '15m' AND open_time_ms = ?;",
                           (processed_candle["open_time_ms"],))
            if cursor.fetchone() is not None:
                return  # Already processed

            # 2. Portfolio Update
            pos_json = json.dumps(state.active_position.to_dict()) if state.active_position else None
            now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute("""
                UPDATE portfolio_state
                SET equity=?, peak_equity=?, active_position_json=?,
                    last_processed_candle_open_ms=?, total_trades_count=?, updated_at_utc=?
                WHERE id = 1
            """, (state.equity, state.peak_equity, pos_json,
                  state.last_processed_candle_open_ms, state.total_trades_count, now_utc))

            # 3. Processed Candle Insert
            cursor.execute("""
                INSERT INTO processed_candles (
                    timeframe, open_time_ms, close_time_ms, open_price, high_price,
                    low_price, close_price, processed_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("15m", processed_candle["open_time_ms"], processed_candle["close_time_ms"],
                  processed_candle["open"], processed_candle["high"], processed_candle["low"],
                  processed_candle["close"], now_utc))

            # 4. Evaluated Signal Insert
            if evaluated_signal:
                cursor.execute("""
                    INSERT INTO evaluated_signals (
                        open_time_ms, close_price, atr7, p_avg, spread, min_distance,
                        direction, reason, evaluated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (evaluated_signal["open_time_ms"], evaluated_signal["close_price"],
                      evaluated_signal["atr7"], evaluated_signal["p_avg"],
                      evaluated_signal["spread"], evaluated_signal["min_distance"],
                      evaluated_signal["direction"], evaluated_signal["reason"], now_utc))

            # 5. Trade Ledger Insert
            if trade_record:
                cursor.execute("""
                    INSERT INTO trade_ledger (
                        position_id, direction, entry_time_ms, exit_time_ms,
                        entry_price_nominal, entry_price_effective, exit_price_nominal,
                        exit_price_effective, exit_reason, holding_bars, gross_pnl_pct,
                        total_cost_pct, net_pnl_pct, net_pnl_usd, mfe_pct, mae_pct,
                        equity_after_usd, drawdown_pct, recorded_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (trade_record["position_id"], trade_record["direction"],
                      trade_record["entry_time_ms"], trade_record["exit_time_ms"],
                      trade_record["entry_price_nominal"], trade_record["entry_price_effective"],
                      trade_record["exit_price_nominal"], trade_record["exit_price_effective"],
                      trade_record["exit_reason"], trade_record["holding_bars"],
                      trade_record["gross_pnl_pct"], trade_record["total_cost_pct"],
                      trade_record["net_pnl_pct"], trade_record["net_pnl_usd"],
                      trade_record["mfe_pct"], trade_record["mae_pct"],
                      trade_record["equity_after_usd"], trade_record["drawdown_pct"], now_utc))

            # 6. Audit Event Insert
            payload = {
                "candle_open_ms": processed_candle["open_time_ms"],
                "portfolio_equity": state.equity
            }
            if trade_record:
                payload["trade"] = trade_record
            if evaluated_signal:
                payload["signal"] = evaluated_signal

            self.record_audit_event_tx(
                cursor=cursor,
                event_type=audit_event_type,
                event_name=audit_event_name,
                candle_open_ms=processed_candle["open_time_ms"],
                payload=payload
            )
            # TX implicitly commits on exit

    def get_audit_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM audit_events ORDER BY event_id ASC LIMIT ?;",
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "event_id": r["event_id"],
                    "event_type": r["event_type"],
                    "event_name": r["event_name"],
                    "candle_open_ms": r["candle_open_ms"],
                    "payload": json.loads(r["payload_json"]),
                    "created_at_utc": r["created_at_utc"],
                }
                for r in rows
            ]

    def get_trade_ledger(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trade_ledger ORDER BY trade_id ASC;")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
