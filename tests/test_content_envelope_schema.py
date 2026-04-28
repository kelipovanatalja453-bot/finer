"""Tests for ContentEnvelope and ContentBlock schemas.

Tests cover:
- ContentEnvelope creation and validation
- ContentBlock creation and validation
- Block ordering validation
- Helper methods
- Serialization/deserialization
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from finer.schemas.content_envelope import (
    ContentEnvelope,
    ContentBlock,
    BLOCK_TYPE_LITERAL,
    SOURCE_TYPE_LITERAL,
)
from finer.schemas.quality import QualityCard
from finer.schemas.temporal import TemporalAnchor
from finer.schemas.entity_anchor import EntityAnchor
from finer.schemas.evidence import EvidenceSpan


# =============================================================================
# QualityCard Fixtures
# =============================================================================

@pytest.fixture
def high_quality_card() -> QualityCard:
    """Create a high-quality QualityCard."""
    return QualityCard(
        readability_score=0.95,
        semantic_completeness_score=0.9,
        financial_relevance_score=0.95,
        entity_resolution_score=0.9,
        temporal_resolution_score=0.85,
        evidence_traceability_score=0.9,
    )


@pytest.fixture
def low_quality_card() -> QualityCard:
    """Create a low-quality QualityCard."""
    return QualityCard(
        readability_score=0.4,
        semantic_completeness_score=0.35,
        financial_relevance_score=0.3,
        entity_resolution_score=0.4,
        temporal_resolution_score=0.35,
        evidence_traceability_score=0.3,
    )


# =============================================================================
# ContentBlock Tests
# =============================================================================

def test_content_block_creation_minimal(high_quality_card: QualityCard):
    """Test creating a ContentBlock with minimal required fields."""
    block = ContentBlock(
        block_type="paragraph",
        text="This is a test paragraph.",
        order=0,
        quality_card=high_quality_card,
    )

    assert block.block_type == "paragraph"
    assert block.text == "This is a test paragraph."
    assert block.order == 0
    assert block.parent_block_id is None
    assert block.page_index is None
    assert block.bbox is None
    assert block.speaker is None
    assert block.start_time_sec is None
    assert block.end_time_sec is None
    assert block.evidence_spans == []
    assert block.metadata == {}


def test_content_block_with_all_fields(high_quality_card: QualityCard):
    """Test creating a ContentBlock with all optional fields."""
    block = ContentBlock(
        block_id="block_123",
        block_type="transcript_segment",
        text="Hello, welcome to the show.",
        order=5,
        parent_block_id="block_100",
        page_index=2,
        bbox=[10.0, 20.0, 100.0, 50.0],
        speaker="Host",
        start_time_sec=12.5,
        end_time_sec=15.3,
        quality_card=high_quality_card,
        evidence_spans=[],
        metadata={"custom": "value"},
    )

    assert block.block_id == "block_123"
    assert block.block_type == "transcript_segment"
    assert block.text == "Hello, welcome to the show."
    assert block.order == 5
    assert block.parent_block_id == "block_100"
    assert block.page_index == 2
    assert block.bbox == [10.0, 20.0, 100.0, 50.0]
    assert block.speaker == "Host"
    assert block.start_time_sec == 12.5
    assert block.end_time_sec == 15.3
    assert block.metadata == {"custom": "value"}


def test_content_block_invalid_time_range(high_quality_card: QualityCard):
    """Test that invalid time range raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        ContentBlock(
            block_type="transcript_segment",
            text="Invalid time range.",
            order=0,
            quality_card=high_quality_card,
            start_time_sec=20.0,
            end_time_sec=10.0,  # End before start
        )

    assert "start_time_sec" in str(exc_info.value).lower()


def test_content_block_invalid_bbox_length(high_quality_card: QualityCard):
    """Test that invalid bbox length raises validation error."""
    with pytest.raises(ValidationError):
        ContentBlock(
            block_type="paragraph",
            text="Invalid bbox.",
            order=0,
            quality_card=high_quality_card,
            bbox=[10.0, 20.0, 100.0],  # Only 3 values, need 4
        )


def test_content_block_auto_id_generation(high_quality_card: QualityCard):
    """Test that block_id is auto-generated if not provided."""
    block1 = ContentBlock(
        block_type="paragraph",
        text="First block.",
        order=0,
        quality_card=high_quality_card,
    )

    block2 = ContentBlock(
        block_type="paragraph",
        text="Second block.",
        order=1,
        quality_card=high_quality_card,
    )

    assert block1.block_id != block2.block_id
    assert block1.block_id.startswith("block_")
    assert block2.block_id.startswith("block_")


