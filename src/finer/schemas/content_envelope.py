"""Content Envelope Schema — V0/V0.5 unified content standardization layer.

This module defines the canonical data structure for content normalization
across all data sources (image, chat, feishu_doc, pdf, audio/video transcripts).

Key Design Principles:
1. ContentEnvelope is the top-level container for all content types
2. ContentBlock represents granular content units (paragraphs, tables, etc.)
3. Quality scoring is embedded at both envelope and block levels
4. Temporal and entity anchors provide structured extraction hooks
5. Evidence spans enable traceability from extraction to source

Schema Version: v0.5
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finer.schemas.quality import QualityCard
from finer.schemas.temporal import TemporalAnchor
from finer.schemas.entity_anchor import EntityAnchor
from finer.schemas.evidence import EvidenceSpan


# =============================================================================
# Content Block Types
# =============================================================================

BLOCK_TYPE_LITERAL = Literal[
    "paragraph",
    "heading",
    "table",
    "chart",
    "image_region",
    "chat_message",
    "transcript_segment",
    "list",
    "unknown",
    # Placeholder types for image strategy
    "table_region",
    "chart_region",
    "ocr_unreadable",
]

SOURCE_TYPE_LITERAL = Literal[
    "image",
    "chat",
    "feishu_doc",
    "pdf",
    "audio_transcript",
    "video_transcript",
    "text",
]


# =============================================================================
# Content Block Model
# =============================================================================

class ContentBlock(BaseModel):
    """Granular content unit within a ContentEnvelope.

    ContentBlock represents a semantically meaningful unit of content,
    such as a paragraph, table, or chat message. Each block has its own
    quality assessment and evidence traces.

    Attributes:
        block_id: Unique identifier for this block.
        block_type: Type of content (paragraph, table, etc.).
        text: Textual content of the block (empty for images/charts).
        order: Position in the content sequence (0-indexed).
        parent_block_id: Parent block for nested structures (tables, lists).
        page_index: Page number for paginated sources (PDFs).
        bbox: Bounding box coordinates [x0, y0, x1, y1] for spatial content.
        speaker: Speaker identifier for chat/transcript content.
        start_time_sec: Start time for audio/video transcripts.
        end_time_sec: End time for audio/video transcripts.
        quality_card: Quality assessment for this block.
        evidence_spans: Traceable text spans within this block.
        metadata: Additional extensible metadata.
    """
    model_config = ConfigDict(strict=True)

    # =========================================================================
    # Core Fields (Required)
    # =========================================================================

    block_id: str = Field(
        default_factory=lambda: f"block_{uuid4().hex[:12]}",
        description="Unique identifier for this content block"
    )

    block_type: BLOCK_TYPE_LITERAL = Field(
        ...,
        description="Type of content (paragraph, table, chart, etc.)"
    )

    text: str = Field(
        ...,
        description="Textual content of the block"
    )

    order: int = Field(
        ...,
        ge=0,
        description="Position in the content sequence (0-indexed)"
    )

    # =========================================================================
    # Optional Structural Fields
    # =========================================================================

    parent_block_id: Optional[str] = Field(
        None,
        description="Parent block ID for nested structures (tables, lists)"
    )

    page_index: Optional[int] = Field(
        None,
        ge=0,
        description="Page number for paginated sources (PDFs)"
    )

    bbox: Optional[List[float]] = Field(
        None,
        min_length=4,
        max_length=4,
        description="Bounding box [x0, y0, x1, y1] for spatial content"
    )

    # =========================================================================
    # Temporal/Speaker Fields (for transcripts and chat)
    # =========================================================================

    speaker: Optional[str] = Field(
        None,
        description="Speaker identifier for chat/transcript content"
    )

    start_time_sec: Optional[float] = Field(
        None,
        ge=0,
        description="Start time in seconds for audio/video transcripts"
    )

    end_time_sec: Optional[float] = Field(
        None,
        ge=0,
        description="End time in seconds for audio/video transcripts"
    )

    # =========================================================================
    # Quality and Evidence Fields
    # =========================================================================

    quality_card: QualityCard = Field(
        ...,
        description="Quality assessment for this block"
    )

    evidence_spans: List[EvidenceSpan] = Field(
        default_factory=list,
        description="Traceable text spans within this block"
    )

    # =========================================================================
    # Metadata
    # =========================================================================

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional extensible metadata"
    )

    # =========================================================================
    # Validators
    # =========================================================================

    @model_validator(mode='after')
    def validate_time_range(self) -> ContentBlock:
        """Ensure time range is valid for transcript blocks."""
        if self.start_time_sec is not None and self.end_time_sec is not None:
            if self.start_time_sec > self.end_time_sec:
                raise ValueError(
                    f"start_time_sec ({self.start_time_sec}) cannot exceed "
                    f"end_time_sec ({self.end_time_sec})"
                )
        return self


# =============================================================================
# Content Envelope Model
# =============================================================================

class ContentEnvelope(BaseModel):
    """Top-level container for standardized content.

    ContentEnvelope is the unified data structure for all content types
    in the Finer pipeline. It normalizes diverse sources (images, PDFs,
    chat logs, transcripts) into a consistent, queryable format.

    Attributes:
        envelope_id: Unique identifier for this envelope.
        schema_version: Schema version for compatibility tracking.
        source_type: Type of source content (image, chat, etc.).
        source_uri: URI to original source content.
        source_title: Title or filename of source content.
        creator_id: Unique identifier of content creator.
        creator_name: Display name of content creator.
        published_at: Original publication timestamp.
        ingested_at: Timestamp when content was ingested.
        blocks: Ordered list of content blocks.
        quality_card: Overall quality assessment.
        temporal_anchors: Extracted time references.
        entity_anchors: Extracted entity references.
        metadata: Additional extensible metadata.

    Example:
        >>> envelope = ContentEnvelope(
        ...     envelope_id="env_abc123",
        ...     schema_version="v0.5",
        ...     source_type="feishu_doc",
        ...     source_uri="feishu://docs/abc123",
        ...     source_title="市场分析报告",
        ...     creator_id="user_456",
        ...     creator_name="分析师A",
        ...     published_at=datetime(2024, 1, 15, 10, 30),
        ...     ingested_at=datetime.now(),
        ...     blocks=[...],
        ...     quality_card=QualityCard(...),
        ...     temporal_anchors=[...],
        ...     entity_anchors=[...],
        ... )
    """
    model_config = ConfigDict(
        strict=True,
        json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )

    # =========================================================================
    # Core Fields (Required)
    # =========================================================================

    envelope_id: str = Field(
        default_factory=lambda: f"env_{uuid4().hex[:12]}",
        description="Unique identifier for this content envelope"
    )

    schema_version: str = Field(
        default="v0.5",
        description="Schema version for compatibility tracking"
    )

    source_type: SOURCE_TYPE_LITERAL = Field(
        ...,
        description="Type of source content (image, chat, feishu_doc, etc.)"
    )

    source_uri: Optional[str] = Field(
        None,
        description="URI to original source content"
    )

    source_title: Optional[str] = Field(
        None,
        description="Title or filename of source content"
    )

    # =========================================================================
    # Creator Fields
    # =========================================================================

    creator_id: Optional[str] = Field(
        None,
        description="Unique identifier of content creator"
    )

    creator_name: Optional[str] = Field(
        None,
        description="Display name of content creator"
    )

    # =========================================================================
    # Temporal Fields
    # =========================================================================

    published_at: Optional[datetime] = Field(
        None,
        description="Original publication timestamp"
    )

    ingested_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when content was ingested"
    )

    # =========================================================================
    # Content Blocks
    # =========================================================================

    blocks: List[ContentBlock] = Field(
        default_factory=list,
        description="Ordered list of content blocks"
    )

    # =========================================================================
    # Quality and Extraction Hooks
    # =========================================================================

    quality_card: QualityCard = Field(
        ...,
        description="Overall quality assessment for this envelope"
    )

    temporal_anchors: List[TemporalAnchor] = Field(
        default_factory=list,
        description="Extracted time references"
    )

    entity_anchors: List[EntityAnchor] = Field(
        default_factory=list,
        description="Extracted entity references"
    )

    # =========================================================================
    # Metadata
    # =========================================================================

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional extensible metadata"
    )

    # =========================================================================
    # Validators
    # =========================================================================

    @model_validator(mode='after')
    def validate_block_order(self) -> ContentEnvelope:
        """Ensure block orders are sequential starting from 0."""
        if not self.blocks:
            return self

        orders = [block.order for block in self.blocks]
        expected = list(range(len(self.blocks)))

        if sorted(orders) != expected:
            raise ValueError(
                f"Block orders must be sequential from 0, got: {orders}"
            )
        return self

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary with ISO 8601 timestamps.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContentEnvelope:
        """
        Create ContentEnvelope from dictionary.

        Args:
            data: Dictionary with envelope data.

        Returns:
            ContentEnvelope instance.
        """
        # Handle datetime string conversion
        if isinstance(data.get("published_at"), str):
            data["published_at"] = datetime.fromisoformat(data["published_at"].replace("Z", "+00:00"))
        if isinstance(data.get("ingested_at"), str):
            data["ingested_at"] = datetime.fromisoformat(data["ingested_at"].replace("Z", "+00:00"))

        # Handle blocks datetime conversion
        for block in data.get("blocks", []):
            if isinstance(block.get("quality_card"), dict):
                # quality_card doesn't have datetime fields
                pass

        # Handle temporal_anchors datetime conversion
        for anchor in data.get("temporal_anchors", []):
            if isinstance(anchor.get("resolved_time"), str):
                anchor["resolved_time"] = datetime.fromisoformat(anchor["resolved_time"].replace("Z", "+00:00"))

        return cls.model_validate(data)

    def get_block_by_id(self, block_id: str) -> Optional[ContentBlock]:
        """
        Retrieve a block by its ID.

        Args:
            block_id: Block identifier to search for.

        Returns:
            ContentBlock if found, None otherwise.
        """
        for block in self.blocks:
            if block.block_id == block_id:
                return block
        return None

    def get_blocks_by_type(self, block_type: BLOCK_TYPE_LITERAL) -> List[ContentBlock]:
        """
        Filter blocks by type.

        Args:
            block_type: Block type to filter by.

        Returns:
            List of matching blocks.
        """
        return [b for b in self.blocks if b.block_type == block_type]

    def get_text_content(self) -> str:
        """
        Get concatenated text from all blocks.

        Returns:
            Combined text content, blocks separated by newlines.
        """
        return "\n\n".join(block.text for block in self.blocks if block.text)

    def get_entity_by_symbol(self, symbol: str) -> Optional[EntityAnchor]:
        """
        Find an entity anchor by its resolved symbol.

        Args:
            symbol: Ticker symbol to search for.

        Returns:
            EntityAnchor if found, None otherwise.
        """
        for anchor in self.entity_anchors:
            if anchor.resolved_symbol and anchor.resolved_symbol.upper() == symbol.upper():
                return anchor
        return None

    def get_temporal_anchors_by_type(
        self,
        anchor_type: Literal["published_at", "mentioned_at", "resolved_at", "effective_trade_at"]
    ) -> List[TemporalAnchor]:
        """
        Filter temporal anchors by type.

        Args:
            anchor_type: Type of temporal anchor.

        Returns:
            List of matching temporal anchors.
        """
        return [a for a in self.temporal_anchors if a.anchor_type == anchor_type]

    def compute_overall_quality(self) -> float:
        """
        Compute overall quality score from block quality cards.

        Returns:
            Average quality score across all blocks.
        """
        if not self.blocks:
            return self.quality_card.overall_score

        block_scores = [b.quality_card.overall_score for b in self.blocks]
        return sum(block_scores) / len(block_scores)

    def get_blocks_requiring_review(self) -> List[ContentBlock]:
        """
        Get blocks with gate_status 'review' or 'reject'.

        Returns:
            List of blocks requiring manual review.
        """
        return [
            b for b in self.blocks
            if b.quality_card.gate_status in ("review", "reject")
        ]
