"""Data Lineage and Version Control Schemas.

This module defines schemas for tracking data lineage across the 8-layer Finer pipeline
and version control for reproducibility.

Lineage Chain:
    BacktestResult → TradeAction → EventWithActions → SegmentRecord → ContentRecord → Feishu message

Key Features:
    - Full traceability from backtest to source
    - Version tracking for prompts, models, and configs
    - Reproducibility through config hashing
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Data Lineage Schema
# =============================================================================

class DataLineage(BaseModel):
    """Data lineage tracking across pipeline layers.

    Tracks the complete path from original content (L0) to final output,
    enabling:
        - Traceability: Find source for any TradeAction
        - Debugging: Identify which content produced which actions
        - Re-processing: Re-run specific content through pipeline

    Example:
        lineage = DataLineage(
            original_content_id="feishu_doc_abc123",
            segment_ids=["seg_001", "seg_002"],
            event_ids=["evt_001"],
        )
    """
    model_config = ConfigDict(strict=True)

    # L0: Original content
    original_content_id: str = Field(
        ...,
        description="L0 original content ID (Feishu doc/message ID)"
    )
    original_source: Optional[str] = Field(
        None,
        description="Source system (feishu, bilibili, wechat)"
    )

    # L1: Enrichment
    enrichment_content_ids: List[str] = Field(
        default_factory=list,
        description="L1 enrichment related content IDs"
    )

    # L3: Segments
    segment_ids: List[str] = Field(
        default_factory=list,
        description="L3 parsed segment IDs"
    )

    # L5: Events
    event_ids: List[str] = Field(
        default_factory=list,
        description="L5 event IDs"
    )
    extraction_id: Optional[str] = Field(
        None,
        description="L5 extraction batch ID"
    )

    # Pipeline metadata
    pipeline_run_id: Optional[str] = Field(
        None,
        description="Pipeline run ID for grouping related extractions"
    )

    # Timestamp
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When lineage was created"
    )

    def add_segment(self, segment_id: str) -> None:
        """Add a segment to the lineage chain."""
        if segment_id not in self.segment_ids:
            self.segment_ids.append(segment_id)

    def add_event(self, event_id: str) -> None:
        """Add an event to the lineage chain."""
        if event_id not in self.event_ids:
            self.event_ids.append(event_id)

    def add_enrichment_content(self, content_id: str) -> None:
        """Add enrichment content to the lineage chain."""
        if content_id not in self.enrichment_content_ids:
            self.enrichment_content_ids.append(content_id)

    def to_summary(self) -> str:
        """Get a human-readable summary of the lineage."""
        parts = [f"Source: {self.original_content_id}"]
        if self.enrichment_content_ids:
            parts.append(f"Enrichment: {len(self.enrichment_content_ids)} items")
        if self.segment_ids:
            parts.append(f"Segments: {len(self.segment_ids)}")
        if self.event_ids:
            parts.append(f"Events: {len(self.event_ids)}")
        return " → ".join(parts)


# =============================================================================
# Version Control Schema
# =============================================================================

class VersionInfo(BaseModel):
    """Version control information for reproducibility.

    Tracks:
        - Schema version: Data structure version
        - Config hash: Hash of prompt + model + temperature
        - Model version: Specific model used
        - Prompt version: Prompt template version

    This enables:
        - Detecting when re-processing is needed (prompt changed)
        - Reproducing results (same config → same output)
        - Debugging (which model produced this output)

    Example:
        version = VersionInfo(
            schema_version="1.0",
            extraction_config_hash="a3f2c1d8",
            model_version="glm-5.1-2024q1",
            prompt_version="2.0",
        )
    """
    model_config = ConfigDict(strict=True)

    # Schema version
    schema_version: str = Field(
        "1.0",
        description="Schema version for backward compatibility"
    )

    # Configuration hash
    extraction_config_hash: Optional[str] = Field(
        None,
        description="Hash of (prompt + model + temperature + other params)"
    )

    # Model metadata
    model_version: Optional[str] = Field(
        None,
        description="Model version identifier (e.g., glm-5.1-2024q1)"
    )
    model_provider: Optional[str] = Field(
        None,
        description="Model provider (zhipu, dashscope, openai)"
    )

    # Prompt metadata
    prompt_version: Optional[str] = Field(
        None,
        description="Prompt template version"
    )
    prompt_hash: Optional[str] = Field(
        None,
        description="Hash of the prompt template"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this version info was created"
    )
    modified_at: Optional[datetime] = Field(
        None,
        description="Last modification time"
    )
    modified_by: Optional[str] = Field(
        None,
        description="Who modified (user ID or 'auto')"
    )

    # Additional config
    temperature: Optional[float] = Field(
        None,
        description="Temperature used for extraction"
    )
    additional_params: dict = Field(
        default_factory=dict,
        description="Additional extraction parameters"
    )

    def to_dict_safe(self) -> dict:
        """Export version info as dict (for JSON serialization)."""
        return self.model_dump(mode='json')


# =============================================================================
# Pipeline Run Info
# =============================================================================

class PipelineRunInfo(BaseModel):
    """Information about a pipeline run.

    Groups related extractions together for tracking and debugging.
    """
    model_config = ConfigDict(strict=True)

    run_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique run ID"
    )

    started_at: datetime = Field(
        default_factory=datetime.now,
        description="When run started"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="When run completed"
    )

    # Configuration
    config_snapshot: dict = Field(
        default_factory=dict,
        description="Snapshot of configuration at run time"
    )

    # Statistics
    items_processed: int = Field(
        0,
        description="Number of items processed"
    )
    items_failed: int = Field(
        0,
        description="Number of items that failed"
    )

    # Status
    status: str = Field(
        "running",
        description="Run status (running, completed, failed)"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if failed"
    )

    def mark_completed(self) -> None:
        """Mark run as completed."""
        self.completed_at = datetime.now()
        self.status = "completed"

    def mark_failed(self, error: str) -> None:
        """Mark run as failed."""
        self.completed_at = datetime.now()
        self.status = "failed"
        self.error_message = error
