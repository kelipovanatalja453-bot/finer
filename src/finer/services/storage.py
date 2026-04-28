"""Lightweight SQLite storage layer for Finer.

This module provides a SQLite-based indexing layer on top of the file-based
storage. The file system remains the source of truth; SQLite serves as an
index for efficient queries.

Key Design Principles:
1. File system is authoritative; SQLite is derived
2. Support rebuilding index from files
3. Queries should be O(log n) via proper indexing
4. Minimal dependencies (only sqlite3 from stdlib)
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from finer.paths import DATA_ROOT
from finer.schemas.trade_action import (
    TradeAction,
    TradeDirection,
    ValidationStatus,
)


@dataclass
class DateRange:
    """Date range filter for queries."""
    start: datetime
    end: datetime

    def to_tuple(self) -> Tuple[str, str]:
        """Convert to ISO format strings for SQLite."""
        return (self.start.isoformat(), self.end.isoformat())


class TradeActionDB:
    """SQLite-based index for TradeAction records.

    This is a low-level storage primitive. For higher-level operations,
    use TradeActionRepository.
    """

    def __init__(self, db_path: Path = DATA_ROOT / "cache" / "trade_actions.db"):
        """Initialize the database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main index table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_actions (
                    trade_action_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    creator_id TEXT,
                    content_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    ticker_normalized TEXT,
                    direction TEXT NOT NULL,
                    validation_status TEXT NOT NULL DEFAULT 'pending',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    requires_manual_review INTEGER NOT NULL DEFAULT 0,
                    file_path TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_actions_timestamp
                ON trade_actions(timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_actions_creator_id
                ON trade_actions(creator_id, timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_actions_ticker
                ON trade_actions(ticker_normalized, timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_actions_direction
                ON trade_actions(direction, timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_actions_validation
                ON trade_actions(validation_status, requires_manual_review)
            """)

            # Metadata table for tracking index state
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS index_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper configuration.

        Uses thread-local connection pooling for better performance.
        Each thread maintains its own connection, avoiding repeated open/close.
        """
        import threading

        # Thread-local storage for connections
        if not hasattr(self, "_thread_local"):
            self._thread_local = threading.local()

        # Check for existing connection in this thread
        conn = getattr(self._thread_local, "conn", None)

        if conn is None:
            # Create new connection for this thread
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,  # 30 second timeout for locks
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")  # 30s busy timeout
            self._thread_local.conn = conn

        try:
            yield conn
        except sqlite3.OperationalError:
            # On error, invalidate the connection
            self._thread_local.conn = None
            raise

    def close_connection(self) -> None:
        """Close the thread-local connection if it exists."""
        import threading

        if hasattr(self, "_thread_local"):
            conn = getattr(self._thread_local, "conn", None)
            if conn is not None:
                conn.close()
                self._thread_local.conn = None

    def upsert(self, action: TradeAction, file_path: Optional[str] = None) -> None:
        """Insert or update a trade action record.

        Args:
            action: TradeAction to index.
            file_path: Optional path to source file.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            now = datetime.now().isoformat()
            ticker_normalized = action.target.ticker_normalized or action.target.ticker.upper()

            cursor.execute("""
                INSERT INTO trade_actions (
                    trade_action_id, timestamp, creator_id, content_id,
                    ticker, ticker_normalized, direction, validation_status,
                    confidence, requires_manual_review, file_path, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_action_id) DO UPDATE SET
                    timestamp = excluded.timestamp,
                    creator_id = excluded.creator_id,
                    content_id = excluded.content_id,
                    ticker = excluded.ticker,
                    ticker_normalized = excluded.ticker_normalized,
                    direction = excluded.direction,
                    validation_status = excluded.validation_status,
                    confidence = excluded.confidence,
                    requires_manual_review = excluded.requires_manual_review,
                    file_path = excluded.file_path,
                    updated_at = excluded.updated_at
            """, (
                action.trade_action_id,
                action.timestamp.isoformat(),
                action.source.creator_id,
                action.source.content_id,
                action.target.ticker,
                ticker_normalized,
                action.direction.value,
                action.validation_status.value,
                action.confidence,
                1 if action.requires_manual_review else 0,
                file_path,
                now,
            ))

            conn.commit()

    def delete(self, trade_action_id: str) -> bool:
        """Delete a trade action from the index.

        Args:
            trade_action_id: ID of the action to delete.

        Returns:
            True if a record was deleted.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM trade_actions WHERE trade_action_id = ?",
                (trade_action_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_by_id(self, trade_action_id: str) -> Optional[Dict[str, Any]]:
        """Get a trade action by ID.

        Args:
            trade_action_id: ID of the action.

        Returns:
            Dictionary with row data, or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM trade_actions WHERE trade_action_id = ?",
                (trade_action_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def query(
        self,
        creator_id: Optional[str] = None,
        ticker: Optional[str] = None,
        direction: Optional[str] = None,
        validation_status: Optional[str] = None,
        date_range: Optional[DateRange] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query trade actions with filters.

        Args:
            creator_id: Filter by KOL/creator ID.
            ticker: Filter by normalized ticker.
            direction: Filter by direction (bullish/bearish/neutral).
            validation_status: Filter by validation status.
            date_range: Filter by timestamp range.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of matching rows as dictionaries.
        """
        conditions = []
        params: List[Any] = []

        if creator_id:
            conditions.append("creator_id = ?")
            params.append(creator_id)

        if ticker:
            conditions.append("ticker_normalized = ?")
            params.append(ticker.upper())

        if direction:
            conditions.append("direction = ?")
            params.append(direction.lower())

        if validation_status:
            conditions.append("validation_status = ?")
            params.append(validation_status)

        if date_range:
            conditions.append("timestamp BETWEEN ? AND ?")
            params.extend(date_range.to_tuple())

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT * FROM trade_actions
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def query_by_kols(
        self,
        kol_ids: List[str],
        limit_per_kol: int = 100,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Batch query trade actions for multiple KOLs.

        Single query for all KOLs, then group results in memory.
        Much faster than N individual queries for compare_kols.

        Args:
            kol_ids: List of KOL/creator IDs.
            limit_per_kol: Maximum results per KOL.

        Returns:
            Dict mapping kol_id -> list of matching rows.
        """
        if not kol_ids:
            return {}

        placeholders = ",".join("?" * len(kol_ids))
        query = f"""
            SELECT * FROM trade_actions
            WHERE creator_id IN ({placeholders})
            ORDER BY creator_id, timestamp DESC
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, kol_ids)
            all_rows = [dict(row) for row in cursor.fetchall()]

        # Group by creator_id and limit per KOL
        results: Dict[str, List[Dict[str, Any]]] = {}
        for row in all_rows:
            kol_id = row.get("creator_id", "")
            if kol_id not in results:
                results[kol_id] = []
            if len(results[kol_id]) < limit_per_kol:
                results[kol_id].append(row)

        return results

    def count(
        self,
        creator_id: Optional[str] = None,
        ticker: Optional[str] = None,
        direction: Optional[str] = None,
        validation_status: Optional[str] = None,
        date_range: Optional[DateRange] = None,
    ) -> int:
        """Count trade actions matching filters.

        Args:
            Same filters as query().

        Returns:
            Count of matching records.
        """
        conditions = []
        params: List[Any] = []

        if creator_id:
            conditions.append("creator_id = ?")
            params.append(creator_id)

        if ticker:
            conditions.append("ticker_normalized = ?")
            params.append(ticker.upper())

        if direction:
            conditions.append("direction = ?")
            params.append(direction.lower())

        if validation_status:
            conditions.append("validation_status = ?")
            params.append(validation_status)

        if date_range:
            conditions.append("timestamp BETWEEN ? AND ?")
            params.extend(date_range.to_tuple())

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"SELECT COUNT(*) as cnt FROM trade_actions WHERE {where_clause}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row["cnt"] if row else 0

    def get_distinct_values(self, column: str) -> List[str]:
        """Get distinct values for a column.

        Args:
            column: Column name (creator_id, ticker_normalized, direction).

        Returns:
            List of distinct values.
        """
        valid_columns = {"creator_id", "ticker_normalized", "direction", "validation_status"}
        if column not in valid_columns:
            raise ValueError(f"Invalid column: {column}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT DISTINCT {column} FROM trade_actions WHERE {column} IS NOT NULL ORDER BY {column}"
            )
            return [row[column] for row in cursor.fetchall()]

    def get_timeline_stats(self, creator_id: str) -> Dict[str, Any]:
        """Get timeline statistics for a KOL.

        Args:
            creator_id: KOL ID.

        Returns:
            Dictionary with stats (total, by direction, by status, date range).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total count
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM trade_actions WHERE creator_id = ?",
                (creator_id,)
            )
            total = cursor.fetchone()["cnt"]

            if total == 0:
                return {
                    "creator_id": creator_id,
                    "total_actions": 0,
                    "by_direction": {},
                    "by_status": {},
                    "date_range": None,
                }

            # By direction
            cursor.execute("""
                SELECT direction, COUNT(*) as cnt
                FROM trade_actions
                WHERE creator_id = ?
                GROUP BY direction
            """, (creator_id,))
            by_direction = {row["direction"]: row["cnt"] for row in cursor.fetchall()}

            # By status
            cursor.execute("""
                SELECT validation_status, COUNT(*) as cnt
                FROM trade_actions
                WHERE creator_id = ?
                GROUP BY validation_status
            """, (creator_id,))
            by_status = {row["validation_status"]: row["cnt"] for row in cursor.fetchall()}

            # Date range
            cursor.execute("""
                SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts
                FROM trade_actions
                WHERE creator_id = ?
            """, (creator_id,))
            row = cursor.fetchone()
            date_range = {
                "start": row["min_ts"],
                "end": row["max_ts"],
            } if row and row["min_ts"] else None

            return {
                "creator_id": creator_id,
                "total_actions": total,
                "by_direction": by_direction,
                "by_status": by_status,
                "date_range": date_range,
            }

    def set_metadata(self, key: str, value: str) -> None:
        """Set a metadata value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO index_metadata (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (key, value, datetime.now().isoformat()))
            conn.commit()

    def get_metadata(self, key: str) -> Optional[str]:
        """Get a metadata value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM index_metadata WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row["value"] if row else None

    def clear(self) -> None:
        """Clear all indexed data (keep schema)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trade_actions")
            cursor.execute("DELETE FROM index_metadata")
            conn.commit()
