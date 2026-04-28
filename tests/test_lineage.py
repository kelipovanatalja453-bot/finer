"""Tests for data lineage and version control.

Tests cover:
    - Lineage creation and tracking
    - Version management and config hashing
    - TradeAction lineage fields
    - API endpoints
"""

import pytest
from datetime import datetime
from pathlib import Path

from finer.schemas.lineage import DataLineage, VersionInfo, PipelineRunInfo
from finer.schemas.trade_action import TradeAction, TradeDirection
from finer.services.versioning import (
    compute_config_hash,
    compute_prompt_hash,
    VersionManager,
    get_version_manager,
)
from finer.services.lineage import (
    LineageTracker,
    get_lineage_tracker,
)


# =============================================================================
# Lineage Schema Tests
# =============================================================================

class TestDataLineage:
    """Tests for DataLineage schema."""

    def test_create_lineage(self):
        """Test creating a lineage record."""
        lineage = DataLineage(
            original_content_id="feishu_doc_123",
            original_source="feishu",
        )

        assert lineage.original_content_id == "feishu_doc_123"
        assert lineage.original_source == "feishu"
        assert lineage.segment_ids == []
        assert lineage.event_ids == []
        assert lineage.created_at is not None

    def test_add_segment(self):
        """Test adding segments to lineage."""
        lineage = DataLineage(original_content_id="test")

        lineage.add_segment("seg_001")
        lineage.add_segment("seg_002")

        assert len(lineage.segment_ids) == 2
        assert "seg_001" in lineage.segment_ids
        assert "seg_002" in lineage.segment_ids

    def test_add_event(self):
        """Test adding events to lineage."""
        lineage = DataLineage(original_content_id="test")

        lineage.add_event("evt_001")

        assert len(lineage.event_ids) == 1
        assert "evt_001" in lineage.event_ids

    def test_no_duplicate_segments(self):
        """Test that duplicate segments are not added."""
        lineage = DataLineage(original_content_id="test")

        lineage.add_segment("seg_001")
        lineage.add_segment("seg_001")  # Duplicate

        assert len(lineage.segment_ids) == 1

    def test_to_summary(self):
        """Test lineage summary generation."""
        lineage = DataLineage(
            original_content_id="feishu_123",
            original_source="feishu",
        )
        lineage.add_segment("seg_001")
        lineage.add_event("evt_001")

        summary = lineage.to_summary()

        assert "feishu_123" in summary
        assert "Segments: 1" in summary
        assert "Events: 1" in summary


class TestVersionInfo:
    """Tests for VersionInfo schema."""

    def test_create_version_info(self):
        """Test creating version info."""
        version = VersionInfo(
            schema_version="1.0",
            extraction_config_hash="abc123",
            model_version="glm-5.1",
            prompt_version="2.0",
        )

        assert version.schema_version == "1.0"
        assert version.extraction_config_hash == "abc123"
        assert version.model_version == "glm-5.1"
        assert version.prompt_version == "2.0"

    def test_to_dict_safe(self):
        """Test serialization."""
        version = VersionInfo(
            schema_version="1.0",
            model_version="glm-5.1",
        )

        data = version.to_dict_safe()

        assert isinstance(data, dict)
        assert data["schema_version"] == "1.0"


class TestPipelineRunInfo:
    """Tests for PipelineRunInfo schema."""

    def test_create_pipeline_run(self):
        """Test creating a pipeline run."""
        run = PipelineRunInfo()

        assert run.run_id is not None
        assert run.status == "running"
        assert run.started_at is not None

    def test_mark_completed(self):
        """Test marking run as completed."""
        run = PipelineRunInfo()
        run.items_processed = 10
        run.mark_completed()

        assert run.status == "completed"
        assert run.completed_at is not None

    def test_mark_failed(self):
        """Test marking run as failed."""
        run = PipelineRunInfo()
        run.mark_failed("Test error")

        assert run.status == "failed"
        assert run.error_message == "Test error"


# =============================================================================
# Version Manager Tests
# =============================================================================

class TestVersionManager:
    """Tests for VersionManager."""

    def test_compute_config_hash(self):
        """Test config hash computation."""
        hash1 = compute_config_hash(
            prompt_template="Extract trades",
            model_name="glm-5.1",
            temperature=0.3,
        )

        assert hash1 is not None
        assert len(hash1) == 16  # 16 char hex

    def test_different_configs_different_hashes(self):
        """Test that different configs produce different hashes."""
        hash1 = compute_config_hash(
            prompt_template="Extract trades",
            model_name="glm-5.1",
            temperature=0.3,
        )
        hash2 = compute_config_hash(
            prompt_template="Extract trades",
            model_name="glm-5.1",
            temperature=0.5,  # Different temperature
        )

        assert hash1 != hash2

    def test_compute_prompt_hash(self):
        """Test prompt hash computation."""
        hash1 = compute_prompt_hash("Extract trades from text")

        assert hash1 is not None
        assert len(hash1) == 16

    def test_create_version_info(self):
        """Test creating version info from manager."""
        manager = VersionManager()
        version = manager.create_version_info(
            model_name="glm-5.1",
            prompt_template="Extract trades",
            temperature=0.3,
        )

        assert version is not None
        assert version.model_version == "glm-5.1"
        assert version.temperature == 0.3
        assert version.extraction_config_hash is not None

    def test_should_reprocess_prompt_change(self):
        """Test reprocessing detection on prompt change."""
        manager = VersionManager(prompt_version="2.0")

        old_version = VersionInfo(
            prompt_version="1.0",
            schema_version="1.0",
        )

        should_reprocess = manager.should_reprocess(old_version)

        assert should_reprocess is True

    def test_should_not_reprocess_same_version(self):
        """Test no reprocessing needed for same version."""
        manager = VersionManager(prompt_version="2.0")

        version = VersionInfo(
            prompt_version="2.0",
            schema_version="1.0",
        )

        should_reprocess = manager.should_reprocess(version)

        assert should_reprocess is False


