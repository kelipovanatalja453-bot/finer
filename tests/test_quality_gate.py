"""Tests for Quality Gate Service.

Tests cover:
1. QualityCard evaluation with default policy
2. QualityCard evaluation with custom policy
3. ContentEnvelope evaluation (block aggregation)
4. Edge cases: missing/low dimensions, OCR issues
5. Policy variations (strict, lenient)
"""

import pytest
from datetime import datetime

from finer.schemas.quality import QualityCard
from finer.schemas.content_envelope import BlockQuality, ContentEnvelope, ContentBlock
from finer.services.quality_gate import (
    QualityGateDecision,
    QualityGatePolicy,
    evaluate_quality_card,
    evaluate_envelope_quality,
    get_default_policy,
    create_strict_policy,
    create_lenient_policy,
)


# =============================================================================
# QualityCard Evaluation Tests
# =============================================================================

class TestQualityCardEvaluation:
    """Tests for evaluate_quality_card function."""

    def test_high_quality_card_passes(self):
        """High quality card should pass."""
        card = QualityCard(
            readability_score=0.9,
            semantic_completeness_score=0.85,
            financial_relevance_score=0.95,
            entity_resolution_score=0.8,
            temporal_resolution_score=0.7,
            evidence_traceability_score=0.85,
        )

        decision = evaluate_quality_card(card)

        assert decision.status == "pass"
        assert decision.score >= 0.75
        assert decision.recommended_next_step == "extract_intent"
        assert len(decision.reasons) == 0

    def test_medium_quality_card_review(self):
        """Medium quality card should go to review."""
        card = QualityCard(
            readability_score=0.7,
            semantic_completeness_score=0.65,
            financial_relevance_score=0.6,
            entity_resolution_score=0.5,
            temporal_resolution_score=0.55,
            evidence_traceability_score=0.55,
        )

        decision = evaluate_quality_card(card)

        assert decision.status == "review"
        assert decision.score >= 0.45
        assert decision.recommended_next_step in ("manual_review", "reprocess_source")

    def test_low_quality_card_reject(self):
        """Low quality card with low financial relevance should be rejected."""
        card = QualityCard(
            readability_score=0.35,
            semantic_completeness_score=0.3,
            financial_relevance_score=0.25,
            entity_resolution_score=0.3,
            temporal_resolution_score=0.25,
            evidence_traceability_score=0.2,
        )

        decision = evaluate_quality_card(card)

        assert decision.status == "reject"
        assert decision.score < 0.45
        assert decision.recommended_next_step == "drop"

    def test_high_overall_low_financial_review(self):
        """High overall score but low financial relevance should go to review."""
        card = QualityCard(
            readability_score=0.9,
            semantic_completeness_score=0.9,
            financial_relevance_score=0.4,  # Below pass threshold
            entity_resolution_score=0.8,
            temporal_resolution_score=0.8,
            evidence_traceability_score=0.8,
        )

        decision = evaluate_quality_card(card)

        assert decision.status == "review"
        assert "financial_relevance_score" in " ".join(decision.reasons)

    def test_low_evidence_traceability_review(self):
        """Low evidence_traceability should trigger review."""
        card = QualityCard(
            readability_score=0.85,
            semantic_completeness_score=0.8,
            financial_relevance_score=0.9,
            entity_resolution_score=0.75,
            temporal_resolution_score=0.7,
            evidence_traceability_score=0.5,  # Below pass threshold
        )

        decision = evaluate_quality_card(card)

        assert decision.status == "review"
        assert decision.recommended_next_step == "manual_review"

    def test_critical_dimension_failure(self):
        """Critical dimension below 0.3 should trigger review or reject."""
        card = QualityCard(
            readability_score=0.2,  # Critical failure
            semantic_completeness_score=0.7,
            financial_relevance_score=0.8,
            entity_resolution_score=0.6,
            temporal_resolution_score=0.5,
            evidence_traceability_score=0.65,
        )

        decision = evaluate_quality_card(card)

        assert decision.status == "review"
        assert decision.recommended_next_step == "reprocess_source"
        assert any("readability" in r for r in decision.reasons)