# =============================================================================
# ContentEnvelope Tests
# =============================================================================

def test_content_envelope_creation_minimal(high_quality_card: QualityCard):
    """Test creating a ContentEnvelope with minimal required fields."""
    envelope = ContentEnvelope(
        source_type="text",
        quality_card=high_quality_card,
    )

    assert envelope.source_type == "text"
    assert envelope.schema_version == "v0.5"
    assert envelope.blocks == []
    assert envelope.temporal_anchors == []
    assert envelope.entity_anchors == []
    assert envelope.metadata == {}
    assert envelope.envelope_id.startswith("env_")


def test_content_envelope_with_all_fields(high_quality_card: QualityCard, low_quality_card: QualityCard):
    """Test creating a ContentEnvelope with all fields."""
    block1 = ContentBlock(
        block_type="paragraph",
        text="First paragraph.",
        order=0,
        quality_card=high_quality_card,
    )

    block2 = ContentBlock(
        block_type="paragraph",
        text="Second paragraph.",
        order=1,
        quality_card=low_quality_card,
    )

    temporal_anchor = TemporalAnchor(
        anchor_type="published_at",
        raw_text="2024-01-15",
        confidence=1.0,
        resolution_strategy="explicit_date",
    )

    entity_anchor = EntityAnchor(
        entity_type="stock",
        raw_text="AAPL",
        confidence=0.95,
    )

    envelope = ContentEnvelope(
        envelope_id="env_test123",
        schema_version="v0.5",
        source_type="feishu_doc",
        source_uri="feishu://docs/abc123",
        source_title="Test Document",
        creator_id="user_456",
        creator_name="Test User",
        published_at=datetime(2024, 1, 15, 10, 30),
        ingested_at=datetime.now(),
        blocks=[block1, block2],
        quality_card=high_quality_card,
        temporal_anchors=[temporal_anchor],
        entity_anchors=[entity_anchor],
        metadata={"source": "test"},
    )

    assert envelope.envelope_id == "env_test123"
    assert envelope.source_type == "feishu_doc"
    assert envelope.source_uri == "feishu://docs/abc123"
    assert envelope.source_title == "Test Document"
    assert envelope.creator_id == "user_456"
    assert envelope.creator_name == "Test User"
    assert len(envelope.blocks) == 2
    assert len(envelope.temporal_anchors) == 1
    assert len(envelope.entity_anchors) == 1


def test_content_envelope_block_order_validation(high_quality_card: QualityCard):
    """Test that block orders must be sequential."""
    block1 = ContentBlock(
        block_type="paragraph",
        text="First block.",
        order=0,
        quality_card=high_quality_card,
    )

    block2 = ContentBlock(
        block_type="paragraph",
        text="Second block.",
        order=2,  # Skip order 1
        quality_card=high_quality_card,
    )

    with pytest.raises(ValidationError) as exc_info:
        ContentEnvelope(
            source_type="text",
            blocks=[block1, block2],
            quality_card=high_quality_card,
        )

    assert "sequential" in str(exc_info.value).lower()


def test_content_envelope_get_block_by_id(high_quality_card: QualityCard):
    """Test retrieving a block by ID."""
    block1 = ContentBlock(
        block_id="block_a",
        block_type="paragraph",
        text="First block.",
        order=0,
        quality_card=high_quality_card,
    )

    block2 = ContentBlock(
        block_id="block_b",
        block_type="paragraph",
        text="Second block.",
        order=1,
        quality_card=high_quality_card,
    )

    envelope = ContentEnvelope(
        source_type="text",
        blocks=[block1, block2],
        quality_card=high_quality_card,
    )

    found = envelope.get_block_by_id("block_b")
    assert found is not None
    assert found.text == "Second block."

    not_found = envelope.get_block_by_id("block_c")
    assert not_found is None


def test_content_envelope_get_blocks_by_type(high_quality_card: QualityCard):
    """Test filtering blocks by type."""
    paragraph1 = ContentBlock(
        block_type="paragraph",
        text="Paragraph 1.",
        order=0,
        quality_card=high_quality_card,
    )

    heading = ContentBlock(
        block_type="heading",
        text="Introduction",
        order=1,
        quality_card=high_quality_card,
    )

    paragraph2 = ContentBlock(
        block_type="paragraph",
        text="Paragraph 2.",
        order=2,
        quality_card=high_quality_card,
    )

    envelope = ContentEnvelope(
        source_type="text",
        blocks=[paragraph1, heading, paragraph2],
        quality_card=high_quality_card,
    )

    paragraphs = envelope.get_blocks_by_type("paragraph")
    assert len(paragraphs) == 2

    headings = envelope.get_blocks_by_type("heading")
    assert len(headings) == 1

    tables = envelope.get_blocks_by_type("table")
    assert len(tables) == 0


