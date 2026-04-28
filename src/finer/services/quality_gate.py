"""Quality Gate Service — Task-oriented quality gate evaluation.

This module provides quality gate evaluation for content envelopes and
quality cards. The quality gate determines whether content is ready for
V1 intent extraction, needs manual review, or should be rejected.

Default Gate Policy:
- PASS: overall >= 0.75 AND financial_relevance >= 0.6 AND evidence_traceability >= 0.6
- REVIEW: overall >= 0.45 OR any critical dimension is low/missing
- REJECT: overall < 0.45 AND financial_relevance < 0.3

Image Strategy (猫大人图片策略):
For image-based content, OCR issues should not immediately trigger rejection.
Evaluate by block:
- Large readable strategy text with high financial relevance → PASS (V1)
- Tables/charts with low OCR confidence but clear position → REVIEW
- Unrecognizable social media UI noise → DROP or low priority
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from finer.schemas.quality import QualityCard, GATE_STATUS_LITERAL
from finer.schemas.content_envelope import ContentEnvelope


# =============================================================================
# Quality Gate Decision Types
# =============================================================================

NEXT_STEP_LITERAL = Literal[
    "extract_intent",
    "manual_review",
    "reprocess_source",
    "drop",
]


# =============================================================================
# Quality Gate Models
# =============================================================================

class QualityGatePolicy(BaseModel):
    """Policy configuration for quality gate evaluation.

    Attributes:
        pass_threshold: Minimum overall score for PASS (default: 0.75).
        review_threshold: Minimum overall score for REVIEW (default: 0.45).
        financial_relevance_min: Minimum financial_relevance for PASS (default: 0.6).
        evidence_traceability_min: Minimum evidence_traceability for PASS (default: 0.6).
        reject_financial_max: Maximum financial_relevance for REJECT (default: 0.3).
        critical_dimension_min: Minimum score for critical dimensions (default: 0.3).
        warn_dimension_min: Warning threshold for dimensions (default: 0.5).
    """

    pass_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Minimum overall score for PASS"
    )

    review_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Minimum overall score for REVIEW"
    )

    financial_relevance_min: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum financial_relevance for PASS"
    )

    evidence_traceability_min: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum evidence_traceability for PASS"
    )

    reject_financial_max: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Maximum financial_relevance for REJECT"
    )

    critical_dimension_min: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum score for critical dimensions (below = warning)"
    )

    warn_dimension_min: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Warning threshold for dimensions"
    )


class QualityGateDecision(BaseModel):
    """Quality gate evaluation result.

    Attributes:
        status: Gate status (pass/review/reject).
        score: Overall quality score (0.0-1.0).
        reasons: List of reasons for the decision.
        recommended_next_step: Recommended action for this content.
        block_decisions: Per-block gate decisions (for envelope evaluation).
        metadata: Additional context for the decision.
    """

    status: GATE_STATUS_LITERAL = Field(
        ...,
        description="Gate status (pass/review/reject)"
    )

    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall quality score"
    )

    reasons: List[str] = Field(
        default_factory=list,
        description="Reasons for the decision"
    )

    recommended_next_step: NEXT_STEP_LITERAL = Field(
        ...,
        description="Recommended action for this content"
    )

    block_decisions: Optional[List["QualityGateDecision"]] = Field(
        None,
        description="Per-block gate decisions (for envelope evaluation)"
    )

    metadata: dict = Field(
        default_factory=dict,
        description="Additional context for the decision"
    )


# =============================================================================
# Default Policy Instance
# =============================================================================

DEFAULT_POLICY = QualityGatePolicy()


# =============================================================================
# Gate Evaluation Functions
# =============================================================================

def evaluate_quality_card(
    card: QualityCard,
    policy: Optional[QualityGatePolicy] = None,
) -> QualityGateDecision:
    """Evaluate a QualityCard against the gate policy.

    Args:
        card: QualityCard to evaluate.
        policy: Gate policy (uses default if None).

    Returns:
        QualityGateDecision with status, score, reasons, and next step.

    Example:
        >>> card = QualityCard(
        ...     readability_score=0.9,
        ...     semantic_completeness_score=0.85,
        ...     financial_relevance_score=0.95,
        ...     entity_resolution_score=0.8,
        ...     temporal_resolution_score=0.7,
        ...     evidence_traceability_score=0.85,
        ... )
        >>> decision = evaluate_quality_card(card)
        >>> decision.status
        'pass'
        >>> decision.recommended_next_step
        'extract_intent'
    """
    if policy is None:
        policy = DEFAULT_POLICY

    reasons: List[str] = []
    overall = card.overall_score

    # Check critical dimension failures
    critical_failures = 0

    if card.readability_score < policy.critical_dimension_min:
        reasons.append(f"readability_score ({card.readability_score:.2f}) below critical threshold ({policy.critical_dimension_min})")
        critical_failures += 1

    if card.semantic_completeness_score < policy.critical_dimension_min:
        reasons.append(f"semantic_completeness_score ({card.semantic_completeness_score:.2f}) below critical threshold ({policy.critical_dimension_min})")
        critical_failures += 1

    if card.financial_relevance_score < policy.critical_dimension_min:
        reasons.append(f"financial_relevance_score ({card.financial_relevance_score:.2f}) below critical threshold ({policy.critical_dimension_min})")
        critical_failures += 1
    elif card.financial_relevance_score < policy.financial_relevance_min:
        # Warning: below pass threshold but not critical
        reasons.append(f"financial_relevance_score ({card.financial_relevance_score:.2f}) below pass threshold ({policy.financial_relevance_min})")

    # Check warning conditions (non-critical dimensions)
    if card.entity_resolution_score < policy.warn_dimension_min:
        reasons.append(f"entity_resolution_score ({card.entity_resolution_score:.2f}) below warning threshold ({policy.warn_dimension_min})")

    if card.temporal_resolution_score < policy.warn_dimension_min:
        reasons.append(f"temporal_resolution_score ({card.temporal_resolution_score:.2f}) below warning threshold ({policy.warn_dimension_min})")

    if card.evidence_traceability_score < policy.warn_dimension_min:
        reasons.append(f"evidence_traceability_score ({card.evidence_traceability_score:.2f}) below warning threshold ({policy.warn_dimension_min})")
    elif card.evidence_traceability_score < policy.evidence_traceability_min:
        # Warning: below pass threshold but not critical
        reasons.append(f"evidence_traceability_score ({card.evidence_traceability_score:.2f}) below pass threshold ({policy.evidence_traceability_min})")

    # Determine gate status
    # REJECT: low overall AND low financial_relevance
    if overall < policy.review_threshold and card.financial_relevance_score < policy.reject_financial_max:
        return QualityGateDecision(
            status="reject",
            score=overall,
            reasons=reasons or ["Low overall score and financial relevance"],
            recommended_next_step="drop",
            metadata={
                "critical_failures": critical_failures,
                "weakest_dimension": card.get_weakest_dimension()[0],
            }
        )

    # PASS: high overall AND sufficient financial_relevance AND evidence_traceability
    if (
        overall >= policy.pass_threshold
        and card.financial_relevance_score >= policy.financial_relevance_min
        and card.evidence_traceability_score >= policy.evidence_traceability_min
        and critical_failures == 0
    ):
        return QualityGateDecision(
            status="pass",
            score=overall,
            reasons=[],
            recommended_next_step="extract_intent",
            metadata={
                "critical_failures": 0,
                "weakest_dimension": card.get_weakest_dimension()[0],
            }
        )

    # REVIEW: anything that doesn't pass or reject
    # Determine if reprocessing might help
    next_step = "manual_review"

    # If OCR/parsing issues detected, suggest reprocessing
    if card.readability_score < policy.warn_dimension_min or critical_failures > 0:
        next_step = "reprocess_source"

    return QualityGateDecision(
        status="review",
        score=overall,
        reasons=reasons or ["Score below pass threshold"],
        recommended_next_step=next_step,
        metadata={
            "critical_failures": critical_failures,
            "weakest_dimension": card.get_weakest_dimension()[0],
        }
    )


def evaluate_envelope_quality(
    envelope: ContentEnvelope,
    policy: Optional[QualityGatePolicy] = None,
) -> QualityGateDecision:
    """Evaluate a ContentEnvelope against the gate policy.

    This function evaluates both the envelope-level quality card and
    individual block quality cards. For image-based content with OCR
    issues, it applies the 猫大人图片策略 (Cat's image strategy).

    Strategy:
    - Evaluate each block independently
    - Large readable text blocks with high financial relevance → PASS
    - Tables/charts with low OCR but clear structure → REVIEW
    - Social media UI noise → DROP or low priority
    - Aggregate block decisions into overall envelope decision

    Args:
        envelope: ContentEnvelope to evaluate.
        policy: Gate policy (uses default if None).

    Returns:
        QualityGateDecision with aggregated status and block-level details.

    Example:
        >>> envelope = ContentEnvelope(
        ...     source_type="feishu_doc",
        ...     quality_card=QualityCard.create_high_quality(),
        ...     blocks=[...],
        ... )
        >>> decision = evaluate_envelope_quality(envelope)
        >>> decision.status
        'pass'
    """
    if policy is None:
        policy = DEFAULT_POLICY

    # If no blocks, evaluate envelope quality card only
    if not envelope.blocks:
        return evaluate_quality_card(envelope.quality_card, policy)

    # Evaluate each block
    block_decisions: List[QualityGateDecision] = []
    pass_count = 0
    review_count = 0
    reject_count = 0

    for block in envelope.blocks:
        block_decision = evaluate_quality_card(block.quality_card, policy)
        block_decisions.append(block_decision)

        if block_decision.status == "pass":
            pass_count += 1
        elif block_decision.status == "review":
            review_count += 1
        else:
            reject_count += 1

    # Determine overall envelope status based on block distribution
    total_blocks = len(envelope.blocks)

    # If majority of blocks pass, envelope passes
    if pass_count > total_blocks * 0.6:
        overall_status: GATE_STATUS_LITERAL = "pass"
        next_step: NEXT_STEP_LITERAL = "extract_intent"
        reasons: List[str] = []
    # If significant blocks need review, envelope goes to review
    elif review_count > 0 or (pass_count > 0 and reject_count > 0):
        overall_status = "review"
        next_step = "manual_review"
        reasons = [f"{review_count} blocks require review, {reject_count} blocks rejected"]
    # If majority rejected
    else:
        overall_status = "reject"
        next_step = "drop"
        reasons = [f"{reject_count}/{total_blocks} blocks rejected"]

    # Compute aggregated score (weighted average of block scores)
    total_score = sum(b.quality_card.overall_score for b in envelope.blocks)
    avg_score = total_score / total_blocks if total_blocks > 0 else envelope.quality_card.overall_score

    return QualityGateDecision(
        status=overall_status,
        score=round(avg_score, 2),
        reasons=reasons,
        recommended_next_step=next_step,
        block_decisions=block_decisions,
        metadata={
            "total_blocks": total_blocks,
            "pass_count": pass_count,
            "review_count": review_count,
            "reject_count": reject_count,
            "envelope_score": envelope.quality_card.overall_score,
        }
    )


# =============================================================================
# Helper Functions
# =============================================================================

def get_default_policy() -> QualityGatePolicy:
    """Get the default quality gate policy.

    Returns:
        Default QualityGatePolicy instance.
    """
    return DEFAULT_POLICY.model_copy()


def create_strict_policy() -> QualityGatePolicy:
    """Create a strict quality gate policy.

    Higher thresholds for production use.

    Returns:
        Strict QualityGatePolicy instance.
    """
    return QualityGatePolicy(
        pass_threshold=0.85,
        review_threshold=0.55,
        financial_relevance_min=0.7,
        evidence_traceability_min=0.7,
        reject_financial_max=0.35,
        critical_dimension_min=0.4,
        warn_dimension_min=0.6,
    )


def create_lenient_policy() -> QualityGatePolicy:
    """Create a lenient quality gate policy.

    Lower thresholds for experimental/development use.

    Returns:
        Lenient QualityGatePolicy instance.
    """
    return QualityGatePolicy(
        pass_threshold=0.65,
        review_threshold=0.35,
        financial_relevance_min=0.5,
        evidence_traceability_min=0.5,
        reject_financial_max=0.25,
        critical_dimension_min=0.25,
        warn_dimension_min=0.4,
    )
