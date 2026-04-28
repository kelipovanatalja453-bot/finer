"""Repository layer for TradeAction management.

This module provides high-level operations for TradeAction records,
bridging the file-based storage with the SQLite index layer.

Key Design Principles:
1. File system is the authoritative source
2. Repository coordinates file I/O and index updates
3. Supports rebuilding index from files
4. Provides domain-specific query methods
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from finer.paths import DATA_ROOT
from finer.schemas.trade_action import (
    TradeAction,
    TradeDirection,
    ValidationStatus,
)
from finer.services.storage import DateRange, TradeActionDB
from finer.services.performance import track_performance


@dataclass
class KOLTimeline:
    """Timeline summary for a KOL's trade actions."""
    creator_id: str
    total_actions: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    pending_count: int
    verified_count: int
    date_range: Optional[Dict[str, str]]
    tickers: Set[str] = field(default_factory=set)
    avg_confidence: float = 0.0


class TradeActionRepository:
    """Repository for TradeAction with file + index management.

    This is the primary interface for working with TradeAction records.
    It handles:
    - Reading/writing TradeAction files
    - Maintaining the SQLite index
    - Rebuilding index from files
    - Domain-specific queries
    """

    def __init__(
        self,
        db_path: Path = DATA_ROOT / "cache" / "trade_actions.db",
        action_dir: Path = DATA_ROOT / "L5_candidate",
    ):
        """Initialize repository.

        Args:
            db_path: Path to SQLite index database.
            action_dir: Directory containing TradeAction JSON files.
        """
        self.db = TradeActionDB(db_path)
        self.action_dir = action_dir
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.action_dir.mkdir(parents=True, exist_ok=True)
        self.db.db_path.parent.mkdir(parents=True, exist_ok=True)

    def index_trade_action(self, action: TradeAction, file_path: Optional[str] = None) -> None:
        """Index a TradeAction record.

        This method adds/updates the record in the SQLite index.
        It does NOT write to file - use save() for that.

        Args:
            action: TradeAction to index.
            file_path: Optional path to source file.
        """
        self.db.upsert(action, file_path)

    def save(self, action: TradeAction, file_path: Optional[Path] = None) -> Path:
        """Save a TradeAction to file and index it.

        Args:
            action: TradeAction to save.
            file_path: Optional explicit file path. If not provided,
                      uses action_dir/{ticker}_{timestamp}.action.json.

        Returns:
            Path to saved file.
        """
        if file_path is None:
            # Generate default path
            ticker = (action.target.ticker_normalized or action.target.ticker).upper()
            timestamp_str = action.timestamp.strftime("%Y%m%d_%H%M%S")
            file_path = self.action_dir / f"{ticker}_{timestamp_str}_{action.trade_action_id[:8]}.action.json"

        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(action.to_dict(), f, ensure_ascii=False, indent=2)

        # Update index
        self.index_trade_action(action, str(file_path))

        return file_path

    def load(self, trade_action_id: str) -> Optional[TradeAction]:
        """Load a TradeAction by ID.

        First checks the index for file path, then loads from file.

        Args:
            trade_action_id: ID of the action to load.

        Returns:
            TradeAction instance, or None if not found.
        """
        # Check index for file path
        record = self.db.get_by_id(trade_action_id)
        if record and record.get("file_path"):
            file_path = Path(record["file_path"])
            if file_path.exists():
                return self._load_from_file(file_path)

        # Fall back to scanning directory
        for file_path in self.action_dir.glob("*.action.json"):
            try:
                action = self._load_from_file(file_path)
                if action.trade_action_id == trade_action_id:
                    return action
            except Exception:
                continue

        return None

    def _load_from_file(self, file_path: Path) -> TradeAction:
        """Load TradeAction from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TradeAction.from_dict(data)

    def query_by_kol(
        self,
        kol_id: str,
        date_range: Optional[DateRange] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TradeAction]:
        """Query trade actions by KOL/creator ID.

        Args:
            kol_id: Creator/KOL identifier.
            date_range: Optional date range filter.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            List of matching TradeAction instances.
        """
        records = self.db.query(
            creator_id=kol_id,
            date_range=date_range,
            limit=limit,
            offset=offset,
        )

        actions = []
        for record in records:
            if record.get("file_path"):
                try:
                    action = self._load_from_file(Path(record["file_path"]))
                    actions.append(action)
                except Exception:
                    continue

        return actions

    def query_by_kols(
        self,
        kol_ids: List[str],
        limit_per_kol: int = 100,
    ) -> Dict[str, List[TradeAction]]:
        """Batch query trade actions for multiple KOLs.

        Single database query for all KOLs, avoiding N+1 pattern.

        Args:
            kol_ids: List of KOL/creator IDs.
            limit_per_kol: Maximum results per KOL.

        Returns:
            Dict mapping kol_id -> list of TradeAction instances.
        """
        records_by_kol = self.db.query_by_kols(kol_ids, limit_per_kol)

        results: Dict[str, List[TradeAction]] = {}
        for kol_id, records in records_by_kol.items():
            actions = []
            for record in records:
                if record.get("file_path"):
                    try:
                        action = self._load_from_file(Path(record["file_path"]))
                        actions.append(action)
                    except Exception:
                        continue
            results[kol_id] = actions

        return results

    def query_by_ticker(
        self,
        ticker: str,
        direction: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TradeAction]:
        """Query trade actions by ticker.

        Args:
            ticker: Ticker symbol (will be normalized).
            direction: Optional direction filter.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            List of matching TradeAction instances.
        """
        records = self.db.query(
            ticker=ticker,
            direction=direction,
            limit=limit,
            offset=offset,
        )

        actions = []
        for record in records:
            if record.get("file_path"):
                try:
                    action = self._load_from_file(Path(record["file_path"]))
                    actions.append(action)
                except Exception:
                    continue

        return actions

    def query_pending_review(self, limit: int = 50) -> List[TradeAction]:
        """Query trade actions pending manual review.

        Args:
            limit: Maximum results.

        Returns:
            List of TradeAction instances requiring review.
        """
        records = self.db.query(
            validation_status="pending",
            limit=limit,
        )

        actions = []
        for record in records:
            # Check requires_manual_review flag
            if record.get("requires_manual_review"):
                if record.get("file_path"):
                    try:
                        action = self._load_from_file(Path(record["file_path"]))
                        actions.append(action)
                    except Exception:
                        continue

        return actions

    @track_performance("timeline_query")
    def get_timeline(self, kol_id: str) -> KOLTimeline:
        """Get timeline summary for a KOL.

        Args:
            kol_id: KOL/creator identifier.

        Returns:
            KOLTimeline with statistics.
        """
        stats = self.db.get_timeline_stats(kol_id)

        # Get unique tickers
        records = self.db.query(creator_id=kol_id, limit=1000)
        tickers = {r["ticker_normalized"] for r in records if r.get("ticker_normalized")}

        # Calculate average confidence
        confidences = [r["confidence"] for r in records if r.get("confidence") is not None]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return KOLTimeline(
            creator_id=kol_id,
            total_actions=stats["total_actions"],
            bullish_count=stats["by_direction"].get("bullish", 0),
            bearish_count=stats["by_direction"].get("bearish", 0),
            neutral_count=stats["by_direction"].get("neutral", 0),
            pending_count=stats["by_status"].get("pending", 0),
            verified_count=stats["by_status"].get("verified", 0),
            date_range=stats["date_range"],
            tickers=tickers,
            avg_confidence=avg_conf,
        )

    def rebuild_index(self, batch_size: int = 100) -> Dict[str, int]:
        """Rebuild the SQLite index from all TradeAction files.

        Scans the action directory and reindexes all .action.json files.

        Args:
            batch_size: Number of records to process per transaction.

        Returns:
            Dictionary with stats: indexed, failed, total.
        """
        # Clear existing index
        self.db.clear()

        indexed = 0
        failed = 0

        # Scan for all .action.json files
        action_files = list(self.action_dir.glob("**/*.action.json"))
        total = len(action_files)

        for i, file_path in enumerate(action_files):
            try:
                action = self._load_from_file(file_path)
                self.index_trade_action(action, str(file_path))
                indexed += 1
            except Exception as e:
                failed += 1
                # Log error but continue
                print(f"Failed to index {file_path}: {e}")

        # Update metadata
        self.db.set_metadata("last_rebuild", datetime.now().isoformat())
        self.db.set_metadata("total_indexed", str(indexed))

        return {
            "indexed": indexed,
            "failed": failed,
            "total": total,
        }

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
            creator_id: Filter by KOL ID.
            ticker: Filter by ticker.
            direction: Filter by direction.
            validation_status: Filter by validation status.
            date_range: Filter by date range.

        Returns:
            Count of matching records.
        """
        return self.db.count(
            creator_id=creator_id,
            ticker=ticker,
            direction=direction,
            validation_status=validation_status,
            date_range=date_range,
        )

    def get_all_kols(self) -> List[str]:
        """Get list of all indexed KOL IDs.

        Returns:
            List of unique creator_id values.
        """
        return self.db.get_distinct_values("creator_id")

    def get_all_tickers(self) -> List[str]:
        """Get list of all indexed tickers.

        Returns:
            List of unique normalized ticker values.
        """
        return self.db.get_distinct_values("ticker_normalized")

    def update_validation_status(
        self,
        trade_action_id: str,
        status: ValidationStatus,
        issues: Optional[List[str]] = None,
    ) -> bool:
        """Update validation status for a trade action.

        Updates the index only. To persist to file, load, modify, and save.

        Args:
            trade_action_id: ID of the action.
            status: New validation status.
            issues: Optional list of validation issues.

        Returns:
            True if updated successfully.
        """
        record = self.db.get_by_id(trade_action_id)
        if not record or not record.get("file_path"):
            return False

        try:
            action = self._load_from_file(Path(record["file_path"]))
            action.validation_status = status
            if issues:
                action.validation_issues = issues

            # Save back to file and reindex
            self.save(action, Path(record["file_path"]))
            return True
        except Exception:
            return False

    def delete(self, trade_action_id: str, delete_file: bool = False) -> bool:
        """Delete a trade action from index and optionally from file.

        Args:
            trade_action_id: ID of the action to delete.
            delete_file: Whether to also delete the source file.

        Returns:
            True if deleted from index.
        """
        record = self.db.get_by_id(trade_action_id)

        if delete_file and record and record.get("file_path"):
            try:
                Path(record["file_path"]).unlink()
            except Exception:
                pass

        return self.db.delete(trade_action_id)


# Singleton instance for convenience (thread-safe)
from functools import lru_cache

@lru_cache(maxsize=1)
def get_repository() -> TradeActionRepository:
    """Get the singleton repository instance (thread-safe)."""
    return TradeActionRepository()
