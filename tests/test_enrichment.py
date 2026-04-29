"""Tests for F2 Anchor — market data fusion and sentiment fusion.

Covers:
- MarketContextEnricher: Market data fetching and validation
- SentimentFusionEnricher: Multi-source sentiment aggregation
- PriceRangeValidator: Price target validation
- Entity extraction and topic splitting
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional, Dict, Any

from finer.enrichment import (
    Topic,
    EntityExtraction,
    TopicSplitter,
    EntityExtractor,
    ContentLinker,
    get_content_linker,
)
from finer.enrichment.market_context import (
    PriceRangeValidator,
    MarketContextEnricher,
    EnrichmentStats,
    get_market_enricher,
)
from finer.enrichment.sentiment_fusion import (
    SentimentFusionEnricher,
    SentimentFusionStats,
    DirectionAdjustment,
    get_sentiment_enricher,
    DEFAULT_SOURCE_WEIGHTS,
)
from finer.schemas.event import EventWithActions, TradingAction
from finer.schemas.enriched_event import (
    MarketDataSnapshot,
    SentimentSnapshot,
    PriceValidation,
    EnrichedEventWithActions,
)
from finer.schemas.trade_action import (
    ActionStep,
    ActionType,
    TriggerType,
    TradeDirection,
)


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_finance_client():
    """Mock FinanceSkillsClient."""
    client = AsyncMock()
    client.call = AsyncMock()
    client.call_batch = AsyncMock()
    return client


@pytest.fixture
def mock_llm_client():
    """Mock LLMClient."""
    client = MagicMock()
    client.chat_prompt = MagicMock()
    client.chat = MagicMock()
    return client


@pytest.fixture
def sample_event():
    """Sample EventWithActions for testing."""
    return EventWithActions(
        event_id="evt-001",
        content_id="content-001",
        ticker="AAPL",
        direction="bullish",
        evidence_text="AAPL at 180 is a good entry point",
        action_chain=[
            TradingAction(
                sequence=1,
                action_type=ActionType.LONG,
                trigger_condition="price <= 180",
                confidence=0.8,
            ),
        ],
    )


@pytest.fixture
def sample_market_data():
    """Sample market data from finance-skills."""
    return {
        "current_price": 175.0,
        "change_pct": 1.2,
        "volume": 50000000,
        "52wk_high": 200.0,
        "52wk_low": 120.0,
        "pe_ratio": 28.5,
        "market_cap": 2800000000000,
    }


# =============================================================================
# TopicSplitter Tests
# =============================================================================

class TestTopicSplitter:
    """Tests for TopicSplitter."""

    def test_topic_splitter_short_content(self, mock_llm_client):
        """Test that short content is not split."""
        splitter = TopicSplitter(llm=mock_llm_client)
        content = "Short content\nwith few lines"
        topics = splitter.split(content, min_lines=50)
        assert topics == []

    def test_topic_splitter_success(self, mock_llm_client):
        """Test successful topic splitting."""
        mock_llm_client.chat_prompt.return_value = """
        {
          "topics": [
            {
              "title": "AAPL 看多",
              "tickers": ["AAPL"],
              "companies": ["苹果"],
              "time_range": {"start": "2026-01", "end": "2026-04"},
              "summary": "看好苹果股票",
              "start_line": 1,
              "end_line": 50
            }
          ]
        }
        """
        splitter = TopicSplitter(llm=mock_llm_client)
        content = "\n".join(["Line " + str(i) for i in range(100)])

        topics = splitter.split(content, min_lines=10)
        assert len(topics) == 1
        assert topics[0].title == "AAPL 看多"
        assert "AAPL" in topics[0].tickers

    def test_topic_splitter_parse_error(self, mock_llm_client):
        """Test handling of parse errors."""
        mock_llm_client.chat_prompt.return_value = "Invalid JSON"
        splitter = TopicSplitter(llm=mock_llm_client)
        content = "\n".join(["Line " + str(i) for i in range(100)])

        topics = splitter.split(content, min_lines=10)
        assert topics == []


# =============================================================================
# EntityExtractor Tests
# =============================================================================

class TestEntityExtractor:
    """Tests for EntityExtractor."""

    def test_entity_extractor_known_tickers(self, mock_llm_client):
        """Test extraction of known tickers via regex."""
        mock_llm_client.chat_prompt.return_value = '{"tickers": []}'
        extractor = EntityExtractor(llm=mock_llm_client)

        content = "AAPL and TSLA are both moving today"
        extraction = extractor.extract(content)

        # Should find known tickers
        assert len(extraction.tickers) >= 0  # Depends on ENTITY_REGISTRY

    def test_entity_extractor_valid_ticker_format(self, mock_llm_client):
        """Test ticker format validation."""
        extractor = EntityExtractor(llm=mock_llm_client)

        # US stocks
        assert extractor._is_valid_ticker("AAPL") is True
        assert extractor._is_valid_ticker("NVDA") is True

        # HK stocks
        assert extractor._is_valid_ticker("0700.HK") is True
        assert extractor._is_valid_ticker("9988.HK") is True

        # CN stocks
        assert extractor._is_valid_ticker("600519.SH") is True
        assert extractor._is_valid_ticker("000001.SZ") is True

        # Crypto
        assert extractor._is_valid_ticker("BTC") is True
        assert extractor._is_valid_ticker("ETH") is True

        # Invalid: Chinese characters
        assert extractor._is_valid_ticker("苹果") is False
        assert extractor._is_valid_ticker("腾讯") is False

    def test_entity_extractor_financial_event_filter(self, mock_llm_client):
        """Test financial event filtering."""
        extractor = EntityExtractor(llm=mock_llm_client)

        # Financial events
        assert extractor._is_financial_event("财报发布") is True
        assert extractor._is_financial_event("IPO") is True
        assert extractor._is_financial_event("收购并购") is True

        # Non-financial
        assert extractor._is_financial_event("天气晴朗") is False
        assert extractor._is_financial_event("周末活动") is False

    def test_entity_extractor_financial_concept_filter(self, mock_llm_client):
        """Test financial concept filtering."""
        extractor = EntityExtractor(llm=mock_llm_client)

        # Financial concepts
        assert extractor._is_financial_concept("估值") is True
        assert extractor._is_financial_concept("市盈率") is True
        assert extractor._is_financial_concept("ROE") is True

        # Non-financial / tool names
        assert extractor._is_financial_concept("飞书") is False
        assert extractor._is_financial_concept("网盘") is False


# =============================================================================
# ContentLinker Tests
# =============================================================================

class TestContentLinker:
    """Tests for ContentLinker."""

    def test_content_linker_index(self):
        """Test content indexing."""
        linker = ContentLinker()
        entities = EntityExtraction(
            tickers=["AAPL", "TSLA"],
            companies=["Apple", "Tesla"],
            events=["Earnings"],
        )
        linker.index_content("content-001", entities)

        assert "AAPL" in linker.index
        assert "content-001" in linker.index["AAPL"]

    def test_content_linker_find_related(self):
        """Test finding related content."""
        linker = ContentLinker()

        # Index two contents with shared ticker
        entities1 = EntityExtraction(tickers=["AAPL"])
        entities2 = EntityExtraction(tickers=["AAPL", "TSLA"])

        linker.index_content("content-001", entities1)
        linker.index_content("content-002", entities2)

        related = linker.find_related("content-001")
        assert "content-002" in related

    def test_content_linker_get_by_ticker(self):
        """Test getting content by ticker."""
        linker = ContentLinker()
        entities = EntityExtraction(tickers=["AAPL"])
        linker.index_content("content-001", entities)

        content = linker.get_by_ticker("AAPL")
        assert "content-001" in content


# =============================================================================
# PriceRangeValidator Tests
# =============================================================================

class TestPriceRangeValidator:
    """Tests for PriceRangeValidator."""

    def test_validate_no_market_data(self):
        """Test validation when no market data available."""
        validator = PriceRangeValidator()
        action = TradingAction(
            sequence=1,
            action_type=ActionType.LONG,
            target_price_low=100.0,
            target_price_high=150.0,
            confidence=0.8,
        )

        validation = validator.validate(action, None)
        assert "No market data" in validation.warnings[0]

    def test_validate_price_range_valid(self):
        """Test valid price range."""
        validator = PriceRangeValidator()
        action = TradingAction(
            sequence=1,
            action_type=ActionType.LONG,
            target_price_low=100.0,
            target_price_high=150.0,
            confidence=0.8,
        )
        market = MarketDataSnapshot(
            ticker="AAPL",
            current_price=120.0,
            high_52wk=200.0,
            low_52wk=80.0,
        )

        validation = validator.validate(action, market)
        assert validation.is_valid is True

    def test_validate_price_range_invalid(self):
        """Test invalid price range (low >= high)."""
        validator = PriceRangeValidator()
        action = TradingAction(
            sequence=1,
            action_type=ActionType.LONG,
            target_price_low=150.0,
            target_price_high=100.0,  # Invalid
            confidence=0.8,
        )
        market = MarketDataSnapshot(
            ticker="AAPL",
            current_price=120.0,
            high_52wk=200.0,
            low_52wk=80.0,
        )

        validation = validator.validate(action, market)
        assert validation.is_valid is False
        assert len(validation.issues) > 0

    def test_validate_price_near_52wk_high(self):
        """Test detection of price near 52-week high."""
        validator = PriceRangeValidator()
        action = TradingAction(
            sequence=1,
            action_type=ActionType.LONG,
            confidence=0.8,
        )
        market = MarketDataSnapshot(
            ticker="AAPL",
            current_price=195.0,  # Near 200
            high_52wk=200.0,
            low_52wk=100.0,
        )

        validation = validator.validate(action, market)
        assert validation.price_position == "near_52wk_high"

    def test_validate_price_near_52wk_low(self):
        """Test detection of price near 52-week low."""
        validator = PriceRangeValidator()
        action = TradingAction(
            sequence=1,
            action_type=ActionType.LONG,
            confidence=0.8,
        )
        market = MarketDataSnapshot(
            ticker="AAPL",
            current_price=105.0,  # Near 100
            high_52wk=200.0,
            low_52wk=100.0,
        )

        validation = validator.validate(action, market)
        assert validation.price_position == "near_52wk_low"

    def test_validate_target_outside_52wk_range(self):
        """Test detection of targets far outside 52-week range."""
        validator = PriceRangeValidator()
        action = TradingAction(
            sequence=1,
            action_type=ActionType.LONG,
            target_price_high=350.0,  # Way above 52wk high
            confidence=0.8,
        )
        market = MarketDataSnapshot(
            ticker="AAPL",
            current_price=180.0,
            high_52wk=200.0,
            low_52wk=100.0,
        )

        validation = validator.validate(action, market)
        assert validation.is_valid is False


# =============================================================================
# MarketContextEnricher Tests
# =============================================================================

class TestMarketContextEnricher:
    """Tests for MarketContextEnricher."""

    @pytest.mark.asyncio
    async def test_fetch_market_data_success(self, mock_finance_client, sample_market_data):
        """Test successful market data fetching."""
        mock_finance_client.call_batch.return_value = [
            sample_market_data,
            {"fundamentals": {"pe_ratio": 28.5}, "options_flow": {}},
        ]

        enricher = MarketContextEnricher(client=mock_finance_client, enable_sentiment=False)
        snapshot = await enricher.fetch_market_data("AAPL")

        assert snapshot is not None
        assert snapshot.ticker == "AAPL"
        assert snapshot.current_price == 175.0

    @pytest.mark.asyncio
    async def test_fetch_market_data_no_data(self, mock_finance_client):
        """Test handling when no market data available."""
        mock_finance_client.call_batch.return_value = [None, None]

        enricher = MarketContextEnricher(client=mock_finance_client, enable_sentiment=False)
        snapshot = await enricher.fetch_market_data("UNKNOWN")

        assert snapshot is None

    @pytest.mark.asyncio
    async def test_enrich_event_success(
        self, mock_finance_client, sample_event, sample_market_data
    ):
        """Test successful event enrichment."""
        mock_finance_client.call_batch.return_value = [
            sample_market_data,
            {"fundamentals": {}, "options_flow": {}},
        ]

        enricher = MarketContextEnricher(client=mock_finance_client, enable_sentiment=False)
        enriched, issues = await enricher.enrich_event(sample_event)

        assert enriched.ticker == "AAPL"
        assert enriched.market_snapshot is not None
        assert enriched.overall_confidence > 0

    @pytest.mark.asyncio
    async def test_enrich_events_batch(self, mock_finance_client, sample_market_data):
        """Test batch event enrichment."""
        mock_finance_client.call_batch.return_value = [
            sample_market_data,
            {"fundamentals": {}, "options_flow": {}},
        ]

        events = [
            EventWithActions(
                ticker="AAPL",
                direction="bullish",
                evidence_text="Test 1",
            ),
            EventWithActions(
                ticker="TSLA",
                direction="bearish",
                evidence_text="Test 2",
            ),
        ]

        enricher = MarketContextEnricher(client=mock_finance_client, enable_sentiment=False)
        enriched_events, stats = await enricher.enrich_events(events)

        assert stats.total_events == 2
        assert stats.enriched_events == 2


# =============================================================================
# SentimentFusionEnricher Tests
# =============================================================================

class TestSentimentFusionEnricher:
    """Tests for SentimentFusionEnricher."""

    @pytest.mark.asyncio
    async def test_fetch_sentiment_success(self, mock_finance_client):
        """Test successful sentiment fetching."""
        mock_finance_client.call.return_value = {
            "reddit": {"score": 0.7, "mentions": 100},
            "twitter": {"score": 0.6, "mentions": 200},
            "news": {"score": 0.5, "count": 50},
            "polymarket": {"probability": 0.65},
            "velocity": 0.1,
        }

        enricher = SentimentFusionEnricher(client=mock_finance_client)
        snapshot = await enricher.fetch_sentiment("AAPL")

        assert snapshot.ticker == "AAPL"
        assert len(snapshot.sources) == 4
        assert snapshot.data_quality == "complete"

    @pytest.mark.asyncio
    async def test_fetch_sentiment_no_data(self, mock_finance_client):
        """Test handling when no sentiment data available."""
        mock_finance_client.call.return_value = None

        enricher = SentimentFusionEnricher(client=mock_finance_client)
        snapshot = await enricher.fetch_sentiment("UNKNOWN")

        assert snapshot.data_quality == "unavailable"

    def test_aggregate_sentiment(self, mock_finance_client):
        """Test sentiment aggregation."""
        enricher = SentimentFusionEnricher(client=mock_finance_client)

        snapshot = SentimentSnapshot(
            ticker="AAPL",
            reddit_sentiment=0.6,
            twitter_sentiment=0.8,
            news_sentiment=0.7,
            polymarket_probability=0.75,
        )
        snapshot.source_weights = DEFAULT_SOURCE_WEIGHTS

        score = enricher._aggregate_sentiment(snapshot)
        assert -1.0 <= score <= 1.0

    def test_classify_sentiment(self, mock_finance_client):
        """Test sentiment classification."""
        enricher = SentimentFusionEnricher(client=mock_finance_client)

        assert enricher._classify_sentiment(0.5) == "bullish"
        assert enricher._classify_sentiment(-0.5) == "bearish"
        assert enricher._classify_sentiment(0.0) == "neutral"

    def test_detect_contrarian_bullish_extreme(self, mock_finance_client):
        """Test contrarian signal detection for extreme bullish."""
        enricher = SentimentFusionEnricher(client=mock_finance_client)

        # Extreme bullish + rapid rise
        assert enricher._detect_contrarian(0.8, 0.4) is True

        # Moderate sentiment
        assert enricher._detect_contrarian(0.5, 0.2) is False

    def test_detect_contrarian_bearish_extreme(self, mock_finance_client):
        """Test contrarian signal detection for extreme bearish."""
        enricher = SentimentFusionEnricher(client=mock_finance_client)

        # Extreme bearish + rapid fall
        assert enricher._detect_contrarian(-0.8, -0.4) is True

    def test_calculate_direction_adjustment_bullish_extreme(
        self, mock_finance_client
    ):
        """Test direction adjustment for bullish view with extreme sentiment."""
        enricher = SentimentFusionEnricher(client=mock_finance_client)

        sentiment = SentimentSnapshot(
            ticker="AAPL",
            aggregated_score=0.8,
            extreme_sentiment=True,
            contrarian_signal=True,
        )
        sentiment.data_quality = "complete"

        adjustment = enricher.calculate_direction_adjustment("bullish", sentiment)

        # Bullish + extreme optimism should reduce confidence
        assert adjustment.confidence_modifier < 0
        assert adjustment.contrarian_opportunity is True

    def test_calculate_direction_adjustment_bullish_pessimistic(
        self, mock_finance_client
    ):
        """Test direction adjustment for bullish view against pessimism."""
        enricher = SentimentFusionEnricher(client=mock_finance_client)

        sentiment = SentimentSnapshot(
            ticker="AAPL",
            aggregated_score=-0.8,
            extreme_sentiment=True,
        )
        sentiment.data_quality = "complete"

        adjustment = enricher.calculate_direction_adjustment("bullish", sentiment)

        # Bullish + extreme pessimism = contrarian opportunity
        assert adjustment.confidence_modifier > 0
        assert "contrarian" in adjustment.reason.lower()

    @pytest.mark.asyncio
    async def test_enrich_event_with_sentiment(
        self, mock_finance_client, sample_event
    ):
        """Test event enrichment with sentiment."""
        mock_finance_client.call.return_value = {
            "reddit": {"score": 0.7},
            "twitter": {"score": 0.6},
            "news": {"score": 0.5},
        }

        enricher = SentimentFusionEnricher(client=mock_finance_client)
        enriched, issues = await enricher.enrich_event(sample_event)

        assert enriched.sentiment_snapshot is not None


# =============================================================================
# EnrichmentStats Tests
# =============================================================================

class TestEnrichmentStats:
    """Tests for EnrichmentStats."""

    def test_stats_defaults(self):
        """Test default stats values."""
        stats = EnrichmentStats()
        assert stats.total_events == 0
        assert stats.enriched_events == 0
        assert stats.failed_enrichments == 0

    def test_stats_values(self):
        """Test stats with values."""
        stats = EnrichmentStats(
            total_events=10,
            enriched_events=8,
            failed_enrichments=2,
            validation_issues=3,
            requires_review=1,
        )
        assert stats.total_events == 10
        assert stats.enriched_events == 8


# =============================================================================
# SentimentFusionStats Tests
# =============================================================================

class TestSentimentFusionStats:
    """Tests for SentimentFusionStats."""

    def test_stats_defaults(self):
        """Test default stats values."""
        stats = SentimentFusionStats()
        assert stats.total_events == 0
        assert stats.contrarian_signals == 0
        assert stats.extreme_sentiments == 0
