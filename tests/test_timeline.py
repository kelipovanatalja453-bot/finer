"""Tests for F7 Timeline Engine."""

from datetime import datetime

import pytest

from finer.schemas.trade_action import (
    TradeAction,
    TradeDirection,
    ValidationStatus,
    SourceInfo,
    TargetInfo,
    ActionStep,
    ActionType,
)
from finer.timeline.models import (
    TimelineEntry,
    TimelineSummary,
    KOLTimeline,
    TimelineFilter,
    KOLComparison,
    KOLComparisonEntry,
)
from finer.timeline.engine import TimelineEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_action(
    ticker: str = "AAPL",
    direction: TradeDirection = TradeDirection.BULLISH,
    confidence: float = 0.8,
    validation_status: ValidationStatus = ValidationStatus.PENDING,
    creator_id: str = "kol_001",
    timestamp: datetime | None = None,
) -> TradeAction:
    """Create a minimal TradeAction for testing."""
    return TradeAction(
        trade_action_id=f"ta_{ticker}_{direction.value}",
        timestamp=timestamp or datetime(2026, 1, 15, 12, 0, 0),
        source=SourceInfo(
            creator_id=creator_id,
            content_id="content_001",
            evidence_text="AAPL looking strong",
        ),
        target=TargetInfo(
            ticker=ticker,
            ticker_normalized=ticker.upper(),
        ),
        direction=direction,
        action_chain=[
            ActionStep(sequence=1, action_type=ActionType.WATCH)
        ],
        confidence=confidence,
        validation_status=validation_status,
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestTimelineModels:
    """Test timeline data models."""

    def test_timeline_entry_creation(self) -> None:
        action = _make_action()
        entry = TimelineEntry(
            timestamp=action.timestamp,
            action=action,
            validation_status=action.validation_status,
        )
        assert entry.timestamp == action.timestamp
        assert entry.action.trade_action_id == action.trade_action_id
        assert entry.market_context is None
        assert entry.validation_status == ValidationStatus.PENDING

    def test_timeline_summary_defaults(self) -> None:
        summary = TimelineSummary()
        assert summary.total_actions == 0
        assert summary.bullish_count == 0
        assert summary.bearish_count == 0
        assert summary.tickers_covered == []
        assert summary.date_range is None

    def test_kol_timeline_creation(self) -> None:
        timeline = KOLTimeline(kol_id="kol_001")
        assert timeline.kol_id == "kol_001"
        assert timeline.entries == []
        assert isinstance(timeline.summary, TimelineSummary)

    def test_timeline_filter_defaults(self) -> None:
        f = TimelineFilter()
        assert f.tickers is None
        assert f.directions is None
        assert f.limit == 200

    def test_kol_comparison_creation(self) -> None:
        comp = KOLComparison()
        assert comp.kol_entries == []
        assert comp.shared_tickers == []
        assert comp.direction_overlap == 0.0


# ---------------------------------------------------------------------------
# Engine unit tests (without repository)
# ---------------------------------------------------------------------------

class TestTimelineEngineHelpers:
    """Test TimelineEngine static helper methods."""

    def test_actions_to_entries(self) -> None:
        actions = [
            _make_action(ticker="AAPL", timestamp=datetime(2026, 1, 10)),
            _make_action(ticker="TSLA", timestamp=datetime(2026, 1, 15)),
        ]
        entries = TimelineEngine._actions_to_entries(actions)
        assert len(entries) == 2
        assert entries[0].action.target.ticker == "AAPL"
        assert entries[0].market_context is None  # no enrichment

    def test_compute_summary_empty(self) -> None:
        summary = TimelineEngine._compute_summary([])
        assert summary.total_actions == 0
        assert summary.date_range is None

    def test_compute_summary_with_entries(self) -> None:
        actions = [
            _make_action(
                ticker="AAPL",
                direction=TradeDirection.BULLISH,
                confidence=0.9,
                validation_status=ValidationStatus.VERIFIED,
                timestamp=datetime(2026, 1, 10),
            ),
            _make_action(
                ticker="TSLA",
                direction=TradeDirection.BEARISH,
                confidence=0.6,
                validation_status=ValidationStatus.PENDING,
                timestamp=datetime(2026, 1, 15),
            ),
        ]
        entries = TimelineEngine._actions_to_entries(actions)
        summary = TimelineEngine._compute_summary(entries)

        assert summary.total_actions == 2
        assert summary.bullish_count == 1
        assert summary.bearish_count == 1
        assert summary.verified_count == 1
        assert summary.pending_count == 1
        assert "AAPL" in summary.tickers_covered
        assert "TSLA" in summary.tickers_covered
        assert summary.avg_confidence == pytest.approx(0.75, abs=0.01)
        assert summary.date_range is not None
        assert summary.date_range[0] == datetime(2026, 1, 10)
        assert summary.date_range[1] == datetime(2026, 1, 15)

    def test_apply_filters_by_ticker(self) -> None:
        actions = [
            _make_action(ticker="AAPL"),
            _make_action(ticker="TSLA"),
        ]
        entries = TimelineEngine._actions_to_entries(actions)
        filters = TimelineFilter(tickers=["AAPL"])
        result = TimelineEngine._apply_filters(entries, filters)
        assert len(result) == 1
        assert result[0].action.target.ticker == "AAPL"

    def test_apply_filters_by_direction(self) -> None:
        actions = [
            _make_action(direction=TradeDirection.BULLISH),
            _make_action(direction=TradeDirection.BEARISH),
        ]
        entries = TimelineEngine._actions_to_entries(actions)
        filters = TimelineFilter(directions=[TradeDirection.BULLISH])
        result = TimelineEngine._apply_filters(entries, filters)
        assert len(result) == 1
        assert result[0].action.direction == TradeDirection.BULLISH

    def test_apply_filters_by_date_range(self) -> None:
        actions = [
            _make_action(timestamp=datetime(2026, 1, 10)),
            _make_action(timestamp=datetime(2026, 2, 10)),
        ]
        entries = TimelineEngine._actions_to_entries(actions)
        filters = TimelineFilter(
            date_start=datetime(2026, 1, 15),
            date_end=datetime(2026, 2, 15),
        )
        result = TimelineEngine._apply_filters(entries, filters)
        assert len(result) == 1
        assert result[0].timestamp == datetime(2026, 2, 10)

    def test_apply_filters_by_confidence(self) -> None:
        actions = [
            _make_action(confidence=0.3),
            _make_action(confidence=0.8),
        ]
        entries = TimelineEngine._actions_to_entries(actions)
        filters = TimelineFilter(min_confidence=0.5)
        result = TimelineEngine._apply_filters(entries, filters)
        assert len(result) == 1
        assert result[0].action.confidence == 0.8

    def test_apply_filters_combined(self) -> None:
        actions = [
            _make_action(
                ticker="AAPL",
                direction=TradeDirection.BULLISH,
                confidence=0.9,
                timestamp=datetime(2026, 1, 10),
            ),
            _make_action(
                ticker="TSLA",
                direction=TradeDirection.BEARISH,
                confidence=0.3,
                timestamp=datetime(2026, 2, 10),
            ),
        ]
        entries = TimelineEngine._actions_to_entries(actions)
        filters = TimelineFilter(
            tickers=["AAPL", "TSLA"],
            directions=[TradeDirection.BULLISH],
            min_confidence=0.5,
        )
        result = TimelineEngine._apply_filters(entries, filters)
        assert len(result) == 1
        assert result[0].action.target.ticker == "AAPL"

    def test_resolve_kol_name_from_metadata(self) -> None:
        action = _make_action()
        action.metadata["creator_name"] = "Trader_Ji"
        name = TimelineEngine._resolve_kol_name("kol_001", [action])
        assert name == "Trader_Ji"

    def test_resolve_kol_name_none(self) -> None:
        action = _make_action()
        name = TimelineEngine._resolve_kol_name("kol_001", [action])
        assert name is None

    def test_direction_overlap_identical(self) -> None:
        vectors = [
            {"bullish": 10, "bearish": 5, "neutral": 3},
            {"bullish": 10, "bearish": 5, "neutral": 3},
        ]
        overlap = TimelineEngine._compute_direction_overlap(vectors)
        assert overlap == pytest.approx(1.0, abs=0.01)

    def test_direction_overlap_orthogonal(self) -> None:
        vectors = [
            {"bullish": 10, "bearish": 0, "neutral": 0},
            {"bullish": 0, "bearish": 10, "neutral": 0},
        ]
        overlap = TimelineEngine._compute_direction_overlap(vectors)
        assert overlap == pytest.approx(0.0, abs=0.01)

    def test_direction_overlap_partial(self) -> None:
        vectors = [
            {"bullish": 8, "bearish": 2, "neutral": 0},
            {"bullish": 4, "bearish": 6, "neutral": 0},
        ]
        overlap = TimelineEngine._compute_direction_overlap(vectors)
        assert 0.0 < overlap < 1.0


# ---------------------------------------------------------------------------
# Integration-level tests (with mock repository)
# ---------------------------------------------------------------------------

class FakeRepository:
    """Minimal fake repository for TimelineEngine integration tests."""

    def __init__(self, actions_by_kol: dict[str, list[TradeAction]] | None = None) -> None:
        self._data = actions_by_kol or {}

    def query_by_kol(self, kol_id: str, **kwargs) -> list[TradeAction]:
        return self._data.get(kol_id, [])

    def query_by_kols(self, kol_ids: list[str], **kwargs) -> dict[str, list[TradeAction]]:
        """Batch query for multiple KOLs."""
        return {kol_id: self._data.get(kol_id, []) for kol_id in kol_ids}


class TestTimelineEngineIntegration:
    """Integration tests using a fake repository."""

    def test_build_timeline(self) -> None:
        actions = [
            _make_action(
                ticker="AAPL",
                direction=TradeDirection.BULLISH,
                timestamp=datetime(2026, 1, 10),
            ),
            _make_action(
                ticker="TSLA",
                direction=TradeDirection.BEARISH,
                timestamp=datetime(2026, 1, 15),
            ),
        ]
        repo = FakeRepository({"kol_001": actions})
        engine = TimelineEngine(repo)

        timeline = engine.build_timeline("kol_001")
        assert timeline.kol_id == "kol_001"
        assert len(timeline.entries) == 2
        # Should be reverse chronological
        assert timeline.entries[0].timestamp > timeline.entries[1].timestamp
        assert timeline.summary.total_actions == 2
        assert timeline.summary.bullish_count == 1
        assert timeline.summary.bearish_count == 1

    def test_build_timeline_empty(self) -> None:
        repo = FakeRepository({"kol_999": []})
        engine = TimelineEngine(repo)

        timeline = engine.build_timeline("kol_999")
        assert len(timeline.entries) == 0
        assert timeline.summary.total_actions == 0

    def test_query_timeline_with_filters(self) -> None:
        actions = [
            _make_action(
                ticker="AAPL",
                direction=TradeDirection.BULLISH,
                confidence=0.9,
                timestamp=datetime(2026, 1, 10),
            ),
            _make_action(
                ticker="TSLA",
                direction=TradeDirection.BEARISH,
                confidence=0.3,
                timestamp=datetime(2026, 2, 10),
            ),
        ]
        repo = FakeRepository({"kol_001": actions})
        engine = TimelineEngine(repo)

        filters = TimelineFilter(min_confidence=0.5)
        timeline = engine.query_timeline("kol_001", filters)
        assert len(timeline.entries) == 1
        assert timeline.entries[0].action.target.ticker == "AAPL"

    def test_query_timeline_limit(self) -> None:
        actions = [
            _make_action(ticker=f"T{i}", timestamp=datetime(2026, 1, i + 1))
            for i in range(10)
        ]
        repo = FakeRepository({"kol_001": actions})
        engine = TimelineEngine(repo)

        filters = TimelineFilter(limit=3)
        timeline = engine.query_timeline("kol_001", filters)
        assert len(timeline.entries) == 3

    def test_compare_kols(self) -> None:
        repo = FakeRepository({
            "kol_001": [
                _make_action(
                    ticker="AAPL",
                    direction=TradeDirection.BULLISH,
                    creator_id="kol_001",
                    timestamp=datetime(2026, 1, 10),
                ),
            ],
            "kol_002": [
                _make_action(
                    ticker="AAPL",
                    direction=TradeDirection.BEARISH,
                    creator_id="kol_002",
                    timestamp=datetime(2026, 1, 10),
                ),
            ],
        })
        engine = TimelineEngine(repo)

        comparison = engine.compare_kols(["kol_001", "kol_002"])
        assert len(comparison.kol_entries) == 2
        assert "AAPL" in comparison.shared_tickers
        # Opposite directions, overlap should be < 1.0
        assert comparison.direction_overlap < 1.0

    def test_compare_kols_requires_two(self) -> None:
        repo = FakeRepository()
        engine = TimelineEngine(repo)

        with pytest.raises(ValueError, match="at least 2"):
            engine.compare_kols(["kol_001"])