# =============================================================================
# Custom Policy Tests
# =============================================================================

class TestCustomPolicy:
    """Tests with custom quality gate policies."""

    def test_strict_policy_rejects_medium_quality(self):
        """Strict policy should reject medium quality cards."""
        card = QualityCard(
            readability_score=0.75,
            semantic_completeness_score=0.7,
            financial_relevance_score=0.65,
            entity_resolution_score=0.6,
            temporal_resolution_score=0.55,
            evidence_traceability_score=0.6,
        )

        decision = evaluate_quality_card(card, create_strict_policy())

        # With strict policy (pass_threshold=0.85), this should be review
        assert decision.status == "review"

    def test_lenient_policy_passes_lower_quality(self):
        """Lenient policy should pass cards that default policy would review."""
        card = QualityCard(
            readability_score=0.75,
            semantic_completeness_score=0.7,
            financial_relevance_score=0.65,
            entity_resolution_score=0.65,
            temporal_resolution_score=0.65,
            evidence_traceability_score=0.65,
        )

        decision = evaluate_quality_card(card, create_lenient_policy())

        # overall_score = (0.75+0.7+0.65+0.65+0.65+0.65)/6 = 0.68 >= 0.65
        # With lenient policy (pass_threshold=0.65), this should pass
        assert decision.status == "pass"
        assert decision.recommended_next_step == "extract_intent"

    def test_custom_policy_min_thresholds(self):
        """Custom policy with different thresholds."""
        custom_policy = QualityGatePolicy(
            pass_threshold=0.75,
            financial_relevance_min=0.7,
            evidence_traceability_min=0.5,  # Lowered
        )

        card = QualityCard(
            readability_score=0.85,
            semantic_completeness_score=0.8,
            financial_relevance_score=0.75,
            entity_resolution_score=0.7,
            temporal_resolution_score=0.7,
            evidence_traceability_score=0.6,  # Would fail default (0.6), passes custom (0.5)
        )

        decision = evaluate_quality_card(card, custom_policy)

        # overall_score = (0.85+0.8+0.75+0.7+0.7+0.6)/6 = 0.73
        # But pass_threshold is 0.75, so this should be review
        assert decision.status == "review"


# =============================================================================
# ContentEnvelope Evaluation Tests
# =============================================================================

class TestEnvelopeEvaluation:
    """Tests for evaluate_envelope_quality function."""

    def create_block(self, overall_score: float, block_type: str = "paragraph") -> ContentBlock:
        """Helper to create a ContentBlock with uniform scores."""
        card = QualityCard.create_default(overall_score)
        return ContentBlock(
            block_type=block_type,
            text="Sample content",
            order=0,
            quality_card=card,
        )

    def test_empty_envelope_uses_envelope_card(self):
        """Envelope without blocks should use envelope quality card."""
        card = QualityCard.create_high_quality()
        envelope = ContentEnvelope(
            source_type="feishu_doc",
            quality_card=card,
            blocks=[],
        )

        decision = evaluate_envelope_quality(envelope)

        assert decision.status == "pass"
        assert decision.block_decisions is None

    def test_envelope_uses_envelope_card_not_block_quality(self):
        """Envelope gate uses envelope QualityCard, not per-block BlockQuality."""
        blocks = [
            ContentBlock(
                block_type="paragraph",
                text="Readable source text",
                order_index=0,
                quality=BlockQuality(
                    readability=0.1,
                    extraction_confidence=0.1,
                    structural_confidence=0.1,
                    completeness=0.1,
                    noise_score=0.9,
                ),
            )
        ]

        envelope = ContentEnvelope(
            source_type="feishu_chat",
            quality_card=QualityCard.create_default(0.8),
            blocks=blocks,
        )

        decision = evaluate_envelope_quality(envelope)

        assert decision.status == "pass"
        assert decision.recommended_next_step == "extract_intent"
        assert decision.block_decisions is None
        assert decision.metadata["total_blocks"] == 1
        assert decision.metadata["envelope_score"] == envelope.quality_card.overall_score

    def test_envelope_card_review(self):
        """Envelope-level review card should send the envelope to review."""
        envelope = ContentEnvelope(
            source_type="image",
            quality_card=QualityCard.create_default(0.6),
            blocks=[self.create_block(0.8)],
        )

        decision = evaluate_envelope_quality(envelope)

        assert decision.status == "review"
        assert decision.recommended_next_step == "manual_review"