# =============================================================================
# Lineage Tracker Tests
# =============================================================================

class TestLineageTracker:
    """Tests for LineageTracker."""

    def test_create_lineage(self):
        """Test creating a lineage in tracker."""
        tracker = LineageTracker()
        lineage = tracker.create_lineage("content_123")

        assert lineage is not None
        assert lineage.original_content_id == "content_123"

    def test_register_action(self):
        """Test registering an action with lineage."""
        tracker = LineageTracker()
        lineage = tracker.create_lineage("content_123")
        tracker.register_action("action_456", lineage)

        traced = tracker.trace_back("action_456")

        assert traced is not None
        assert traced.original_content_id == "content_123"

    def test_get_original_content(self):
        """Test getting original content ID."""
        tracker = LineageTracker()
        lineage = tracker.create_lineage("content_123")
        tracker.register_action("action_456", lineage)

        content_id = tracker.get_original_content("action_456")

        assert content_id == "content_123"

    def test_add_segment_and_event(self):
        """Test adding segments and events."""
        tracker = LineageTracker()
        lineage = tracker.create_lineage("content_123")

        tracker.add_segment(lineage, "seg_001")
        tracker.add_event(lineage, "evt_001")

        # Lookup by segment
        by_segment = tracker.get_lineage_by_segment("seg_001")
        assert by_segment is not None

        # Lookup by event
        by_event = tracker.get_lineage_by_event("evt_001")
        assert by_event is not None

    def test_pipeline_run_lifecycle(self):
        """Test pipeline run tracking."""
        tracker = LineageTracker()

        run = tracker.create_pipeline_run(config_snapshot={"model": "glm-5.1"})
        assert run.status == "running"

        tracker.complete_pipeline_run(run.run_id, items_processed=10)
        assert run.status == "completed"
        assert run.items_processed == 10

    def test_get_statistics(self):
        """Test getting tracking statistics."""
        tracker = LineageTracker()

        lineage = tracker.create_lineage("content_123")
        tracker.register_action("action_456", lineage)

        stats = tracker.get_statistics()

        assert stats["total_actions_tracked"] == 1
        assert stats["total_contents"] == 1


# =============================================================================
# TradeAction Lineage Integration Tests
# =============================================================================

class TestTradeActionLineage:
    """Tests for TradeAction lineage fields."""

    def test_trade_action_with_lineage(self):
        """Test creating TradeAction with lineage."""
        from finer.schemas.trade_action import SourceInfo, TargetInfo

        lineage = DataLineage(
            original_content_id="feishu_123",
            original_source="feishu",
        )
        lineage.add_segment("seg_001")

        action = TradeAction(
            source=SourceInfo(
                content_id="feishu_123",
                evidence_text="Test evidence",
            ),
            target=TargetInfo(ticker="AAPL"),
            direction=TradeDirection.BULLISH,
            lineage=lineage,
        )

        assert action.lineage is not None
        assert action.get_source_content_id() == "feishu_123"

    def test_trade_action_with_version_info(self):
        """Test creating TradeAction with version info."""
        from finer.schemas.trade_action import SourceInfo, TargetInfo

        version = VersionInfo(
            schema_version="1.0",
            extraction_config_hash="abc123",
            model_version="glm-5.1",
        )

        action = TradeAction(
            source=SourceInfo(
                content_id="test",
                evidence_text="Test",
            ),
            target=TargetInfo(ticker="AAPL"),
            direction=TradeDirection.BULLISH,
            version_info=version,
        )

        assert action.version_info is not None
        assert action.get_extraction_config_hash() == "abc123"

    def test_backward_compatibility(self):
        """Test that actions without lineage/version work."""
        from finer.schemas.trade_action import SourceInfo, TargetInfo

        action = TradeAction(
            source=SourceInfo(
                content_id="test",
                evidence_text="Test",
            ),
            target=TargetInfo(ticker="AAPL"),
            direction=TradeDirection.BULLISH,
        )

        # Should work without errors
        assert action.lineage is None
        assert action.version_info is None
        assert action.get_source_content_id() is None
        assert action.get_extraction_config_hash() is None


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for full workflow."""

    def test_full_lineage_workflow(self):
        """Test complete workflow from creation to tracing."""
        tracker = LineageTracker()
        manager = VersionManager()

        # Create lineage
        lineage = tracker.create_lineage(
            content_id="feishu_doc_abc",
            source="feishu",
        )

        # Add processing steps
        tracker.add_segment(lineage, "seg_001")
        tracker.add_event(lineage, "evt_001")

        # Create version
        version = manager.create_version_info(
            model_name="glm-5.1",
            prompt_template="Extract trades from text",
            temperature=0.3,
        )

        # Register action
        tracker.register_action("action_789", lineage)

        # Trace back
        traced = tracker.trace_back("action_789")
        assert traced is not None
        assert traced.original_content_id == "feishu_doc_abc"
        assert len(traced.segment_ids) == 1
        assert len(traced.event_ids) == 1

    def test_config_hash_determinism(self):
        """Test that same config produces same hash."""
        hash1 = compute_config_hash(
            prompt_template="Extract trades",
            model_name="glm-5.1",
            temperature=0.3,
        )
        hash2 = compute_config_hash(
            prompt_template="Extract trades",
            model_name="glm-5.1",
            temperature=0.3,
        )

        assert hash1 == hash2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
