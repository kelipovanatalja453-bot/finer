"""Enriched Action Extractor — Extract events with market data enrichment.

Extends ActionExtractor with market data enrichment capabilities.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Tuple

from finer.extraction.extractor import ActionExtractor
from finer.schemas.event import EventWithActions, ExtractionResult
from finer.schemas.enriched_event import (
    EnrichedEventWithActions,
    EnrichedExtractionResult,
)
from finer.enrichment.market_context import (
    MarketContextEnricher,
    EnrichmentStats,
    get_market_enricher,
)

logger = logging.getLogger(__name__)


class EnrichedActionExtractor(ActionExtractor):
    """Enhanced extractor with market data enrichment.

    Inherits from ActionExtractor and adds enrich_event() method
    for fetching market data and validating price targets.

    Example usage:
        extractor = EnrichedActionExtractor()
        enriched_events = await extractor.extract_and_enrich(text)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        enricher: Optional[MarketContextEnricher] = None,
        enable_enrichment: bool = True,
    ):
        super().__init__(api_key=api_key, model=model)
        self.enricher = enricher or get_market_enricher()
        self.enable_enrichment = enable_enrichment

    async def enrich_events(
        self,
        events: List[EventWithActions],
        parallel: bool = True,
    ) -> Tuple[List[EnrichedEventWithActions], EnrichmentStats]:
        """Enrich events with market data.

        Args:
            events: List of events to enrich
            parallel: Whether to fetch data in parallel

        Returns:
            Tuple of (enriched events, enrichment stats)
        """
        if not self.enable_enrichment:
            # Return basic enriched events without market data
            enriched = [
                EnrichedEventWithActions.from_event(event)
                for event in events
            ]
            stats = EnrichmentStats(
                total_events=len(events),
                enriched_events=len(events),
            )
            return enriched, stats

        return await self.enricher.enrich_events(events, parallel=parallel)

    async def extract_and_enrich(
        self,
        text: str,
        context: Optional[str] = None,
        parallel_enrichment: bool = True,
    ) -> EnrichedExtractionResult:
        """Extract events from text and enrich with market data.

        This is the main entry point for enriched extraction.

        Args:
            text: Text to analyze
            context: Optional additional context
            parallel_enrichment: Whether to fetch market data in parallel

        Returns:
            EnrichedExtractionResult with enriched events and stats
        """
        # Step 1: Extract base events using parent class
        logger.info("Extracting events from text...")
        events = self.extract_events(text, context=context)

        if not events:
            logger.info("No events extracted")
            return EnrichedExtractionResult(
                events=[],
                enrichment_stats={"total_events": 0}
            )

        logger.info(f"Extracted {len(events)} events")

        # Step 2: Enrich with market data
        logger.info("Enriching events with market data...")
        enriched_events, stats = await self.enrich_events(
            events,
            parallel=parallel_enrichment
        )

        # Build stats dict
        stats_dict = {
            "total_events": stats.total_events,
            "enriched_events": stats.enriched_events,
            "failed_enrichments": stats.failed_enrichments,
            "validation_issues": stats.validation_issues,
            "requires_review": stats.requires_review,
        }

        logger.info(
            f"Enrichment complete: {stats.enriched_events}/{stats.total_events} events, "
            f"{stats.validation_issues} issues, {stats.requires_review} require review"
        )

        return EnrichedExtractionResult(
            events=enriched_events,
            enrichment_stats=stats_dict,
        )

    def extract_events(
        self,
        text: str,
        context: Optional[str] = None
    ) -> List[EventWithActions]:
        """Extract events (sync wrapper for compatibility).

        This calls the parent ActionExtractor.extract_events().
        """
        return super().extract_events(text, context=context)

    async def extract_and_enrich_single(
        self,
        text: str,
        context: Optional[str] = None,
    ) -> Optional[EnrichedEventWithActions]:
        """Extract and enrich a single event.

        Convenience method for single-event extraction.

        Returns:
            The most confident enriched event, or None if no events found
        """
        result = await self.extract_and_enrich(text, context)

        if not result.events:
            return None

        # Return the event with highest confidence
        return max(result.events, key=lambda e: e.overall_confidence)


# Convenience function for quick usage
async def extract_enriched(
    text: str,
    context: Optional[str] = None,
    api_key: Optional[str] = None,
) -> EnrichedExtractionResult:
    """Convenience function for enriched extraction.

    Example:
        result = await extract_enriched("AAPL at 180 is a good entry")
        for event in result.events:
            print(f"{event.ticker}: {event.overall_confidence}")
    """
    extractor = EnrichedActionExtractor(api_key=api_key)
    return await extractor.extract_and_enrich(text, context)
