"""Quality Card Schema — Multi-dimensional quality scoring system.

This module defines quality assessment schemas for content envelopes
and content blocks. The QualityCard provides a six-dimensional quality
scoring system with automatic gate status derivation.

Dimensions:
1. readability_score: Text clarity and formatting quality
2. semantic_completeness_score: Information completeness
3. financial_relevance_score: Relevance to financial/investment domain
4. entity_resolution_score: Quality of entity identification
5. temporal_resolution_score: Quality of time reference extraction
6. evidence_traceability_score: Ability to trace back to source

Schema Version: v0.5
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


# =============================================================================
# Gate Status Type
# =============================================================================

GATE_STATUS_LITERAL = Literal["pass", "review", "reject"]


# =============================================================================
# Quality Card Model
# =============================================================================

class QualityCard(BaseModel):
    """Multi-dimensional quality scoring system.

    QualityCard provides a comprehensive quality assessment across six
    dimensions, with automatic derivation of overall score and gate status.

    Attributes:
        schema_version: Schema version for backward compatibility.
        readability_score: Text clarity and formatting quality (0.0-1.0).
        semantic_completeness_score: Information completeness (0.0-1.0).
        financial_relevance_score: Relevance to financial domain (0.0-1.0).
        entity_resolution_score: Quality of entity identification (0.0-1.0).
        temporal_resolution_score: Quality of time reference extraction (0.0-1.0).
        evidence_traceability_score: Traceability to source (0.0-1.0).
        overall_score: Derived average of all dimension scores.
        gate_status: Automatic quality gate decision.
        gate_reasons: Reasons for gate status (if not 'pass').

    Example:
        >>> card = QualityCard(
        ...     readability_score=0.9,
        ...     semantic_completeness_score=0.8,
        ...     financial_relevance_score=0.95,
        ...     entity_resolution_score=0.7,
        ...     temporal_resolution_score=0.6,
        ...     evidence_traceability_score=0.85,
        ... )
        >>> card.overall_score  # Auto-computed
        0.8
        >>> card.gate_status  # Auto-derived
        'pass'
    """
    model_config = ConfigDict(strict=True)

    # =========================================================================
    # Schema Version
    # =========================================================================

    schema_version: str = Field(
        default="v0.5",
        description="Schema version for backward compatibility"
    )

    # =========================================================================
    # Six Dimension Scores (Required)
    # =========================================================================

    readability_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Text clarity and formatting quality (0.0-1.0)"
    )

    semantic_completeness_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Information completeness (0.0-1.0)"
    )

    financial_relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance to financial/investment domain (0.0-1.0)"
    )

    entity_resolution_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Quality of entity identification (0.0-1.0)"
    )

    temporal_resolution_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Quality of time reference extraction (0.0-1.0)"
    )

    evidence_traceability_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Traceability to source (0.0-1.0)"
    )

    # =========================================================================
    # Derived Fields
    # =========================================================================

    overall_score: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Average of all dimension scores (auto-computed)"
    )

    gate_status: GATE_STATUS_LITERAL = Field(
        "pass",
        description="Automatic quality gate decision"
    )

    gate_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons for gate status (if not 'pass')"
    )

    # =========================================================================
    # Validators
    # =========================================================================

    @model_validator(mode='after')
    def compute_derived_fields(self) -> QualityCard:
        """Auto-compute overall score, gate status, and reasons."""
        # Compute overall score (average of six dimensions)
        scores = [
            self.readability_score,
            self.semantic_completeness_score,
            self.financial_relevance_score,
            self.entity_resolution_score,
            self.temporal_resolution_score,
            self.evidence_traceability_score,
        ]
        self.overall_score = round(sum(scores) / len(scores), 2)

        # Determine gate status and reasons
        reasons: List[str] = []

        # Check for critical failures (score < 0.3)
        if self.readability_score < 0.3:
            reasons.append("readability_score below 0.3 threshold")
        if self.semantic_completeness_score < 0.3:
            reasons.append("semantic_completeness_score below 0.3 threshold")
        if self.financial_relevance_score < 0.3:
            reasons.append("financial_relevance_score below 0.3 threshold")

        # Check for warning conditions (score < 0.5)
        if self.entity_resolution_score < 0.5:
            reasons.append("entity_resolution_score below 0.5 threshold")
        if self.temporal_resolution_score < 0.5:
            reasons.append("temporal_resolution_score below 0.5 threshold")
        if self.evidence_traceability_score < 0.5:
            reasons.append("evidence_traceability_score below 0.5 threshold")

        # Set gate status based on reasons and overall score
        if self.overall_score < 0.4 or len([r for r in reasons if "0.3" in r]) >= 2:
            self.gate_status = "reject"
            self.gate_reasons = reasons
        elif self.overall_score < 0.7 or reasons:
            self.gate_status = "review"
            self.gate_reasons = reasons
        else:
            self.gate_status = "pass"
            self.gate_reasons = []

        return self

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QualityCard:
        """
        Create QualityCard from dictionary.

        Args:
            data: Dictionary with quality scores.

        Returns:
            QualityCard instance.
        """
        return cls.model_validate(data)

    @classmethod
    def create_default(cls, overall: float = 0.5) -> QualityCard:
        """
        Create a QualityCard with uniform scores.

        Args:
            overall: Score to apply to all dimensions.

        Returns:
            QualityCard with uniform scores.
        """
        return cls(
            readability_score=overall,
            semantic_completeness_score=overall,
            financial_relevance_score=overall,
            entity_resolution_score=overall,
            temporal_resolution_score=overall,
            evidence_traceability_score=overall,
        )

    @classmethod
    def create_high_quality(cls) -> QualityCard:
        """
        Create a high-quality QualityCard (all scores 0.9+).

        Returns:
            QualityCard indicating high quality.
        """
        return cls(
            readability_score=0.95,
            semantic_completeness_score=0.9,
            financial_relevance_score=0.95,
            entity_resolution_score=0.9,
            temporal_resolution_score=0.85,
            evidence_traceability_score=0.9,
        )

    @classmethod
    def create_low_quality(cls) -> QualityCard:
        """
        Create a low-quality QualityCard (all scores 0.3-0.5).

        Returns:
            QualityCard indicating low quality.
        """
        return cls(
            readability_score=0.4,
            semantic_completeness_score=0.35,
            financial_relevance_score=0.3,
            entity_resolution_score=0.4,
            temporal_resolution_score=0.35,
            evidence_traceability_score=0.3,
        )

    def get_weakest_dimension(self) -> tuple[str, float]:
        """
        Identify the lowest-scoring dimension.

        Returns:
            Tuple of (dimension_name, score).
        """
        dimensions = {
            "readability": self.readability_score,
            "semantic_completeness": self.semantic_completeness_score,
            "financial_relevance": self.financial_relevance_score,
            "entity_resolution": self.entity_resolution_score,
            "temporal_resolution": self.temporal_resolution_score,
            "evidence_traceability": self.evidence_traceability_score,
        }
        weakest = min(dimensions.items(), key=lambda x: x[1])
        return weakest

    def get_dimension_scores(self) -> Dict[str, float]:
        """
        Get all dimension scores as a dictionary.

        Returns:
            Dictionary mapping dimension names to scores.
        """
        return {
            "readability": self.readability_score,
            "semantic_completeness": self.semantic_completeness_score,
            "financial_relevance": self.financial_relevance_score,
            "entity_resolution": self.entity_resolution_score,
            "temporal_resolution": self.temporal_resolution_score,
            "evidence_traceability": self.evidence_traceability_score,
        }
