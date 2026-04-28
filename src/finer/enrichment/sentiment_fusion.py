"""Sentiment Fusion Enricher — Multi-source sentiment aggregation.

Integrates finance-skills sentiment analysis to enhance Trade Action
direction judgment with cross-source sentiment data.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

from finer.schemas.event import EventWithActions
from finer.schemas.enriched_event import (
    SentimentSnapshot,
    EnrichedEventWithActions,
)
from finer.services.finance_skills_client import (
    FinanceSkillsClient,
    SkillName,
    get_finance_skills_client,
)

logger = logging.getLogger(__name__)


# Default source weights for sentiment aggregation
DEFAULT_SOURCE_WEIGHTS = {
    "reddit": 0.25,
    "twitter": 0.25,
    "news": 0.35,
    "polymarket": 0.15,
}

# Thresholds for contrarian signal detection
CONTRARIAN_SENTIMENT_THRESHOLD = 0.7
CONTRARIAN_VELOCITY_THRESHOLD = 0.3


@dataclass
class DirectionAdjustment:
    """Result of direction adjustment calculation."""
    original_direction: str
    adjusted_direction: str
    confidence_modifier: float
    reason: str
    contrarian_opportunity: bool = False


@dataclass
class SentimentFusionStats:
    """Statistics for sentiment fusion run."""
    total_events: int = 0
    enriched_events: int = 0
    failed_enrichments: int = 0
    contrarian_signals: int = 0
    extreme_sentiments: int = 0
    partial_data: int = 0


class SentimentFusionEnricher:
    """Enrich events with multi-source sentiment data.

    Fetches sentiment from Reddit, Twitter, News, and Polymarket,
    aggregates them with configurable weights, and detects contrarian signals.

    Example:
        enricher = SentimentFusionEnricher()
        sentiment = await enricher.fetch_sentiment("AAPL")
        adjustment = enricher.calculate_direction_adjustment("bullish", sentiment)
    """

    def __init__(
        self,
        client: Optional[FinanceSkillsClient] = None,
        source_weights: Optional[Dict[str, float]] = None,
        contrarian_threshold: float = CONTRARIAN_SENTIMENT_THRESHOLD,
        velocity_threshold: float = CONTRARIAN_VELOCITY_THRESHOLD,
    ):
        self.client = client or get_finance_skills_client()
        self.source_weights = source_weights or DEFAULT_SOURCE_WEIGHTS
        self.contrarian_threshold = contrarian_threshold
        self.velocity_threshold = velocity_threshold

    async def fetch_sentiment(
        self,
        ticker: str,
        lookback_hours: int = 72,
    ) -> SentimentSnapshot:
        """Fetch multi-source sentiment for a ticker.

        Args:
            ticker: Stock ticker symbol
            lookback_hours: Hours to look back for sentiment data

        Returns:
            SentimentSnapshot with aggregated sentiment data
        """
        snapshot = SentimentSnapshot(ticker=ticker)
        snapshot.source_weights = self.source_weights.copy()

        # Call sentiment analysis skill
        try:
            sentiment_data = await self.client.call(
                SkillName.SENTIMENT_ANALYSIS,
                ticker=ticker,
                lookback_hours=lookback_hours,
            )

            if not sentiment_data:
                snapshot.data_quality = "unavailable"
                logger.warning(f"No sentiment data available for {ticker}")
                return snapshot

            # Parse individual source sentiments
            if "reddit" in sentiment_data:
                snapshot.reddit_sentiment = self._normalize_score(
                    sentiment_data["reddit"].get("score")
                )
                snapshot.sources.append("reddit")
                snapshot.social_mentions += sentiment_data["reddit"].get("mentions", 0)

            if "twitter" in sentiment_data:
                snapshot.twitter_sentiment = self._normalize_score(
                    sentiment_data["twitter"].get("score")
                )
                snapshot.sources.append("twitter")
                snapshot.social_mentions += sentiment_data["twitter"].get("mentions", 0)

            if "news" in sentiment_data:
                snapshot.news_sentiment = self._normalize_score(
                    sentiment_data["news"].get("score")
                )
                snapshot.sources.append("news")
                snapshot.news_count = sentiment_data["news"].get("count", 0)

            if "polymarket" in sentiment_data:
                # Polymarket gives probability (0-1), convert to -1 to 1
                prob = sentiment_data["polymarket"].get("probability")
                if prob is not None:
                    snapshot.polymarket_probability = prob
                    snapshot.sources.append("polymarket")

            # Get velocity if available
            snapshot.sentiment_velocity = sentiment_data.get("velocity", 0.0)

            # Aggregate sentiment
            snapshot.aggregated_score = self._aggregate_sentiment(snapshot)

            # Classify overall sentiment
            snapshot.overall_sentiment = self._classify_sentiment(snapshot.aggregated_score)

            # Detect extreme sentiment
            snapshot.extreme_sentiment = abs(snapshot.aggregated_score) > self.contrarian_threshold

            # Detect contrarian signal
            snapshot.contrarian_signal = self._detect_contrarian(
                snapshot.aggregated_score,
                snapshot.sentiment_velocity
            )

            # Set data quality
            if len(snapshot.sources) >= 3:
                snapshot.data_quality = "complete"
            elif len(snapshot.sources) > 0:
                snapshot.data_quality = "partial"
            else:
                snapshot.data_quality = "unavailable"

            logger.debug(
                f"Sentiment for {ticker}: score={snapshot.aggregated_score:.2f}, "
                f"sources={snapshot.sources}, quality={snapshot.data_quality}"
            )

        except Exception as e:
            logger.error(f"Failed to fetch sentiment for {ticker}: {e}")
            snapshot.data_quality = "unavailable"

        return snapshot

    def _normalize_score(self, score: Optional[float]) -> Optional[float]:
        """Normalize score to -1 to 1 range."""
        if score is None:
            return None
        # Assume input is 0-1, convert to -1 to 1
        if 0 <= score <= 1:
            return (score - 0.5) * 2
        # Already in -1 to 1 range
        return max(-1.0, min(1.0, score))

    def _aggregate_sentiment(self, snapshot: SentimentSnapshot) -> float:
        """Calculate weighted aggregated sentiment score."""
        total = 0.0
        total_weight = 0.0

        source_scores = {
            "reddit": snapshot.reddit_sentiment,
            "twitter": snapshot.twitter_sentiment,
            "news": snapshot.news_sentiment,
        }

        for source, score in source_scores.items():
            if score is not None:
                weight = self.source_weights.get(source, 0.25)
                total += score * weight
                total_weight += weight

        # Add polymarket (probability, not sentiment score)
        if snapshot.polymarket_probability is not None:
            # Convert probability to sentiment-like score
            pm_score = (snapshot.polymarket_probability - 0.5) * 2
            weight = self.source_weights.get("polymarket", 0.15)
            total += pm_score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return total / total_weight

    def _classify_sentiment(self, score: float) -> str:
        """Classify sentiment score into category."""
        if score > 0.15:
            return "bullish"
        elif score < -0.15:
            return "bearish"
        else:
            return "neutral"

    def _detect_contrarian(self, sentiment: float, velocity: float) -> bool:
        """Detect contrarian signal (extreme sentiment + rapid change)."""
        # Extreme optimism + rapid rise = potential top
        if sentiment > self.contrarian_threshold and velocity > self.velocity_threshold:
            return True
        # Extreme pessimism + rapid fall = potential bottom
        if sentiment < -self.contrarian_threshold and velocity < -self.velocity_threshold:
            return True
        return False

    def calculate_direction_adjustment(
        self,
        llm_direction: str,
        sentiment: SentimentSnapshot,
    ) -> DirectionAdjustment:
        """Calculate direction adjustment based on sentiment.

        Args:
            llm_direction: Direction extracted by LLM
            sentiment: Sentiment snapshot

        Returns:
            DirectionAdjustment with adjustment recommendations
        """
        adjustment = DirectionAdjustment(
            original_direction=llm_direction,
            adjusted_direction=llm_direction,
            confidence_modifier=0.0,
            reason="",
            contrarian_opportunity=sentiment.contrarian_signal,
        )

        if sentiment.data_quality == "unavailable":
            adjustment.reason = "No sentiment data available"
            return adjustment

        score = sentiment.aggregated_score

        # Direction-sentiment alignment check
        if llm_direction == "bullish":
            if sentiment.extreme_sentiment and score > self.contrarian_threshold:
                # Bullish view + extreme optimism = reduce confidence
                adjustment.confidence_modifier = -0.2
                adjustment.reason = f"Bullish view conflicts with extreme optimism ({score:.2f})"
            elif score < -self.contrarian_threshold:
                # Bullish view + extreme pessimism = contrarian opportunity
                adjustment.confidence_modifier = 0.1
                adjustment.reason = f"Bullish view against extreme pessimism - contrarian opportunity ({score:.2f})"
            elif score < -0.3:
                # Bullish view + negative sentiment = slight concern
                adjustment.confidence_modifier = -0.1
                adjustment.reason = f"Bullish view diverges from negative sentiment ({score:.2f})"

        elif llm_direction == "bearish":
            if sentiment.extreme_sentiment and score < -self.contrarian_threshold:
                # Bearish view + extreme pessimism = reduce confidence
                adjustment.confidence_modifier = -0.2
                adjustment.reason = f"Bearish view conflicts with extreme pessimism ({score:.2f})"
            elif score > self.contrarian_threshold:
                # Bearish view + extreme optimism = contrarian opportunity
                adjustment.confidence_modifier = 0.1
                adjustment.reason = f"Bearish view against extreme optimism - contrarian opportunity ({score:.2f})"
            elif score > 0.3:
                # Bearish view + positive sentiment = slight concern
                adjustment.confidence_modifier = -0.1
                adjustment.reason = f"Bearish view diverges from positive sentiment ({score:.2f})"

        elif llm_direction == "neutral":
            if sentiment.extreme_sentiment:
                adjustment.reason = f"Neutral view but extreme sentiment detected ({score:.2f}) - consider manual review"

        return adjustment

    async def enrich_event(
        self,
        event: EventWithActions,
    ) -> Tuple[EnrichedEventWithActions, List[str]]:
        """Enrich a single event with sentiment data.

        Args:
            event: Event to enrich

        Returns:
            Tuple of (enriched event, list of issues)
        """
        issues: List[str] = []

        # Fetch sentiment
        sentiment_snapshot = await self.fetch_sentiment(event.ticker)

        if sentiment_snapshot.data_quality == "unavailable":
            issues.append(f"Could not fetch sentiment data for {event.ticker}")

        # Calculate direction adjustment
        adjustment = self.calculate_direction_adjustment(
            event.direction,
            sentiment_snapshot
        )

        # Build enriched event
        enriched = EnrichedEventWithActions.from_event(event)
        enriched.sentiment_snapshot = sentiment_snapshot

        # Apply confidence adjustment
        if enriched.market_snapshot:
            # Combine with existing market confidence
            base = enriched.overall_confidence
            sentiment_adj = adjustment.confidence_modifier
            enriched.overall_confidence = max(0.0, min(1.0, base + sentiment_adj * 0.3))
        else:
            # Only sentiment adjustment
            base = max((a.confidence for a in event.action_chain), default=1.0)
            enriched.overall_confidence = max(0.0, min(1.0, base + adjustment.confidence_modifier))

        # Add to validation issues if significant
        if adjustment.reason and abs(adjustment.confidence_modifier) >= 0.1:
            issues.append(adjustment.reason)

        # Mark for review if contrarian signal
        if sentiment_snapshot.contrarian_signal:
            enriched.requires_manual_review = True
            issues.append(f"Contrarian signal detected for {event.ticker}")

        return enriched, issues

    async def enrich_events(
        self,
        events: List[EventWithActions],
        parallel: bool = True,
    ) -> Tuple[List[EnrichedEventWithActions], SentimentFusionStats]:
        """Enrich multiple events with sentiment data.

        Args:
            events: List of events to enrich
            parallel: Whether to fetch data in parallel

        Returns:
            Tuple of (enriched events, stats)
        """
        stats = SentimentFusionStats(total_events=len(events))

        if not events:
            return [], stats

        if parallel:
            results = await asyncio.gather(
                *[self.enrich_event(event) for event in events],
                return_exceptions=True
            )

            enriched_events = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to enrich event {i}: {result}")
                    stats.failed_enrichments += 1
                    enriched = EnrichedEventWithActions.from_event(events[i])
                    enriched.validation_issues.append(f"Sentiment enrichment failed: {result}")
                    enriched_events.append(enriched)
                else:
                    enriched, issues = result
                    enriched_events.append(enriched)
                    stats.enriched_events += 1

                    if enriched.sentiment_snapshot:
                        if enriched.sentiment_snapshot.contrarian_signal:
                            stats.contrarian_signals += 1
                        if enriched.sentiment_snapshot.extreme_sentiment:
                            stats.extreme_sentiments += 1
                        if enriched.sentiment_snapshot.data_quality == "partial":
                            stats.partial_data += 1
        else:
            enriched_events = []
            for event in events:
                try:
                    enriched, issues = await self.enrich_event(event)
                    enriched_events.append(enriched)
                    stats.enriched_events += 1

                    if enriched.sentiment_snapshot:
                        if enriched.sentiment_snapshot.contrarian_signal:
                            stats.contrarian_signals += 1
                        if enriched.sentiment_snapshot.extreme_sentiment:
                            stats.extreme_sentiments += 1
                        if enriched.sentiment_snapshot.data_quality == "partial":
                            stats.partial_data += 1

                except Exception as e:
                    logger.error(f"Failed to enrich event: {e}")
                    stats.failed_enrichments += 1
                    enriched = EnrichedEventWithActions.from_event(event)
                    enriched.validation_issues.append(f"Sentiment enrichment failed: {e}")
                    enriched_events.append(enriched)

        return enriched_events, stats


# Global enricher instance
_sentiment_enricher: Optional[SentimentFusionEnricher] = None


def get_sentiment_enricher() -> SentimentFusionEnricher:
    """Get or create the global sentiment enricher."""
    global _sentiment_enricher
    if _sentiment_enricher is None:
        _sentiment_enricher = SentimentFusionEnricher()
    return _sentiment_enricher
