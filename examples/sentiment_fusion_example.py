"""
P1 Sentiment Fusion Examples

This script demonstrates how to use the SentimentFusionEnricher
for multi-source sentiment aggregation.

Requirements:
- Set FINANCE_SKILLS_API_KEY environment variable
- Set DASHSCOPE_API_KEY for text extraction
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from finer.enrichment.sentiment_fusion import (
    SentimentFusionEnricher,
    DirectionAdjustment,
    get_sentiment_enricher,
)
from finer.enrichment.market_context import MarketContextEnricher
from finer.extraction.enriched_extractor import EnrichedActionExtractor
from finer.schemas.event import EventWithActions, TradingAction


async def example_basic_sentiment():
    """Example 1: Basic sentiment fetch."""
    print("\n=== Example 1: Basic Sentiment Fetch ===\n")

    enricher = SentimentFusionEnricher()

    # Check if API key is set
    if not os.getenv("FINANCE_SKILLS_API_KEY"):
        print("Warning: FINANCE_SKILLS_API_KEY not set. Using mock mode.")
        print("Set the environment variable to test with real data.")
        return

    # Fetch sentiment for a ticker
    print("Fetching sentiment for AAPL...")
    sentiment = await enricher.fetch_sentiment("AAPL")

    print(f"Ticker: {sentiment.ticker}")
    print(f"Aggregated Score: {sentiment.aggregated_score:.3f}")
    print(f"Overall Sentiment: {sentiment.overall_sentiment}")
    print(f"Sources: {sentiment.sources}")
    print(f"Data Quality: {sentiment.data_quality}")
    print(f"Extreme Sentiment: {sentiment.extreme_sentiment}")
    print(f"Contrarian Signal: {sentiment.contrarian_signal}")

    if sentiment.reddit_sentiment is not None:
        print(f"Reddit Sentiment: {sentiment.reddit_sentiment:.3f}")
    if sentiment.twitter_sentiment is not None:
        print(f"Twitter Sentiment: {sentiment.twitter_sentiment:.3f}")
    if sentiment.news_sentiment is not None:
        print(f"News Sentiment: {sentiment.news_sentiment:.3f}")


async def example_direction_adjustment():
    """Example 2: Direction adjustment calculation."""
    print("\n=== Example 2: Direction Adjustment ===\n")

    enricher = SentimentFusionEnricher()

    # Simulate different scenarios
    scenarios = [
        ("bullish", 0.8, 0.4),   # Bullish + extreme optimism
        ("bullish", -0.8, -0.4), # Bullish + extreme pessimism (contrarian)
        ("bearish", -0.8, -0.4), # Bearish + extreme pessimism
        ("bearish", 0.8, 0.4),   # Bearish + extreme optimism (contrarian)
        ("neutral", 0.75, 0.2),  # Neutral + extreme sentiment
    ]

    print("Scenario Analysis:")
    print("-" * 60)

    for direction, sentiment_score, velocity in scenarios:
        # Create mock sentiment snapshot
        from finer.schemas.enriched_event import SentimentSnapshot
        sentiment = SentimentSnapshot(
            ticker="TEST",
            aggregated_score=sentiment_score,
            sentiment_velocity=velocity,
            extreme_sentiment=abs(sentiment_score) > 0.7,
            contrarian_signal=(
                abs(sentiment_score) > 0.7 and abs(velocity) > 0.3
            ),
            data_quality="complete",
        )

        adjustment = enricher.calculate_direction_adjustment(direction, sentiment)

        print(f"\nLLM Direction: {direction}")
        print(f"Sentiment Score: {sentiment_score:.2f}")
        print(f"Velocity: {velocity:.2f}")
        print(f"Confidence Modifier: {adjustment.confidence_modifier:+.2f}")
        print(f"Reason: {adjustment.reason or 'No adjustment needed'}")
        print(f"Contrarian Opportunity: {adjustment.contrarian_opportunity}")


async def example_full_enrichment():
    """Example 3: Full event enrichment with sentiment."""
    print("\n=== Example 3: Full Event Enrichment ===\n")

    # Create a mock event
    event = EventWithActions(
        ticker="TSLA",
        direction="bullish",
        evidence_text="TSLA 在 200 附近有强支撑，突破 220 可看 250",
        action_chain=[
            TradingAction(
                action_type="long",
                trigger_condition="at 200",
                target_price_low=200,
                target_price_high=250,
                confidence=0.8,
            )
        ],
    )

    enricher = SentimentFusionEnricher()
    enriched, issues = await enricher.enrich_event(event)

    print(f"Ticker: {enriched.ticker}")
    print(f"Original Direction: {event.direction}")
    print(f"Overall Confidence: {enriched.overall_confidence:.2f}")

    if enriched.sentiment_snapshot:
        s = enriched.sentiment_snapshot
        print(f"\nSentiment Data:")
        print(f"  Aggregated Score: {s.aggregated_score:.3f}")
        print(f"  Overall: {s.overall_sentiment}")
        print(f"  Sources: {s.sources}")
        print(f"  Contrarian: {s.contrarian_signal}")

    if issues:
        print(f"\nIssues: {issues}")


async def example_integrated_extraction():
    """Example 4: Integrated extraction with market + sentiment."""
    print("\n=== Example 4: Integrated Extraction ===\n")

    if not os.getenv("DASHSCOPE_API_KEY"):
        print("Warning: DASHSCOPE_API_KEY not set. Skipping extraction example.")
        return

    extractor = EnrichedActionExtractor()

    text = """
    腾讯控股(0700.HK)近期在380港元附近震荡，技术面显示有企稳迹象。
    如果能突破400港元，下一目标位在420-450区间。
    建议在380附近分批建仓，跌破360止损。
    """

    print("Extracting and enriching events...")
    print(f"Text: {text[:100]}...\n")

    result = await extractor.extract_and_enrich(text)

    print(f"Total Events: {len(result.events)}")
    print(f"Stats: {result.enrichment_stats}")

    for event in result.events:
        print(f"\n--- Event: {event.ticker} ---")
        print(f"Direction: {event.direction}")
        print(f"Confidence: {event.overall_confidence:.2f}")

        if event.market_snapshot:
            print(f"Current Price: {event.market_snapshot.current_price}")

        if event.sentiment_snapshot:
            s = event.sentiment_snapshot
            print(f"Sentiment: {s.overall_sentiment} ({s.aggregated_score:.2f})")
            if s.contrarian_signal:
                print("  ⚠️ Contrarian signal detected!")

        if event.validation_issues:
            print(f"Issues: {event.validation_issues}")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("P1 Sentiment Fusion Examples")
    print("=" * 60)

    await example_basic_sentiment()
    await example_direction_adjustment()
    await example_full_enrichment()
    await example_integrated_extraction()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
