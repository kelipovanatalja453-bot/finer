"""Evidence Span Schema — Traceability system for content extraction.

This module defines evidence span schemas for enabling traceability from
extracted entities, events, and trade actions back to their source text.

EvidenceSpan captures the exact location (character offsets) of relevant
text within a content block, enabling:
1. Source traceability for all extractions
2. Confidence scoring based on text quality
3. Human review support with highlighted evidence

Schema Version: v0.5
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


# =============================================================================
# Evidence Span Model
# =============================================================================

class EvidenceSpan(BaseModel):
    """Traceable text span within a content block.

    EvidenceSpan captures the exact location of relevant text within a
    content block, enabling traceability from extracted information
    back to its source.

    Attributes:
        schema_version: Schema version for backward compatibility.
        evidence_span_id: Unique identifier for this evidence span.
        block_id: ID of the content block containing this span.
        char_start: Starting character index within the block text.
        char_end: Ending character index within the block text.
        text: The text content of this span (extracted substring).
        confidence: Confidence score for this evidence (0.0-1.0).
        span_type: Type of evidence (entity, temporal, event, action).
        metadata: Additional extensible metadata.

    Example:
        >>> span = EvidenceSpan(
        ...     evidence_span_id="span_abc123",
        ...     block_id="block_xyz",
        ...     char_start=42,
        ...     char_end=58,
        ...     text="苹果公司 (AAPL)",
        ...     confidence=0.95,
        ...     span_type="entity",
        ... )
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
    # Core Fields (Required)
    # =========================================================================

    evidence_span_id: str = Field(
        default_factory=lambda: f"span_{uuid4().hex[:12]}",
        description="Unique identifier for this evidence span"
    )

    block_id: str = Field(
        ...,
        description="ID of the content block containing this span"
    )

    char_start: int = Field(
        ...,
        ge=0,
        description="Starting character index within the block text"
    )

    char_end: int = Field(
        ...,
        ge=0,
        description="Ending character index within the block text"
    )

    text: str = Field(
        ...,
        description="The text content of this span"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this evidence (0.0-1.0)"
    )

    # =========================================================================
    # Optional Fields
    # =========================================================================

    span_type: Optional[str] = Field(
        None,
        description="Type of evidence (entity, temporal, event, action)"
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
    def validate_char_range(self) -> EvidenceSpan:
        """Ensure character range is valid."""
        if self.char_start >= self.char_end:
            raise ValueError(
                f"char_start ({self.char_start}) must be less than "
                f"char_end ({self.char_end})"
            )
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
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceSpan:
        """
        Create EvidenceSpan from dictionary.

        Args:
            data: Dictionary with evidence span data.

        Returns:
            EvidenceSpan instance.
        """
        return cls.model_validate(data)

    @classmethod
    def create_from_text(
        cls,
        block_id: str,
        full_text: str,
        start: int,
        end: int,
        confidence: float = 1.0,
        span_type: Optional[str] = None,
    ) -> EvidenceSpan:
        """
        Create an EvidenceSpan by extracting from full text.

        Args:
            block_id: ID of the content block.
            full_text: Full text of the block.
            start: Starting character index.
            end: Ending character index.
            confidence: Confidence score.
            span_type: Type of evidence.

        Returns:
            EvidenceSpan instance with extracted text.

        Raises:
            ValueError: If indices are out of range.
        """
        if start < 0 or end > len(full_text):
            raise ValueError(
                f"Character indices out of range: [{start}, {end}] for text of length {len(full_text)}"
            )

        extracted_text = full_text[start:end]

        return cls(
            block_id=block_id,
            char_start=start,
            char_end=end,
            text=extracted_text,
            confidence=confidence,
            span_type=span_type,
        )

    def get_length(self) -> int:
        """
        Get the length of the evidence span in characters.

        Returns:
            Number of characters in the span.
        """
        return self.char_end - self.char_start

    def overlaps_with(self, other: EvidenceSpan) -> bool:
        """
        Check if this span overlaps with another span in the same block.

        Args:
            other: Another EvidenceSpan to compare.

        Returns:
            True if spans overlap and are in the same block.
        """
        if self.block_id != other.block_id:
            return False

        return (
            self.char_start < other.char_end and
            other.char_start < self.char_end
        )

    def contains(self, other: EvidenceSpan) -> bool:
        """
        Check if this span fully contains another span.

        Args:
            other: Another EvidenceSpan to compare.

        Returns:
            True if this span contains the other (same block, wider range).
        """
        if self.block_id != other.block_id:
            return False

        return (
            self.char_start <= other.char_start and
            self.char_end >= other.char_end
        )

    def merge_with(self, other: EvidenceSpan) -> EvidenceSpan:
        """
        Merge this span with another overlapping span.

        Args:
            other: Another EvidenceSpan to merge with.

        Returns:
            New EvidenceSpan covering the combined range.

        Raises:
            ValueError: If spans are in different blocks or don't overlap.
        """
        if self.block_id != other.block_id:
            raise ValueError("Cannot merge spans from different blocks")

        if not self.overlaps_with(other):
            raise ValueError("Cannot merge non-overlapping spans")

        merged_start = min(self.char_start, other.char_start)
        merged_end = max(self.char_end, other.char_end)
        merged_text = self.text if len(self.text) >= len(other.text) else other.text
        merged_confidence = max(self.confidence, other.confidence)

        return EvidenceSpan(
            block_id=self.block_id,
            char_start=merged_start,
            char_end=merged_end,
            text=merged_text,
            confidence=merged_confidence,
            span_type=self.span_type or other.span_type,
        )
