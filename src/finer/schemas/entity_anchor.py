"""Entity Anchor Schema — Entity extraction and resolution for financial content.

This module defines entity anchor schemas for capturing and resolving
named entities (companies, tickers, people, etc.) found in content.

Entity anchors support:
1. Raw text preservation for traceability
2. Resolution to standardized names and symbols
3. Market identification for trading
4. Confidence scoring for uncertain extractions
5. Linkage to evidence spans for source verification

Schema Version: v0.5
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Entity Types
# =============================================================================

ENTITY_TYPE_LITERAL = Literal[
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


# =============================================================================
# Entity Anchor Model
# =============================================================================

class EntityAnchor(BaseModel):
    """Named entity extracted from content.

    EntityAnchor captures named entities found in content, with support
    for resolution to standardized identifiers (tickers, symbols).

    Attributes:
        schema_version: Schema version for backward compatibility.
        entity_anchor_id: Unique identifier for this entity anchor.
        entity_type: Type of entity (stock, company, person, etc.).
        raw_text: Original text mentioning the entity.
        resolved_name: Standardized/resolved entity name.
        resolved_symbol: Resolved ticker or trading symbol.
        market: Market identifier (US, HK, CN, CRYPTO, etc.).
        confidence: Confidence score for the resolution (0.0-1.0).
        evidence_span_id: Link to the evidence span for traceability.
        aliases: Alternative names or symbols for this entity.
        metadata: Additional extensible metadata.

    Example:
        >>> anchor = EntityAnchor(
        ...     entity_anchor_id="entity_abc123",
        ...     entity_type="stock",
        ...     raw_text="苹果公司 (AAPL)",
        ...     resolved_name="Apple Inc.",
        ...     resolved_symbol="AAPL",
        ...     market="US",
        ...     confidence=0.95,
        ...     evidence_span_id="span_xyz",
        ...     aliases=["Apple", "苹果"],
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

    entity_anchor_id: str = Field(
        default_factory=lambda: f"entity_{uuid4().hex[:12]}",
        description="Unique identifier for this entity anchor"
    )

    entity_type: ENTITY_TYPE_LITERAL = Field(
        ...,
        description="Type of entity (stock, company, person, etc.)"
    )

    raw_text: str = Field(
        ...,
        description="Original text mentioning the entity"
    )

    # =========================================================================
    # Resolution Fields
    # =========================================================================

    resolved_name: Optional[str] = Field(
        None,
        description="Standardized/resolved entity name"
    )

    resolved_symbol: Optional[str] = Field(
        None,
        description="Resolved ticker or trading symbol"
    )

    market: Optional[str] = Field(
        None,
        description="Market identifier (US, HK, CN, CRYPTO, etc.)"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the resolution (0.0-1.0)"
    )

    # =========================================================================
    # Optional Fields
    # =========================================================================

    evidence_span_id: Optional[str] = Field(
        None,
        description="Link to the evidence span for traceability"
    )

    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names or symbols for this entity"
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

    @field_validator('resolved_symbol', mode='before')
    @classmethod
    def normalize_symbol(cls, v: Optional[str]) -> Optional[str]:
        """Normalize symbol to uppercase."""
        if v is None:
            return v
        return v.strip().upper()

    @field_validator('market', mode='before')
    @classmethod
    def normalize_market(cls, v: Optional[str]) -> Optional[str]:
        """Normalize market identifier to uppercase."""
        if v is None:
            return v
        return v.strip().upper()

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
    def from_dict(cls, data: Dict[str, Any]) -> EntityAnchor:
        """
        Create EntityAnchor from dictionary.

        Args:
            data: Dictionary with entity anchor data.

        Returns:
            EntityAnchor instance.
        """
        return cls.model_validate(data)

    @classmethod
    def create_stock(
        cls,
        raw_text: str,
        resolved_symbol: str,
        resolved_name: Optional[str] = None,
        market: str = "US",
        confidence: float = 1.0,
        evidence_span_id: Optional[str] = None,
        aliases: Optional[list[str]] = None,
    ) -> EntityAnchor:
        """
        Create a stock entity anchor.

        Args:
            raw_text: Original text mentioning the stock.
            resolved_symbol: Ticker symbol (e.g., 'AAPL').
            resolved_name: Company name (e.g., 'Apple Inc.').
            market: Market identifier.
            confidence: Confidence score.
            evidence_span_id: Evidence span link.
            aliases: Alternative names.

        Returns:
            EntityAnchor with stock type.
        """
        return cls(
            entity_type="stock",
            raw_text=raw_text,
            resolved_symbol=resolved_symbol,
            resolved_name=resolved_name,
            market=market,
            confidence=confidence,
            evidence_span_id=evidence_span_id,
            aliases=aliases or [],
        )

    @classmethod
    def create_crypto(
        cls,
        raw_text: str,
        resolved_symbol: str,
        resolved_name: Optional[str] = None,
        confidence: float = 1.0,
        evidence_span_id: Optional[str] = None,
        aliases: Optional[list[str]] = None,
    ) -> EntityAnchor:
        """
        Create a cryptocurrency entity anchor.

        Args:
            raw_text: Original text mentioning the crypto.
            resolved_symbol: Symbol (e.g., 'BTC').
            resolved_name: Full name (e.g., 'Bitcoin').
            confidence: Confidence score.
            evidence_span_id: Evidence span link.
            aliases: Alternative names.

        Returns:
            EntityAnchor with crypto type.
        """
        return cls(
            entity_type="crypto",
            raw_text=raw_text,
            resolved_symbol=resolved_symbol,
            resolved_name=resolved_name,
            market="CRYPTO",
            confidence=confidence,
            evidence_span_id=evidence_span_id,
            aliases=aliases or [],
        )

    @classmethod
    def create_unresolved(
        cls,
        raw_text: str,
        entity_type: ENTITY_TYPE_LITERAL,
        confidence: float = 0.5,
        evidence_span_id: Optional[str] = None,
    ) -> EntityAnchor:
        """
        Create an unresolved entity anchor (symbol/name unknown).

        Args:
            raw_text: Original text mentioning the entity.
            entity_type: Best guess for entity type.
            confidence: Confidence score (typically low).
            evidence_span_id: Evidence span link.

        Returns:
            EntityAnchor without resolution.
        """
        return cls(
            entity_type=entity_type,
            raw_text=raw_text,
            resolved_name=None,
            resolved_symbol=None,
            market=None,
            confidence=confidence,
            evidence_span_id=evidence_span_id,
        )

    def is_resolved(self) -> bool:
        """
        Check if the entity has been resolved to a symbol.

        Returns:
            True if resolved_symbol is not None.
        """
        return self.resolved_symbol is not None

    def get_display_name(self) -> str:
        """
        Get the best display name for this entity.

        Returns:
            Resolved name, or symbol, or raw text.
        """
        if self.resolved_name:
            return self.resolved_name
        if self.resolved_symbol:
            return self.resolved_symbol
        return self.raw_text

    def get_full_identifier(self) -> Optional[str]:
        """
        Get full identifier with market prefix.

        Returns:
            Market-prefixed symbol (e.g., 'US:AAPL') or None.
        """
        if not self.resolved_symbol:
            return None
        if self.market:
            return f"{self.market}:{self.resolved_symbol}"
        return self.resolved_symbol

    def has_high_confidence(self, threshold: float = 0.8) -> bool:
        """
        Check if resolution confidence is high.

        Args:
            threshold: Confidence threshold.

        Returns:
            True if confidence >= threshold.
        """
        return self.confidence >= threshold