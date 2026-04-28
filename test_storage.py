"""Test script for storage and repository modules."""

from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import os
import sys

# Add src to path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root / "src"))

from finer.schemas.trade_action import (
    TradeAction,
    SourceInfo,
    TargetInfo,
    TradeDirection,
    ActionType,
    ActionStep,
    ValidationStatus,
)
from finer.services.storage import DateRange, TradeActionDB
from finer.services.repository import TradeActionRepository, KOLTimeline


def test_storage_basic():
    """Test basic storage operations."""
    print("Testing TradeActionDB...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = TradeActionDB(db_path)

        # Create test action
        action = TradeAction(
            trade_action_id="test-001",
            timestamp=datetime.now(),
            source=SourceInfo(
                creator_id="kol_123",
                content_id="content_456",
                evidence_text="AAPL looks bullish",
            ),
            target=TargetInfo(
                ticker="AAPL",
                ticker_normalized="AAPL",
                market="US",
            ),
            direction=TradeDirection.BULLISH,
            action_chain=[
                ActionStep(sequence=1, action_type=ActionType.LONG)
            ],
        )

        # Test upsert
        db.upsert(action)
        print("  - upsert: OK")

        # Test get_by_id
        record = db.get_by_id("test-001")
        assert record is not None
        assert record["trade_action_id"] == "test-001"
        assert record["creator_id"] == "kol_123"
        assert record["ticker_normalized"] == "AAPL"
        assert record["direction"] == "bullish"
        print("  - get_by_id: OK")

        # Test query by creator
        results = db.query(creator_id="kol_123")
        assert len(results) == 1
        print("  - query by creator: OK")

        # Test query by ticker
        results = db.query(ticker="AAPL")
        assert len(results) == 1
        print("  - query by ticker: OK")

        # Test count
        count = db.count(creator_id="kol_123")
        assert count == 1
        print("  - count: OK")

        # Test timeline stats
        stats = db.get_timeline_stats("kol_123")
        assert stats["total_actions"] == 1
        assert stats["by_direction"].get("bullish") == 1
        print("  - timeline stats: OK")

        # Test delete
        deleted = db.delete("test-001")
        assert deleted
        assert db.get_by_id("test-001") is None
        print("  - delete: OK")

    print("TradeActionDB: PASSED\n")


def test_repository_basic():
    """Test basic repository operations."""
    print("Testing TradeActionRepository...")

    with tempfile.TemporaryDirectory() as tmpdir:
        action_dir = Path(tmpdir) / "actions"
        db_path = Path(tmpdir) / "cache" / "test.db"

        repo = TradeActionRepository(db_path=db_path, action_dir=action_dir)

        # Create test action
        action = TradeAction(
            trade_action_id="repo-test-001",
            timestamp=datetime.now(),
            source=SourceInfo(
                creator_id="kol_789",
                content_id="content_abc",
                evidence_text="TSLA to the moon",
            ),
            target=TargetInfo(
                ticker="TSLA",
                ticker_normalized="TSLA",
                market="US",
            ),
            direction=TradeDirection.BULLISH,
            action_chain=[
                ActionStep(sequence=1, action_type=ActionType.LONG)
            ],
            confidence=0.85,
        )

        # Test save
        saved_path = repo.save(action)
        assert saved_path.exists(), f"File not created: {saved_path}"
        print(f"  - save: OK ({saved_path.name})")

        # Test load
        loaded = repo.load("repo-test-001")
        assert loaded is not None
        assert loaded.trade_action_id == "repo-test-001"
        assert loaded.direction == TradeDirection.BULLISH
        assert loaded.confidence == 0.85
        print("  - load: OK")

        # Test query by KOL
        results = repo.query_by_kol("kol_789")
        assert len(results) == 1
        print("  - query_by_kol: OK")

        # Test query by ticker
        results = repo.query_by_ticker("TSLA")
        assert len(results) == 1
        print("  - query_by_ticker: OK")

        # Test get_timeline
        timeline = repo.get_timeline("kol_789")
        assert timeline.creator_id == "kol_789"
        assert timeline.total_actions == 1
        assert timeline.bullish_count == 1
        assert "TSLA" in timeline.tickers
        print("  - get_timeline: OK")

        # Test count
        count = repo.count(creator_id="kol_789")
        assert count == 1
        print("  - count: OK")

        # Test get_all_tickers
        tickers = repo.get_all_tickers()
        assert "TSLA" in tickers
        print("  - get_all_tickers: OK")

        # Test get_all_kols
        kols = repo.get_all_kols()
        assert "kol_789" in kols
        print("  - get_all_kols: OK")

        # Test rebuild_index
        stats = repo.rebuild_index()
        assert stats["indexed"] == 1
        assert stats["failed"] == 0
        print("  - rebuild_index: OK")

        # Test update_validation_status
        updated = repo.update_validation_status(
            "repo-test-001",
            ValidationStatus.VERIFIED,
        )
        assert updated
        loaded = repo.load("repo-test-001")
        assert loaded.validation_status == ValidationStatus.VERIFIED
        print("  - update_validation_status: OK")

    print("TradeActionRepository: PASSED\n")


def test_date_range_query():
    """Test date range queries."""
    print("Testing date range queries...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = TradeActionDB(db_path)

        now = datetime.now()

        # Create actions at different times
        for i in range(5):
            action = TradeAction(
                trade_action_id=f"date-test-{i}",
                timestamp=now - timedelta(days=i),
                source=SourceInfo(
                    creator_id="kol_date",
                    content_id=f"content_{i}",
                    evidence_text=f"Test {i}",
                ),
                target=TargetInfo(
                    ticker=f"TICK{i}",
                    ticker_normalized=f"TICK{i}",
                ),
                direction=TradeDirection.BULLISH,
                action_chain=[ActionStep(sequence=1, action_type=ActionType.LONG)],
            )
            db.upsert(action)

        # Query last 2 days
        date_range = DateRange(
            start=now - timedelta(days=2),
            end=now + timedelta(minutes=1),
        )
        results = db.query(creator_id="kol_date", date_range=date_range)
        assert len(results) == 3  # today, yesterday, 2 days ago
        print(f"  - date range query (2 days): {len(results)} results, OK")

        # Count
        count = db.count(creator_id="kol_date", date_range=date_range)
        assert count == 3
        print("  - date range count: OK")

    print("Date range queries: PASSED\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Storage & Repository Tests")
    print("=" * 60 + "\n")

    try:
        test_storage_basic()
        test_repository_basic()
        test_date_range_query()

        print("=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
