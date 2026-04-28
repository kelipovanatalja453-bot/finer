"""Lineage API Routes.

Provides endpoints for querying data lineage across the Finer pipeline.

Endpoints:
    - GET /api/lineage/{trade_action_id} — Get lineage for a TradeAction
    - GET /api/lineage/{trade_action_id}/trace — Trace to original source
    - GET /api/lineage/stats — Get lineage tracking statistics
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

from finer.services.lineage import get_lineage_tracker


router = APIRouter(tags=["lineage"])


# =============================================================================
# Response Models
# =============================================================================

class LineageResponse(BaseModel):
    """Response model for lineage query."""
    ok: bool = True
    data: Optional[Dict] = None
    error: Optional[Dict] = None


class LineageSummary(BaseModel):
    """Summary of a lineage chain."""
    original_content_id: str
    original_source: Optional[str] = None
    segment_count: int = 0
    event_count: int = 0
    enrichment_count: int = 0
    pipeline_run_id: Optional[str] = None
    created_at: Optional[str] = None
    summary: str


class LineageStatsResponse(BaseModel):
    """Lineage tracking statistics."""
    total_actions_tracked: int
    total_contents: int
    total_segments: int
    total_events: int
    active_pipeline_runs: int
    completed_pipeline_runs: int


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/{trade_action_id}", response_model=LineageResponse)
async def get_lineage(trade_action_id: str):
    """Get data lineage for a TradeAction.

    Args:
        trade_action_id: TradeAction ID

    Returns:
        Lineage chain from original content to this action
    """
    tracker = get_lineage_tracker()
    lineage = tracker.trace_back(trade_action_id)

    if not lineage:
        return LineageResponse(
            ok=False,
            error={
                "code": "NOT_FOUND",
                "message": f"No lineage found for trade_action_id: {trade_action_id}"
            }
        )

    return LineageResponse(
        ok=True,
        data={
            "trade_action_id": trade_action_id,
            "lineage": lineage.model_dump(mode='json'),
            "summary": lineage.to_summary(),
        }
    )


@router.get("/{trade_action_id}/trace", response_model=LineageResponse)
async def trace_to_source(trade_action_id: str):
    """Trace a TradeAction back to its original source.

    Args:
        trade_action_id: TradeAction ID

    Returns:
        Original content ID and source information
    """
    tracker = get_lineage_tracker()
    original_content_id = tracker.get_original_content(trade_action_id)

    if not original_content_id:
        return LineageResponse(
            ok=False,
            error={
                "code": "NOT_FOUND",
                "message": f"Cannot trace trade_action_id: {trade_action_id}"
            }
        )

    lineage = tracker.trace_back(trade_action_id)

    return LineageResponse(
        ok=True,
        data={
            "trade_action_id": trade_action_id,
            "original_content_id": original_content_id,
            "original_source": lineage.original_source if lineage else None,
            "segment_ids": lineage.segment_ids if lineage else [],
            "event_ids": lineage.event_ids if lineage else [],
        }
    )


@router.get("/content/{content_id}/actions", response_model=LineageResponse)
async def get_actions_for_content(content_id: str):
    """Get all TradeActions derived from a content.

    Args:
        content_id: Original content ID

    Returns:
        List of TradeAction IDs
    """
    tracker = get_lineage_tracker()
    action_ids = tracker.get_actions_for_content(content_id)

    return LineageResponse(
        ok=True,
        data={
            "content_id": content_id,
            "action_count": len(action_ids),
            "action_ids": action_ids,
        }
    )


@router.get("/stats", response_model=LineageStatsResponse)
async def get_lineage_stats():
    """Get lineage tracking statistics.

    Returns:
        Statistics about tracked lineages
    """
    tracker = get_lineage_tracker()
    stats = tracker.get_statistics()

    return LineageStatsResponse(**stats)


@router.get("/segment/{segment_id}", response_model=LineageResponse)
async def get_lineage_by_segment(segment_id: str):
    """Get lineage by segment ID.

    Args:
        segment_id: Segment ID

    Returns:
        Lineage information
    """
    tracker = get_lineage_tracker()
    lineage = tracker.get_lineage_by_segment(segment_id)

    if not lineage:
        return LineageResponse(
            ok=False,
            error={
                "code": "NOT_FOUND",
                "message": f"No lineage found for segment_id: {segment_id}"
            }
        )

    return LineageResponse(
        ok=True,
        data={
            "segment_id": segment_id,
            "lineage": lineage.model_dump(mode='json'),
        }
    )


@router.get("/event/{event_id}", response_model=LineageResponse)
async def get_lineage_by_event(event_id: str):
    """Get lineage by event ID.

    Args:
        event_id: Event ID

    Returns:
        Lineage information
    """
    tracker = get_lineage_tracker()
    lineage = tracker.get_lineage_by_event(event_id)

    if not lineage:
        return LineageResponse(
            ok=False,
            error={
                "code": "NOT_FOUND",
                "message": f"No lineage found for event_id: {event_id}"
            }
        )

    return LineageResponse(
        ok=True,
        data={
            "event_id": event_id,
            "lineage": lineage.model_dump(mode='json'),
        }
    )
