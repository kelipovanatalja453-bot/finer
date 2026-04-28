"""Enriched Event Schemas — Extended event models with market data.

Extends EventWithActions with market snapshots, sentiment data,
validation results and confidence scores.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict

from finer.schemas.event import EventWithActions, TradingAction


class MarketDataSnapshot(BaseModel):
    """Market data snapshot for a ticker."""
    model_config = ConfigDict(strict=True)

    ticker: str = Field(..., description="Ticker symbol")
    current_price: Optional[float] = Field(None, description="Current price")
    change_pct: Optional[float] = Field(None, description="Percentage change")
    volume: Optional[int] = Field(None, description="Trading volume")

    # 52-week range
    high_52wk: Optional[float] = Field(None, description="52-week high")
    low_52wk: Optional[float] = Field(None, description="52-week low")

    # Valuation metrics
    pe_ratio: Optional[float] = Field(None, description="P/E ratio")
    market_cap: Optional[float] = Field(None, description="Market capitalization")

    # Options data
    avg_iv: Optional[float] = Field(None, description="Average implied volatility")
    options_volume: Optional[int] = Field(None, description="Total options volume")

    # Metadata
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When this data was fetched"
    )
    source: str = Field("finance-skills", description="Data source")

    # Data quality indicator
    is_complete: bool = Field(True, description="Whether all fields are populated")
    missing_fields: List[str] = Field(
        default_factory=list,
        description="Fields that could not be fetched"
    )


class SentimentSnapshot(BaseModel):
    """Sentiment analysis snapshot with multi-source fusion."""
    model_config = ConfigDict(strict=True)

    ticker: str = Field(..., description="Ticker symbol")

    # Multi-source sentiment scores (-1 to 1 scale)
    reddit_sentiment: Optional[float] = Field(
        None, ge=-1.0, le=1.0,
        description="Reddit sentiment score"
    )
    twitter_sentiment: Optional[float] = Field(
        None, ge=-1.0, le=1.0,
        description="Twitter/X sentiment score"
    )
    news_sentiment: Optional[float] = Field(
        None, ge=-1.0, le=1.0,
        description="News sentiment score"
    )
    polymarket_probability: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Polymarket prediction probability"
    )

    # Aggregated metrics
    aggregated_score: float = Field(
        0.0, ge=-1.0, le=1.0,
        description="Weighted aggregated sentiment score"
    )
    sentiment_velocity: float = Field(
        0.0, ge=-1.0, le=1.0,
        description="Rate of sentiment change"
    )

    # Signal flags
    contrarian_signal: bool = Field(
        False,
        description="Whether contrarian signal detected (extreme + rapid change)"
    )
    extreme_sentiment: bool = Field(
        False,
        description="Whether sentiment is at extreme level"
    )

    # Overall classification
    overall_sentiment: Literal["bullish", "bearish", "neutral"] = Field(
        "neutral", description="Overall sentiment classification"
    )

    # Metadata
    sources: List[str] = Field(
        default_factory=list,
        description="Data sources that contributed"
    )
    source_weights: dict = Field(
        default_factory=lambda: {"reddit": 0.25, "twitter": 0.25, "news": 0.35, "polymarket": 0.15},
        description="Weights used for aggregation"
    )
    data_quality: Literal["complete", "partial", "unavailable"] = Field(
        "complete",
        description="Data completeness status"
    )

    # Counts
    news_count: int = Field(0, description="Number of news items analyzed")
    social_mentions: int = Field(0, description="Number of social mentions")

    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = Field("finance-skills", description="Data source service")


class StrategyAssessment(BaseModel):
    """Strategy assessment and validation (placeholder for P2)."""
    model_config = ConfigDict(strict=True)

    # Risk metrics
    risk_level: Literal["low", "medium", "high", "very_high"] = Field(
        "medium", description="Overall risk level"
    )

    # Position sizing suggestion
    suggested_position_pct: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Suggested position size as % of portfolio"
    )

    # Stop loss / take profit suggestions
    suggested_stop_loss: Optional[float] = Field(
        None, description="Suggested stop loss price"
    )
    suggested_take_profit: Optional[float] = Field(
        None, description="Suggested take profit price"
    )

    # Risk-reward ratio
    risk_reward_ratio: Optional[float] = Field(
        None, description="Risk/reward ratio"
    )

    # Reasoning
    rationale: Optional[str] = Field(None, description="Assessment rationale")

    timestamp: datetime = Field(default_factory=datetime.now)


class PriceValidation(BaseModel):
    """Result of price range validation."""
    model_config = ConfigDict(strict=True)

    is_valid: bool = Field(True, description="Whether the price is valid")
    issues: List[str] = Field(default_factory=list, description="Validation issues")
    warnings: List[str] = Field(default_factory=list, description="Warnings (not blocking)")

    # Price context
    price_position: Optional[str] = Field(
        None, description="Position relative to 52-week range (e.g., 'near_52wk_low')"
    )
    distance_from_52wk_high: Optional[float] = Field(
        None, description="Distance from 52-week high as %"
    )
    distance_from_52wk_low: Optional[float] = Field(
        None, description="Distance from 52-week low as %"
    )


class EnrichedEventWithActions(BaseModel):
    """Extended event with market data and validation."""
    model_config = ConfigDict(strict=True)

    # Base event data
    event_id: Optional[str] = Field(None)
    content_id: Optional[str] = Field(None)
    ticker: str = Field(..., description="Ticker symbol")
    direction: Literal["bullish", "bearish", "neutral", "watchlist", "risk_warning"]
    evidence_text: str = Field(..., description="Original text evidence")
    rationale: Optional[str] = None
    action_chain: List[TradingAction] = Field(default_factory=list)
    time_horizon: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

    # Enriched fields
    market_snapshot: Optional[MarketDataSnapshot] = Field(
        None, description="Market data snapshot"
    )
    sentiment_snapshot: Optional[SentimentSnapshot] = Field(
        None, description="Sentiment data (P1)"
    )
    strategy_assessment: Optional[StrategyAssessment] = Field(
        None, description="Strategy assessment (P2)"
    )

    # Validation results
    price_validations: List[PriceValidation] = Field(
        default_factory=list,
        description="Price validation results for each action"
    )

    # Confidence scoring
    base_confidence: float = Field(
        1.0, ge=0.0, le=1.0,
        description="Original extraction confidence"
    )
    market_data_confidence: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Confidence boost from market data validation"
    )
    overall_confidence: float = Field(
        1.0, ge=0.0, le=1.0,
        description="Combined confidence score"
    )

    # Review flags
    validation_issues: List[str] = Field(
        default_factory=list,
        description="Critical validation issues"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-critical warnings"
    )
    requires_manual_review: bool = Field(
        False,
        description="Whether this event needs manual review"
    )

    # Enrichment metadata
    enrichment_timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When enrichment was performed"
    )
    enrichment_version: str = Field("p0", description="Enrichment version/phase")

    @classmethod
    def from_event(
        cls,
        event: EventWithActions,
        market_snapshot: Optional[MarketDataSnapshot] = None,
        validation_issues: Optional[List[str]] = None,
    ) -> EnrichedEventWithActions:
        """Create enriched event from base event."""
        return cls(
            event_id=event.event_id,
            content_id=event.content_id,
            ticker=event.ticker,
            direction=event.direction,
            evidence_text=event.evidence_text,
            rationale=event.rationale,
            action_chain=event.action_chain,
            time_horizon=event.time_horizon,
            metadata=event.metadata,
            market_snapshot=market_snapshot,
            validation_issues=validation_issues or [],
        )


class EnrichedExtractionResult(BaseModel):
    """Container for enriched events."""
    events: List[EnrichedEventWithActions]
    enrichment_stats: dict = Field(default_factory=dict)