def test_content_envelope_get_text_content(high_quality_card: QualityCard):
    """Test concatenating text from all blocks."""
    block1 = ContentBlock(
        block_type="paragraph",
        text="First paragraph.",
        order=0,
        quality_card=high_quality_card,
    )

    block2 = ContentBlock(
        block_type="paragraph",
        text="Second paragraph.",
        order=1,
        quality_card=high_quality_card,
    )

    envelope = ContentEnvelope(
        source_type="text",
        blocks=[block1, block2],
        quality_card=high_quality_card,
    )

    text = envelope.get_text_content()
    assert text == "First paragraph.\n\nSecond paragraph."


def test_content_envelope_serialization(high_quality_card: QualityCard):
    """Test to_dict and from_dict methods."""
    block = ContentBlock(
        block_type="paragraph",
        text="Test paragraph.",
        order=0,
        quality_card=high_quality_card,
    )

    envelope = ContentEnvelope(
        source_type="feishu_doc",
        source_title="Test Doc",
        blocks=[block],
        quality_card=high_quality_card,
    )

    # Serialize
    data = envelope.to_dict()

    assert isinstance(data, dict)
    assert data["source_type"] == "feishu_doc"
    assert "blocks" in data
    assert len(data["blocks"]) == 1

    # Deserialize
    restored = ContentEnvelope.from_dict(data)
    assert restored.source_type == "feishu_doc"
    assert restored.source_title == "Test Doc"
    assert len(restored.blocks) == 1


def test_content_envelope_get_blocks_requiring_review():
    """Test getting blocks that require review."""
    pass_card = QualityCard(
        readability_score=0.9,
        semantic_completeness_score=0.85,
        financial_relevance_score=0.9,
        entity_resolution_score=0.8,
        temporal_resolution_score=0.85,
        evidence_traceability_score=0.8,
    )

    review_card = QualityCard(
        readability_score=0.6,
        semantic_completeness_score=0.5,
        financial_relevance_score=0.55,
        entity_resolution_score=0.4,
        temporal_resolution_score=0.5,
        evidence_traceability_score=0.45,
    )

    block_pass = ContentBlock(
        block_type="paragraph",
        text="Good quality.",
        order=0,
        quality_card=pass_card,
    )

    block_review = ContentBlock(
        block_type="paragraph",
        text="Low quality.",
        order=1,
        quality_card=review_card,
    )

    envelope = ContentEnvelope(
        source_type="text",
        blocks=[block_pass, block_review],
        quality_card=pass_card,
    )

    review_blocks = envelope.get_blocks_requiring_review()
    assert len(review_blocks) == 1
    assert review_blocks[0].text == "Low quality."


# =============================================================================
# Source Type Tests
# =============================================================================

def test_all_source_types_valid(high_quality_card: QualityCard):
    """Test that all defined source types are valid."""
    source_types: list[SOURCE_TYPE_LITERAL] = [
        "image",
        "chat",
        "feishu_doc",
        "pdf",
        "audio_transcript",
        "video_transcript",
        "text",
    ]

    for source_type in source_types:
        envelope = ContentEnvelope(
            source_type=source_type,
            quality_card=high_quality_card,
        )
        assert envelope.source_type == source_type


def test_invalid_source_type(high_quality_card: QualityCard):
    """Test that invalid source type raises error."""
    with pytest.raises(ValidationError):
        ContentEnvelope(
            source_type="invalid_type",  # type: ignore
            quality_card=high_quality_card,
        )


# =============================================================================
# Block Type Tests
# =============================================================================

def test_all_block_types_valid(high_quality_card: QualityCard):
    """Test that all defined block types are valid."""
    block_types: list[BLOCK_TYPE_LITERAL] = [
        "paragraph",
        "heading",
        "table",
        "chart",
        "image_region",
        "chat_message",
        "transcript_segment",
        "list",
        "unknown",
        # Placeholder types
        "table_region",
        "chart_region",
        "ocr_unreadable",
    ]

    for i, block_type in enumerate(block_types):
        block = ContentBlock(
            block_type=block_type,
            text=f"Block of type {block_type}",
            order=i,
            quality_card=high_quality_card,
        )
        assert block.block_type == block_type


def test_invalid_block_type(high_quality_card: QualityCard):
    """Test that invalid block type raises error."""
    with pytest.raises(ValidationError):
        ContentBlock(
            block_type="invalid_type",  # type: ignore
            text="Invalid block",
            order=0,
            quality_card=high_quality_card,
        )
