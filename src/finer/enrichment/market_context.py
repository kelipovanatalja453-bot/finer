"""Market Context Enricher — Enrich events with market data.

Uses finance-skills to fetch market data (yfinance-data, funda-data)
and validate price targets.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from finer.schemas.event import EventWithActions, TradingAction
from finer.schemas.enriched_event import (
    MarketDataSnapshot,
    SentimentSnapshot,
    StrategyAssessment,
    PriceValidation,
    EnrichedEventWithActions,
)
from finer.services.finance_skills_client import (
    FinanceSkillsClient,
    SkillName,
    get_finance_skills_client,
)
from finer.enrichment.sentiment_fusion import (
    SentimentFusionEnricher,
    SentimentFusionStats,
    get_sentiment_enricher,
)

logger = logging.getLogger(__name__)


class PriceRangeValidator:
    """Validate target prices against market data."""

    def validate(
        self,
        action: TradingAction,
        market_data: Optional[MarketDataSnapshot]
    ) -> PriceValidation:
        """Validate price targets in an action.

        Checks:
        1. Target prices within reasonable range of current price
        2. Target prices not outside 52-week range
        3. Stop-loss logic for long/short positions
        """
        validation = PriceValidation()

        if not market_data:
            validation.warnings.append("No market data available for validation")
            return validation

        current_price = market_data.current_price
        if not current_price:
            validation.warnings.append("Current price unavailable")
            return validation

        # Check target prices
        target_low = action.target_price_low
        target_high = action.target_price_high

        # Calculate price position relative to 52-week range
        if market_data.high_52wk and market_data.low_52wk:
            range_size = market_data.high_52wk - market_data.low_52wk
            if range_size > 0:
                position = (current_price - market_data.low_52wk) / range_size
                validation.distance_from_52wk_low = position * 100
                validation.distance_from_52wk_high = (1 - position) * 100

                if position < 0.1:
                    validation.price_position = "near_52wk_low"
                elif position > 0.9:
                    validation.price_position = "near_52wk_high"
                else:
                    validation.price_position = "in_range"

        # Validate target prices
        if target_low and target_high:
            if target_low >= target_high:
                validation.issues.append(
                    f"Invalid price range: low ({target_low}) >= high ({target_high})"
                )
                validation.is_valid = False

        # Action-specific validation
        if action.action_type in ("long", "buy_call"):
            # For long positions, target should be above current
            if target_low and target_low <= current_price:
                # Could be a support level entry, warn but don't fail
                validation.warnings.append(
                    f"Target low ({target_low}) <= current ({current_price:.2f}), "
                    "verify if this is an entry price"
                )

            # Stop loss should be below current for long
            # (This would be in a different field, just noting for P2)

        elif action.action_type in ("short", "buy_put"):
            # For short/put, target should be below current
            if target_high and target_high >= current_price:
                validation.warnings.append(
                    f"Target high ({target_high}) >= current ({current_price:.2f}), "
                    "verify if this makes sense for short position"
                )

        # Check if targets are way outside 52-week range
        if target_high and market_data.high_52wk:
            if target_high > market_data.high_52wk * 1.5:
                validation.issues.append(
                    f"Target high ({target_high}) > 150% of 52-week high ({market_data.high_52wk:.2f})"
                )
                validation.is_valid = False

        if target_low and market_data.low_52wk:
            if target_low < market_data.low_52wk * 0.5:
                validation.issues.append(
                    f"Target low ({target_low}) < 50% of 52-week low ({market_data.low_52wk:.2f})"
                )
                validation.is_valid = False

        return validation


@dataclass
class EnrichmentStats:
    """Statistics for enrichment run."""
    total_events: int = 0
    enriched_events: int = 0
    failed_enrichments: int = 0
    validation_issues: int = 0
    requires_review: int = 0
    cache_hits: int = 0
    api_calls: int = 0


class MarketContextEnricher:
    """Enrich events with market data from finance-skills.

    Fetches:
    - Current price, volume, change
    - 52-week high/low
    - PE ratio, market cap
    - Implied volatility (from options flow)

    Validates price targets against market data.

    P1: Also enriches with multi-source sentiment data.
    """

    def __init__(
        self,
        client: Optional[FinanceSkillsClient] = None,
        enable_validation: bool = True,
        enable_sentiment: bool = True,
        sentiment_enricher: Optional[SentimentFusionEnricher] = None,
    ):
        self.client = client or get_finance_skills_client()
        self.validator = PriceRangeValidator()
        self.enable_validation = enable_validation
        self.enable_sentiment = enable_sentiment
        self.sentiment_enricher = sentiment_enricher or get_sentiment_enricher()

    async def fetch_market_data(
        self,
        ticker: str
    ) -> Optional[MarketDataSnapshot]:
        """Fetch market data for a ticker.

        Makes parallel calls to yfinance-data and funda-data.
        """
        # Fetch market data and fundamentals in parallel
        results = await self.client.call_batch([
            (SkillName.YFINANCE_DATA, {"ticker": ticker}),
            (SkillName.FUNDA_DATA, {"ticker": ticker}),
        ])

        market_data_raw = results[0]
        funda_data_raw = results[1]

        if not market_data_raw and not funda_data_raw:
            logger.warning(f"No market data available for {ticker}")
            return None

        # Build snapshot from available data
        snapshot = MarketDataSnapshot(ticker=ticker)

        # Parse yfinance-data
        if market_data_raw:
            snapshot.current_price = market_data_raw.get("current_price")
            snapshot.change_pct = market_data_raw.get("change_pct")
            snapshot.volume = market_data_raw.get("volume")
            snapshot.high_52wk = market_data_raw.get("52wk_high")
            snapshot.low_52wk = market_data_raw.get("52wk_low")
            snapshot.pe_ratio = market_data_raw.get("pe_ratio")
            snapshot.market_cap = market_data_raw.get("market_cap")

        # Parse funda-data (may override or add data)
        if funda_data_raw:
            fundamentals = funda_data_raw.get("fundamentals", {})
            options_flow = funda_data_raw.get("options_flow", {})

            # Fill in missing from fundamentals
            if not snapshot.pe_ratio:
                snapshot.pe_ratio = fundamentals.get("pe_ratio")
            if not snapshot.market_cap:
                snapshot.market_cap = fundamentals.get("market_cap")

            # Add options data
            snapshot.avg_iv = options_flow.get("avg_iv")
            snapshot.options_volume = options_flow.get("total_volume")

        # Check completeness
        required_fields = [
            "current_price", "high_52wk", "low_52wk"
        ]
        for field in required_fields:
            if getattr(snapshot, field) is None:
                snapshot.missing_fields.append(field)
                snapshot.is_complete = False

        return snapshot

    async def enrich_event(
        self,
        event: EventWithActions,
    ) -> Tuple[EnrichedEventWithActions, List[str]]:
        """Enrich a single event with market data and sentiment.

        Returns:
            Tuple of (enriched event, list of issues)
        """
        issues: List[str] = []
        warnings: List[str] = []

        # Fetch market data and sentiment in parallel
        if self.enable_sentiment:
            market_snapshot, sentiment_snapshot = await asyncio.gather(
                self.fetch_market_data(event.ticker),
                self.sentiment_enricher.fetch_sentiment(event.ticker),
            )
        else:
            market_snapshot = await self.fetch_market_data(event.ticker)
            sentiment_snapshot = None

        if not market_snapshot:
            issues.append(f"Could not fetch market data for {event.ticker}")
        elif not market_snapshot.is_complete:
            warnings.append(
                f"Incomplete market data for {event.ticker}: "
                f"missing {market_snapshot.missing_fields}"
            )

        # Check sentiment data quality
        if sentiment_snapshot and sentiment_snapshot.data_quality == "unavailable":
            warnings.append(f"Sentiment data unavailable for {event.ticker}")

        # Validate price targets
        price_validations = []
        if market_snapshot and self.enable_validation:
            for action in event.action_chain:
                validation = self.validator.validate(action, market_snapshot)
                price_validations.append(validation)

                if validation.issues:
                    issues.extend(validation.issues)
                if validation.warnings:
                    warnings.extend(validation.warnings)

        # Calculate confidence
        base_confidence = max(
            (a.confidence for a in event.action_chain),
            default=1.0
        )

        # Market data confidence boost
        market_confidence = 0.0
        if market_snapshot:
            # Base boost for having data
            market_confidence = 0.2
            # Extra boost for complete data
            if market_snapshot.is_complete:
                market_confidence = 0.3
            # Reduce if there are validation issues
            if issues:
                market_confidence *= 0.5

        # Sentiment confidence adjustment
        sentiment_confidence = 0.0
        if sentiment_snapshot and self.enable_sentiment:
            # Base boost for having sentiment data
            if sentiment_snapshot.data_quality != "unavailable":
                sentiment_confidence = 0.15
                if sentiment_snapshot.data_quality == "complete":
                    sentiment_confidence = 0.2
                # Contrarian signal reduces confidence
                if sentiment_snapshot.contrarian_signal:
                    sentiment_confidence *= 0.5

        # Overall confidence (weighted combination)
        overall_confidence = min(
            1.0,
            base_confidence * 0.5 + market_confidence * 0.3 + sentiment_confidence * 0.2
        )

        # Determine if manual review needed
        requires_review = bool(issues) or (
            market_snapshot and not market_snapshot.is_complete
        )

        # Build enriched event
        enriched = EnrichedEventWithActions.from_event(
            event,
            market_snapshot=market_snapshot,
            validation_issues=issues,
        )
        enriched.sentiment_snapshot = sentiment_snapshot
        enriched.warnings = warnings
        enriched.base_confidence = base_confidence
        enriched.market_data_confidence = market_confidence
        if self.enable_sentiment:
            enriched.metadata["sentiment_confidence"] = sentiment_confidence
        enriched.overall_confidence = overall_confidence
        enriched.price_validations = price_validations
        enriched.requires_manual_review = requires_review

        return enriched, issues

    async def enrich_events(
        self,
        events: List[EventWithActions],
        parallel: bool = True,
    ) -> Tuple[List[EnrichedEventWithActions], EnrichmentStats]:
        """Enrich multiple events with market data.

        Args:
            events: List of events to enrich
            parallel: Whether to fetch data in parallel

        Returns:
            Tuple of (enriched events, stats)
        """
        stats = EnrichmentStats(total_events=len(events))

        if not events:
            return [], stats

        if parallel:
            # Enrich all events in parallel
            results = await asyncio.gather(
                *[self.enrich_event(event) for event in events],
                return_exceptions=True
            )

            enriched_events = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to enrich event {i}: {result}")
                    stats.failed_enrichments += 1
                    # Create basic enriched event without market data
                    enriched = EnrichedEventWithActions.from_event(events[i])
                    enriched.validation_issues = [f"Enrichment failed: {result}"]
                    enriched.requires_manual_review = True
                    enriched_events.append(enriched)
                else:
                    enriched, issues = result
                    enriched_events.append(enriched)
                    stats.enriched_events += 1
                    if issues:
                        stats.validation_issues += len(issues)
                    if enriched.requires_manual_review:
                        stats.requires_review += 1
        else:
            # Sequential enrichment
            enriched_events = []
            for event in events:
                try:
                    enriched, issues = await self.enrich_event(event)
                    enriched_events.append(enriched)
                    stats.enriched_events += 1
                    if issues:
                        stats.validation_issues += len(issues)
                    if enriched.requires_manual_review:
                        stats.requires_review += 1
                except Exception as e:
                    logger.error(f"Failed to enrich event: {e}")
                    stats.failed_enrichments += 1
                    enriched = EnrichedEventWithActions.from_event(event)
                    enriched.validation_issues = [f"Enrichment failed: {e}"]
                    enriched.requires_manual_review = True
                    enriched_events.append(enriched)

        return enriched_events, stats


# Global enricher instance
_enricher: Optional[MarketContextEnricher] = None


def get_market_enricher() -> MarketContextEnricher:
    """Get or create the global market enricher."""
    global _enricher
    if _enricher is None:
        _enricher = MarketContextEnricher()
    return _enricher