# =============================================================================
# Edge Cases and Special Scenarios
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_uniform_scores(self):
        """Test with uniform scores across all dimensions."""
        card = QualityCard.create_default(0.75)

        decision = evaluate_quality_card(card)

        assert decision.status == "pass"

    def test_boundary_values(self):
        """Test with values at policy boundaries."""
        # Exactly at pass threshold (0.75)
        card = QualityCard(
            readability_score=0.8,
            semantic_completeness_score=0.8,
            financial_relevance_score=0.6,  # Exactly at min
            entity_resolution_score=0.8,
            temporal_resolution_score=0.8,
            evidence_traceability_score=0.6,  # Exactly at min
        )

        decision = evaluate_quality_card(card)

        # overall_score = (0.8+0.8+0.6+0.8+0.8+0.6)/6 = 0.73 < 0.75
        # Should be review (below pass threshold)
        assert decision.status == "review"

    def test_zero_scores(self):
        """Test with zero scores."""
        card = QualityCard(
            readability_score=0.0,
            semantic_completeness_score=0.0,
            financial_relevance_score=0.0,
            entity_resolution_score=0.0,
            temporal_resolution_score=0.0,
            evidence_traceability_score=0.0,
        )

        decision = evaluate_quality_card(card)

        assert decision.status == "reject"
        assert decision.score == 0.0

    def test_single_dimension_low(self):
        """Test when only one dimension is low but still passes."""
        card = QualityCard(
            readability_score=0.9,
            semantic_completeness_score=0.9,
            financial_relevance_score=0.9,
            entity_resolution_score=0.9,
            temporal_resolution_score=0.2,  # Very low (below warn_dimension_min=0.5)
            evidence_traceability_score=0.9,
        )

        decision = evaluate_quality_card(card)

        # overall_score = (0.9+0.9+0.9+0.9+0.2+0.9)/6 = 0.78 >= 0.75
        # financial_relevance >= 0.6, evidence_traceability >= 0.6
        # critical_failures = 0 (temporal is not critical)
        # Should pass because all pass conditions are met
        assert decision.status == "pass"

    def test_metadata_includes_weakest_dimension(self):
        """Decision metadata should include weakest dimension."""
        card = QualityCard(
            readability_score=0.9,
            semantic_completeness_score=0.85,
            financial_relevance_score=0.95,
            entity_resolution_score=0.4,  # Weakest
            temporal_resolution_score=0.7,
            evidence_traceability_score=0.85,
        )

        decision = evaluate_quality_card(card)

        assert "weakest_dimension" in decision.metadata
        assert decision.metadata["weakest_dimension"] == "entity_resolution"


# =============================================================================
# Policy Helper Tests
# =============================================================================

class TestPolicyHelpers:
    """Tests for policy helper functions."""

    def test_get_default_policy(self):
        """Should return default policy with correct values."""
        policy = get_default_policy()

        assert policy.pass_threshold == 0.75
        assert policy.review_threshold == 0.45
        assert policy.financial_relevance_min == 0.6

    def test_create_strict_policy(self):
        """Should return strict policy with higher thresholds."""
        policy = create_strict_policy()

        assert policy.pass_threshold > get_default_policy().pass_threshold
        assert policy.financial_relevance_min > get_default_policy().financial_relevance_min

    def test_create_lenient_policy(self):
        """Should return lenient policy with lower thresholds."""
        policy = create_lenient_policy()

        assert policy.pass_threshold < get_default_policy().pass_threshold
        assert policy.financial_relevance_min < get_default_policy().financial_relevance_min

    def test_policy_model_copy(self):
        """Default policy should be immutable via copy."""
        original = get_default_policy()
        modified = original.model_copy(update={"pass_threshold": 0.9})

        assert original.pass_threshold == 0.75
        assert modified.pass_threshold == 0.9
