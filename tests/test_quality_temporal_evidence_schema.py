"""Tests for QualityCard, TemporalAnchor, EvidenceSpan, and EntityAnchor schemas.

Tests cover:
- QualityCard creation, derived fields, and gate status
- TemporalAnchor creation and resolution
- EvidenceSpan creation and overlap detection
- EntityAnchor creation and normalization
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from finer.schemas.quality import QualityCard, GATE_STATUS_LITERAL
from finer.schemas.temporal import (
    TemporalAnchor,
    TEMPORAL_ANCHOR_TYPE_LITERAL,
    RESOLUTION_STRATEGY_LITERAL,
)
from finer.schemas.evidence import EvidenceSpan
from finer.schemas.entity_anchor import EntityAnchor, ENTITY_TYPE_LITERAL


# =============================================================================
# QualityCard Tests
# =============================================================================

def test_quality_card_creation():
    """Test creating a QualityCard with all dimension scores."""
    card = QualityCard(
        readability_score=0.9,
        semantic_completeness_score=0.85,
        financial_relevance_score=0.95,
        entity_resolution_score=0.8,
        temporal_resolution_score=0.75,
        evidence_traceability_score=0.85,
    )

    assert card.readability_score == 0.9
    assert card.semantic_completeness_score == 0.85
    assert card.financial_relevance_score == 0.95
    assert card.entity_resolution_score == 0.8
    assert card.temporal_resolution_score == 0.75
    assert card.evidence_traceability_score == 0.85


def test_quality_card_overall_score_derivation():
    """Test that overall_score is auto-computed as average."""
    card = QualityCard(
        readability_score=1.0,
        semantic_completeness_score=1.0,
        financial_relevance_score=1.0,
        entity_resolution_score=1.0,
        temporal_resolution_score=1.0,
        evidence_traceability_score=1.0,
    )

    assert card.overall_score == 1.0

    card2 = QualityCard(
        readability_score=0.0,
        semantic_completeness_score=0.0,
        financial_relevance_score=0.0,
        entity_resolution_score=0.0,
        temporal_resolution_score=0.0,
        evidence_traceability_score=0.0,
    )

    assert card2.overall_score == 0.0


def test_quality_card_gate_status_pass():
    """Test gate status 'pass' for high quality scores."""
    card = QualityCard(
        readability_score=0.9,
        semantic_completeness_score=0.85,
        financial_relevance_score=0.9,
        entity_resolution_score=0.8,
        temporal_resolution_score=0.85,
        evidence_traceability_score=0.8,
    )

    assert card.gate_status == "pass"
    assert card.gate_reasons == []


def test_quality_card_gate_status_review():
    """Test gate status 'review' for medium quality scores."""
    card = QualityCard(
        readability_score=0.7,
        semantic_completeness_score=0.65,
        financial_relevance_score=0.7,
        entity_resolution_score=0.4,  # Below 0.5 threshold
        temporal_resolution_score=0.65,
        evidence_traceability_score=0.6,
    )

    assert card.gate_status == "review"
    assert len(card.gate_reasons) > 0


def test_quality_card_gate_status_reject():
    """Test gate status 'reject' for low quality scores."""
    card = QualityCard(
        readability_score=0.3,
        semantic_completeness_score=0.25,  # Below 0.3 threshold
        financial_relevance_score=0.2,  # Below 0.3 threshold
        entity_resolution_score=0.3,
        temporal_resolution_score=0.35,
        evidence_traceability_score=0.3,
    )

    assert card.gate_status == "reject"
    assert len(card.gate_reasons) > 0


def test_quality_card_invalid_score_range():
    """Test that scores outside [0.0, 1.0] raise validation error."""
    with pytest.raises(ValidationError):
        QualityCard(
            readability_score=1.5,  # Invalid
            semantic_completeness_score=0.5,
            financial_relevance_score=0.5,
            entity_resolution_score=0.5,
            temporal_resolution_score=0.5,
            evidence_traceability_score=0.5,
        )

    with pytest.raises(ValidationError):
        QualityCard(
            readability_score=-0.1,  # Invalid
            semantic_completeness_score=0.5,
            financial_relevance_score=0.5,
            entity_resolution_score=0.5,
            temporal_resolution_score=0.5,
            evidence_traceability_score=0.5,
        )


def test_quality_card_factory_methods():
    """Test QualityCard factory methods."""
    # Default uniform score
    default_card = QualityCard.create_default(0.6)
    assert default_card.overall_score == 0.6

    # High quality
    high_card = QualityCard.create_high_quality()
    assert high_card.gate_status == "pass"
    assert high_card.overall_score >= 0.85

    # Low quality
    low_card = QualityCard.create_low_quality()
    assert low_card.gate_status == "reject"
    assert low_card.overall_score < 0.4


def test_quality_card_get_weakest_dimension():
    """Test identifying the weakest dimension."""
    card = QualityCard(
        readability_score=0.9,
        semantic_completeness_score=0.85,
        financial_relevance_score=0.4,  # Weakest
        entity_resolution_score=0.8,
        temporal_resolution_score=0.75,
        evidence_traceability_score=0.85,
    )

    weakest_name, weakest_score = card.get_weakest_dimension()
    assert weakest_name == "financial_relevance"
    assert weakest_score == 0.4


# =============================================================================
# TemporalAnchor Tests
# =============================================================================

def test_temporal_anchor_creation():
    """Test creating a TemporalAnchor with all required fields."""
    anchor = TemporalAnchor(
        anchor_type="published_at",
        raw_text="2024-01-15 10:30:00",
        resolved_time=datetime(2024, 1, 15, 10, 30),
        confidence=0.95,
        resolution_strategy="explicit_date",
    )

    assert anchor.anchor_type == "published_at"
    assert anchor.raw_text == "2024-01-15 10:30:00"
    assert anchor.resolved_time == datetime(2024, 1, 15, 10, 30)
    assert anchor.confidence == 0.95
    assert anchor.resolution_strategy == "explicit_date"


def test_temporal_anchor_types():
    """Test all defined temporal anchor types."""
    anchor_types: list[TEMPORAL_ANCHOR_TYPE_LITERAL] = [
        "published_at",
        "mentioned_at",
        "resolved_at",
        "effective_trade_at",
    ]

    for anchor_type in anchor_types:
        anchor = TemporalAnchor(
            anchor_type=anchor_type,
            raw_text="test",
            confidence=0.8,
            resolution_strategy="unknown",
        )
        assert anchor.anchor_type == anchor_type


def test_temporal_anchor_resolution_strategies():
    """Test all defined resolution strategies."""
    strategies: list[RESOLUTION_STRATEGY_LITERAL] = [
        "explicit_date",
        "relative_date",
        "fiscal_period",
        "market_hours",
        "llm_inference",
        "rule_based",
        "unknown",
    ]

    for strategy in strategies:
        anchor = TemporalAnchor(
            anchor_type="mentioned_at",
            raw_text="test",
            confidence=0.8,
            resolution_strategy=strategy,
        )
        assert anchor.resolution_strategy == strategy


def test_temporal_anchor_factory_methods():
    """Test TemporalAnchor factory methods."""
    # published_at
    published = TemporalAnchor.create_published_at(
        raw_text="2024-01-15",
        resolved_time=datetime(2024, 1, 15),
        confidence=1.0,
    )
    assert published.anchor_type == "published_at"
    assert published.resolution_strategy == "explicit_date"

    # mentioned_at
    mentioned = TemporalAnchor.create_mentioned_at(
        raw_text="上周五",
        resolved_time=datetime(2024, 1, 12),
        confidence=0.7,
        resolution_strategy="rule_based",
    )
    assert mentioned.anchor_type == "mentioned_at"
    assert mentioned.resolution_strategy == "rule_based"

    # effective_trade_at
    effective = TemporalAnchor.create_effective_trade_at(
        raw_text="下周一开盘",
        resolved_time=datetime(2024, 1, 22, 9, 30),
        confidence=0.85,
        resolution_strategy="rule_based",
        timezone="Asia/Shanghai",
    )
    assert effective.anchor_type == "effective_trade_at"
    assert effective.timezone == "Asia/Shanghai"


def test_temporal_anchor_is_resolved():
    """Test is_resolved method."""
    resolved = TemporalAnchor(
        anchor_type="published_at",
        raw_text="2024-01-15",
        resolved_time=datetime(2024, 1, 15),
        confidence=0.9,
        resolution_strategy="explicit_date",
    )
    assert resolved.is_resolved() is True

    unresolved = TemporalAnchor(
        anchor_type="mentioned_at",
        raw_text="某个时间点",
        resolved_time=None,
        confidence=0.3,
        resolution_strategy="unknown",
    )
    assert unresolved.is_resolved() is False


def test_temporal_anchor_get_formatted_time():
    """Test get_formatted_time method."""
    anchor = TemporalAnchor(
        anchor_type="published_at",
        raw_text="2024-01-15",
        resolved_time=datetime(2024, 1, 15, 10, 30, 45),
        confidence=0.9,
        resolution_strategy="explicit_date",
    )

    formatted = anchor.get_formatted_time("%Y-%m-%d")
    assert formatted == "2024-01-15"

    formatted_full = anchor.get_formatted_time("%Y-%m-%d %H:%M:%S")
    assert formatted_full == "2024-01-15 10:30:45"


def test_temporal_anchor_invalid_confidence():
    """Test that invalid confidence raises error."""
    with pytest.raises(ValidationError):
        TemporalAnchor(
            anchor_type="published_at",
            raw_text="test",
            confidence=1.5,  # Invalid
            resolution_strategy="explicit_date",
        )


# =============================================================================
# EvidenceSpan Tests
# =============================================================================

def test_evidence_span_creation():
    """Test creating an EvidenceSpan."""
    span = EvidenceSpan(
        block_id="block_123",
        char_start=10,
        char_end=25,
        text="苹果公司 (AAPL)",
        confidence=0.95,
    )

    assert span.block_id == "block_123"
    assert span.char_start == 10
    assert span.char_end == 25
    assert span.text == "苹果公司 (AAPL)"
    assert span.confidence == 0.95


def test_evidence_span_char_range_validation():
    """Test that char_start < char_end is enforced."""
    with pytest.raises(ValidationError):
        EvidenceSpan(
            block_id="block_123",
            char_start=25,
            char_end=10,  # Invalid: must be > char_start
            text="test",
            confidence=0.9,
        )

    with pytest.raises(ValidationError):
        EvidenceSpan(
            block_id="block_123",
            char_start=10,
            char_end=10,  # Invalid: must be > char_start
            text="test",
            confidence=0.9,
        )


def test_evidence_span_create_from_text():
    """Test creating EvidenceSpan from full text."""
    full_text = "这是一段包含苹果公司的测试文本。"
    span = EvidenceSpan.create_from_text(
        block_id="block_123",
        full_text=full_text,
        start=4,
        end=8,
        confidence=0.9,
    )

    assert span.block_id == "block_123"
    assert span.char_start == 4
    assert span.char_end == 8
    assert span.text == "包含苹果"
    assert span.confidence == 0.9


def test_evidence_span_get_length():
    """Test get_length method."""
    span = EvidenceSpan(
        block_id="block_123",
        char_start=10,
        char_end=25,
        text="test text",
        confidence=0.9,
    )

    assert span.get_length() == 15


def test_evidence_span_overlaps_with():
    """Test overlap detection."""
    span1 = EvidenceSpan(
        block_id="block_123",
        char_start=10,
        char_end=20,
        text="span1",
        confidence=0.9,
    )

    # Overlapping span
    span2 = EvidenceSpan(
        block_id="block_123",
        char_start=15,
        char_end=25,
        text="span2",
        confidence=0.9,
    )

    # Non-overlapping span
    span3 = EvidenceSpan(
        block_id="block_123",
        char_start=25,
        char_end=30,
        text="span3",
        confidence=0.9,
    )

    # Different block
    span4 = EvidenceSpan(
        block_id="block_456",
        char_start=10,
        char_end=20,
        text="span4",
        confidence=0.9,
    )

    assert span1.overlaps_with(span2) is True
    assert span1.overlaps_with(span3) is False
    assert span1.overlaps_with(span4) is False


def test_evidence_span_contains():
    """Test span containment."""
    outer = EvidenceSpan(
        block_id="block_123",
        char_start=10,
        char_end=30,
        text="outer",
        confidence=0.9,
    )

    inner = EvidenceSpan(
        block_id="block_123",
        char_start=15,
        char_end=25,
        text="inner",
        confidence=0.9,
    )

    different_block = EvidenceSpan(
        block_id="block_456",
        char_start=15,
        char_end=25,
        text="different",
        confidence=0.9,
    )

    assert outer.contains(inner) is True
    assert inner.contains(outer) is False
    assert outer.contains(different_block) is False


def test_evidence_span_merge():
    """Test span merging."""
    span1 = EvidenceSpan(
        block_id="block_123",
        char_start=10,
        char_end=20,
        text="first span",
        confidence=0.8,
    )

    span2 = EvidenceSpan(
        block_id="block_123",
        char_start=15,
        char_end=30,
        text="second span",
        confidence=0.9,
    )

    merged = span1.merge_with(span2)

    assert merged.char_start == 10
    assert merged.char_end == 30
    assert merged.confidence == 0.9  # Max confidence


def test_evidence_span_merge_different_blocks():
    """Test that merging different blocks raises error."""
    span1 = EvidenceSpan(
        block_id="block_123",
        char_start=10,
        char_end=20,
        text="span1",
        confidence=0.9,
    )

    span2 = EvidenceSpan(
        block_id="block_456",
        char_start=15,
        char_end=25,
        text="span2",
        confidence=0.9,
    )

    with pytest.raises(ValueError) as exc_info:
        span1.merge_with(span2)

    assert "different blocks" in str(exc_info.value)


# =============================================================================
# EntityAnchor Tests
# =============================================================================

def test_entity_anchor_creation():
    """Test creating an EntityAnchor."""
    anchor = EntityAnchor(
        entity_type="stock",
        raw_text="苹果公司 (AAPL)",
        resolved_name="Apple Inc.",
        resolved_symbol="AAPL",
        market="US",
        confidence=0.95,
    )

    assert anchor.entity_type == "stock"
    assert anchor.raw_text == "苹果公司 (AAPL)"
    assert anchor.resolved_name == "Apple Inc."
    assert anchor.resolved_symbol == "AAPL"
    assert anchor.market == "US"
    assert anchor.confidence == 0.95


def test_entity_anchor_symbol_normalization():
    """Test that resolved_symbol is normalized to uppercase."""
    anchor = EntityAnchor(
        entity_type="stock",
        raw_text="苹果公司",
        resolved_symbol="aapl",  # lowercase
        confidence=0.9,
    )

    assert anchor.resolved_symbol == "AAPL"


def test_entity_anchor_market_normalization():
    """Test that market is normalized to uppercase."""
    anchor = EntityAnchor(
        entity_type="stock",
        raw_text="港股",
        resolved_symbol="00700",
        market="hk",  # lowercase
        confidence=0.9,
    )

    assert anchor.market == "HK"


def test_entity_anchor_all_types():
    """Test all defined entity types."""
    entity_types: list[ENTITY_TYPE_LITERAL] = [
        "stock",
        "etf",
        "index",
        "crypto",
        "commodity",
        "forex",
        "bond",
        "fund",
        "company",
        "person",
        "organization",
        "sector",
        "concept",
        "unknown",
    ]

    for entity_type in entity_types:
        anchor = EntityAnchor(
            entity_type=entity_type,
            raw_text="test",
            confidence=0.8,
        )
        assert anchor.entity_type == entity_type


def test_entity_anchor_factory_methods():
    """Test EntityAnchor factory methods."""
    # Stock
    stock = EntityAnchor.create_stock(
        raw_text="苹果 (AAPL)",
        resolved_symbol="AAPL",
        resolved_name="Apple Inc.",
        market="US",
        confidence=0.95,
    )
    assert stock.entity_type == "stock"
    assert stock.resolved_symbol == "AAPL"

    # Crypto
    crypto = EntityAnchor.create_crypto(
        raw_text="比特币",
        resolved_symbol="BTC",
        resolved_name="Bitcoin",
        confidence=0.9,
    )
    assert crypto.entity_type == "crypto"
    assert crypto.market == "CRYPTO"

    # Unresolved
    unresolved = EntityAnchor.create_unresolved(
        raw_text="某公司",
        entity_type="company",
        confidence=0.3,
    )
    assert unresolved.is_resolved() is False


def test_entity_anchor_is_resolved():
    """Test is_resolved method."""
    resolved = EntityAnchor(
        entity_type="stock",
        raw_text="AAPL",
        resolved_symbol="AAPL",
        confidence=0.9,
    )
    assert resolved.is_resolved() is True

    unresolved = EntityAnchor(
        entity_type="company",
        raw_text="某公司",
        confidence=0.3,
    )
    assert unresolved.is_resolved() is False


def test_entity_anchor_get_display_name():
    """Test get_display_name method."""
    # With resolved_name
    anchor1 = EntityAnchor(
        entity_type="stock",
        raw_text="苹果",
        resolved_name="Apple Inc.",
        resolved_symbol="AAPL",
        confidence=0.9,
    )
    assert anchor1.get_display_name() == "Apple Inc."

    # With only resolved_symbol
    anchor2 = EntityAnchor(
        entity_type="stock",
        raw_text="苹果",
        resolved_symbol="AAPL",
        confidence=0.9,
    )
    assert anchor2.get_display_name() == "AAPL"

    # Unresolved
    anchor3 = EntityAnchor(
        entity_type="company",
        raw_text="某公司",
        confidence=0.3,
    )
    assert anchor3.get_display_name() == "某公司"


def test_entity_anchor_get_full_identifier():
    """Test get_full_identifier method."""
    anchor = EntityAnchor(
        entity_type="stock",
        raw_text="AAPL",
        resolved_symbol="AAPL",
        market="US",
        confidence=0.9,
    )
    assert anchor.get_full_identifier() == "US:AAPL"

    anchor_no_market = EntityAnchor(
        entity_type="stock",
        raw_text="AAPL",
        resolved_symbol="AAPL",
        confidence=0.9,
    )
    assert anchor_no_market.get_full_identifier() == "AAPL"

    unresolved = EntityAnchor(
        entity_type="company",
        raw_text="某公司",
        confidence=0.3,
    )
    assert unresolved.get_full_identifier() is None


def test_entity_anchor_has_high_confidence():
    """Test has_high_confidence method."""
    anchor_high = EntityAnchor(
        entity_type="stock",
        raw_text="AAPL",
        resolved_symbol="AAPL",
        confidence=0.9,
    )
    assert anchor_high.has_high_confidence() is True
    assert anchor_high.has_high_confidence(threshold=0.95) is False

    anchor_low = EntityAnchor(
        entity_type="stock",
        raw_text="AAPL",
        resolved_symbol="AAPL",
        confidence=0.6,
    )
    assert anchor_low.has_high_confidence() is False


# =============================================================================
# Serialization Tests
# =============================================================================

def test_quality_card_serialization():
    """Test QualityCard serialization and deserialization."""
    card = QualityCard(
        readability_score=0.9,
        semantic_completeness_score=0.85,
        financial_relevance_score=0.9,
        entity_resolution_score=0.8,
        temporal_resolution_score=0.75,
        evidence_traceability_score=0.85,
    )

    data = card.to_dict()
    restored = QualityCard.from_dict(data)

    assert restored.overall_score == card.overall_score
    assert restored.gate_status == card.gate_status


def test_temporal_anchor_serialization():
    """Test TemporalAnchor serialization and deserialization."""
    anchor = TemporalAnchor(
        anchor_type="published_at",
        raw_text="2024-01-15",
        resolved_time=datetime(2024, 1, 15, 10, 30),
        confidence=0.9,
        resolution_strategy="explicit_date",
        timezone="Asia/Shanghai",
    )

    data = anchor.to_dict()
    restored = TemporalAnchor.from_dict(data)

    assert restored.anchor_type == anchor.anchor_type
    assert restored.raw_text == anchor.raw_text


def test_evidence_span_serialization():
    """Test EvidenceSpan serialization and deserialization."""
    span = EvidenceSpan(
        block_id="block_123",
        char_start=10,
        char_end=25,
        text="苹果公司",
        confidence=0.95,
    )

    data = span.to_dict()
    restored = EvidenceSpan.from_dict(data)

    assert restored.block_id == span.block_id
    assert restored.text == span.text


def test_entity_anchor_serialization():
    """Test EntityAnchor serialization and deserialization."""
    anchor = EntityAnchor(
        entity_type="stock",
        raw_text="苹果公司 (AAPL)",
        resolved_name="Apple Inc.",
        resolved_symbol="AAPL",
        market="US",
        confidence=0.95,
        aliases=["Apple", "苹果"],
    )

    data = anchor.to_dict()
    restored = EntityAnchor.from_dict(data)

    assert restored.resolved_symbol == anchor.resolved_symbol
    assert restored.aliases == anchor.aliases
