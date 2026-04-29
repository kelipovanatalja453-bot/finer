"""Lineage Tracking Service.

Tracks data lineage across the 8-layer Finer pipeline.

Lineage Chain:
    BacktestResult → TradeAction → EventWithActions → SegmentRecord → ContentRecord → Feishu message

Key Features:
    - Create and maintain lineage chains
    - Trace back from any TradeAction to original source
    - Support for multi-hop enrichment lineage
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import uuid4

from finer.schemas.lineage import DataLineage, PipelineRunInfo


logger = logging.getLogger(__name__)


# =============================================================================
# Lineage Tracker
# =============================================================================

class LineageTracker:
    """Tracks data lineage across pipeline layers.

    Maintains in-memory index for fast lookups, with optional persistence.

    Example:
        tracker = LineageTracker()

        # Create lineage for new content
        lineage = tracker.create_lineage("feishu_doc_123")

        # Add segments and events
        tracker.add_segment(lineage, "seg_001")
        tracker.add_event(lineage, "evt_001")

        # Attach to TradeAction
        action.lineage = lineage
    """

    def __init__(self, persist_dir: Optional[Path] = None):
        """Initialize lineage tracker.

        Args:
            persist_dir: Optional directory for persisting lineage data
        """
        self.persist_dir = persist_dir

        # In-memory indexes
        # trade_action_id -> lineage
        self._lineage_by_action: Dict[str, DataLineage] = {}
        # content_id -> list of lineage (one content can produce multiple actions)
        self._lineage_by_content: Dict[str, List[DataLineage]] = {}
        # segment_id -> lineage
        self._lineage_by_segment: Dict[str, DataLineage] = {}
        # event_id -> lineage
        self._lineage_by_event: Dict[str, DataLineage] = {}

        # Active pipeline runs
        self._pipeline_runs: Dict[str, PipelineRunInfo] = {}

    def create_lineage(
        self,
        content_id: str,
        source: Optional[str] = None,
        pipeline_run_id: Optional[str] = None,
    ) -> DataLineage:
        """Create a new lineage record.

        Args:
            content_id: F0 original content ID
            source: Source system (feishu, bilibili, wechat)
            pipeline_run_id: Optional pipeline run ID for grouping

        Returns:
            New DataLineage instance
        """
        lineage = DataLineage(
            original_content_id=content_id,
            original_source=source,
            pipeline_run_id=pipeline_run_id,
        )

        # Index by content
        if content_id not in self._lineage_by_content:
            self._lineage_by_content[content_id] = []
        self._lineage_by_content[content_id].append(lineage)

        logger.debug(f"Created lineage for content: {content_id}")
        return lineage

    def add_segment(self, lineage: DataLineage, segment_id: str) -> None:
        """Add a segment to the lineage chain.

        Args:
            lineage: DataLineage to update
            segment_id: Segment ID to add
        """
        lineage.add_segment(segment_id)
        self._lineage_by_segment[segment_id] = lineage
        logger.debug(f"Added segment {segment_id} to lineage")

    def add_event(self, lineage: DataLineage, event_id: str) -> None:
        """Add an event to the lineage chain.

        Args:
            lineage: DataLineage to update
            event_id: Event ID to add
        """
        lineage.add_event(event_id)
        self._lineage_by_event[event_id] = lineage
        logger.debug(f"Added event {event_id} to lineage")

    def add_enrichment_content(self, lineage: DataLineage, content_id: str) -> None:
        """Add enrichment content to the lineage chain.

        Args:
            lineage: DataLineage to update
            content_id: Enrichment content ID
        """
        lineage.add_enrichment_content(content_id)
        logger.debug(f"Added enrichment content {content_id} to lineage")

    def register_action(
        self,
        action_id: str,
        lineage: DataLineage,
    ) -> None:
        """Register a TradeAction with its lineage.

        Args:
            action_id: TradeAction ID
            lineage: Associated DataLineage
        """
        self._lineage_by_action[action_id] = lineage
        logger.debug(f"Registered lineage for action: {action_id}")

    def trace_back(self, trade_action_id: str) -> Optional[DataLineage]:
        """Trace back from TradeAction to original source.

        Args:
            trade_action_id: TradeAction ID to trace

        Returns:
            DataLineage if found, None otherwise
        """
        return self._lineage_by_action.get(trade_action_id)

    def get_original_content(self, trade_action_id: str) -> Optional[str]:
        """Get the original content ID for a TradeAction.

        Args:
            trade_action_id: TradeAction ID

        Returns:
            Original content ID if found, None otherwise
        """
        lineage = self.trace_back(trade_action_id)
        if lineage:
            return lineage.original_content_id
        return None

    def get_lineage_by_segment(self, segment_id: str) -> Optional[DataLineage]:
        """Get lineage by segment ID.

        Args:
            segment_id: Segment ID

        Returns:
            DataLineage if found, None otherwise
        """
        return self._lineage_by_segment.get(segment_id)

    def get_lineage_by_event(self, event_id: str) -> Optional[DataLineage]:
        """Get lineage by event ID.

        Args:
            event_id: Event ID

        Returns:
            DataLineage if found, None otherwise
        """
        return self._lineage_by_event.get(event_id)

    def get_actions_for_content(self, content_id: str) -> List[str]:
        """Get all TradeAction IDs derived from a content.

        Args:
            content_id: Original content ID

        Returns:
            List of TradeAction IDs
        """
        lineages = self._lineage_by_content.get(content_id, [])
        action_ids = []
        for action_id, lineage in self._lineage_by_action.items():
            if lineage.original_content_id == content_id:
                action_ids.append(action_id)
        return action_ids

    def create_pipeline_run(
        self,
        config_snapshot: Optional[Dict[str, Any]] = None,
    ) -> PipelineRunInfo:
        """Create a new pipeline run.

        Args:
            config_snapshot: Snapshot of configuration

        Returns:
            New PipelineRunInfo instance
        """
        run = PipelineRunInfo(
            config_snapshot=config_snapshot or {},
        )
        self._pipeline_runs[run.run_id] = run
        logger.info(f"Created pipeline run: {run.run_id}")
        return run

    def get_pipeline_run(self, run_id: str) -> Optional[PipelineRunInfo]:
        """Get a pipeline run by ID.

        Args:
            run_id: Run ID

        Returns:
            PipelineRunInfo if found, None otherwise
        """
        return self._pipeline_runs.get(run_id)

    def complete_pipeline_run(self, run_id: str, items_processed: int, items_failed: int = 0) -> None:
        """Mark a pipeline run as completed.

        Args:
            run_id: Run ID
            items_processed: Number of items processed
            items_failed: Number of items that failed
        """
        run = self._pipeline_runs.get(run_id)
        if run:
            run.items_processed = items_processed
            run.items_failed = items_failed
            run.mark_completed()
            logger.info(f"Completed pipeline run {run_id}: {items_processed} processed, {items_failed} failed")

    def fail_pipeline_run(self, run_id: str, error: str) -> None:
        """Mark a pipeline run as failed.

        Args:
            run_id: Run ID
            error: Error message
        """
        run = self._pipeline_runs.get(run_id)
        if run:
            run.mark_failed(error)
            logger.error(f"Failed pipeline run {run_id}: {error}")

    def get_statistics(self) -> Dict[str, int]:
        """Get lineage tracking statistics.

        Returns:
            Dictionary with counts
        """
        return {
            "total_actions_tracked": len(self._lineage_by_action),
            "total_contents": len(self._lineage_by_content),
            "total_segments": len(self._lineage_by_segment),
            "total_events": len(self._lineage_by_event),
            "active_pipeline_runs": sum(1 for r in self._pipeline_runs.values() if r.status == "running"),
            "completed_pipeline_runs": sum(1 for r in self._pipeline_runs.values() if r.status == "completed"),
        }


# =============================================================================
# Global Instance
# =============================================================================

from functools import lru_cache

@lru_cache(maxsize=1)
def get_lineage_tracker() -> LineageTracker:
    """Get the default lineage tracker instance (thread-safe singleton)."""
    return LineageTracker()


def set_lineage_tracker(tracker: LineageTracker) -> None:
    """Set the default lineage tracker instance (clears cache)."""
    get_lineage_tracker.cache_clear()
    # Store in module variable for external access if needed
    global _default_tracker
    _default_tracker = tracker


_default_tracker: Optional[LineageTracker] = None


# =============================================================================
# Convenience Functions
# =============================================================================

def create_lineage_for_content(
    content_id: str,
    source: Optional[str] = None,
    pipeline_run_id: Optional[str] = None,
) -> DataLineage:
    """Convenience function to create a lineage.

    Args:
        content_id: Original content ID
        source: Source system
        pipeline_run_id: Pipeline run ID

    Returns:
        DataLineage instance
    """
    tracker = get_lineage_tracker()
    return tracker.create_lineage(
        content_id=content_id,
        source=source,
        pipeline_run_id=pipeline_run_id,
    )


def trace_trade_action_source(action_id: str) -> Optional[str]:
    """Convenience function to trace action to source.

    Args:
        action_id: TradeAction ID

    Returns:
        Original content ID if found
    """
    tracker = get_lineage_tracker()
    return tracker.get_original_content(action_id)