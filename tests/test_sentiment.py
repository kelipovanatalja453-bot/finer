"""Tests for Sentiment Analysis."""

import pytest
from unittest.mock import MagicMock

from finer.ml.sentiment import (
    SentimentResult,
    SentimentAnalyzer,
    RuleBasedSentimentAnalyzer,
    analyze_sentiment,
)
from finer.ml.sentiment.analyzer import SentimentMode
from finer.ml.sentiment.rules import RuleBasedSentimentEngine
from finer.ml.sentiment.schemas import SentimentType, BatchSentimentResult


class TestRuleBasedSentimentEngine:
    """Test rule-based sentiment engine."""

    def test_initialization(self):
        """Test engine initialization."""
        engine = RuleBasedSentimentEngine()
        assert engine is not None

    def test_bullish_chinese(self):
        """Test bullish sentiment in Chinese."""
        engine = RuleBasedSentimentEngine()
        result = engine.analyze("看好苹果股票，建议买入")
        assert result.sentiment == SentimentType.BULLISH
        assert result.score > 0
        assert len(result.keywords) > 0

    def test_bearish_chinese(self):
        """Test bearish sentiment in Chinese."""
        engine = RuleBasedSentimentEngine()
        result = engine.analyze("特斯拉风险很大，建议卖出止损")
        assert result.sentiment == SentimentType.BEARISH
        assert result.score < 0
        assert len(result.keywords) > 0

    def test_neutral(self):
        """Test neutral sentiment."""
        engine = RuleBasedSentimentEngine()
        result = engine.analyze("今天市场平静，没什么大事件")
        assert result.sentiment == SentimentType.NEUTRAL
        assert abs(result.score) < 0.3

    def test_bullish_english(self):
        """Test bullish sentiment in English."""
        engine = RuleBasedSentimentEngine()
        result = engine.analyze("AAPL looks bullish, strong buy signal")
        assert result.sentiment == SentimentType.BULLISH
        assert result.score > 0

    def test_bearish_english(self):
        """Test bearish sentiment in English."""
        engine = RuleBasedSentimentEngine()
        result = engine.analyze("TSLA is overvalued, recommend selling")
        assert result.sentiment == SentimentType.BEARISH
        assert result.score < 0

    def test_negation(self):
        """Test negation handling."""
        engine = RuleBasedSentimentEngine()
        # "不看好" should reduce confidence or reverse sentiment
        result = engine.analyze("我不看好这只股票")
        # Negation should affect the result
        assert result.confidence < 0.9 or result.sentiment != SentimentType.BULLISH

    def test_intensity_modifiers(self):
        """Test intensity modifier handling."""
        engine = RuleBasedSentimentEngine()
        # Both should be bullish
        result1 = engine.analyze("强烈看好这只股票")
        result2 = engine.analyze("稍微看好这只股票")
        assert result1.sentiment == SentimentType.BULLISH
        assert result2.sentiment == SentimentType.BULLISH

    def test_with_context(self):
        """Test with market context."""
        engine = RuleBasedSentimentEngine()
        context = {"ticker": "AAPL"}
        result = engine.analyze("买入信号", context=context)
        assert result.market_context == context
        assert result.score > 0


class TestSentimentAnalyzer:
    """Test unified sentiment analyzer."""

    def test_rule_based_mode(self):
        """Test rule-based mode."""
        analyzer = SentimentAnalyzer(mode="rule")
        result = analyzer.analyze("看好苹果股票，建议买入")
        assert result.sentiment == SentimentType.BULLISH

    def test_batch_analysis(self):
        """Test batch analysis."""
        analyzer = SentimentAnalyzer(mode="rule")
        texts = ["看好", "看空", "中性"]
        result = analyzer.batch_analyze(texts)
        assert len(result.results) == 3


class TestSentimentResult:
    """Test SentimentResult model."""

    def test_create_result(self):
        """Test creating a result."""
        result = SentimentResult(
            text="看好苹果",
            sentiment=SentimentType.BULLISH,
            score=0.8,
            confidence=0.9,
            keywords=["看好"],
        )
        assert result.score == 0.8
        assert result.sentiment == SentimentType.BULLISH

    def test_result_with_keywords(self):
        """Test result with keywords."""
        result = SentimentResult(
            text="看好苹果",
            sentiment=SentimentType.BULLISH,
            score=0.5,
            confidence=0.8,
            keywords=["买入", "看好"],
        )
        assert len(result.keywords) == 2


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_analyze_sentiment(self):
        """Test analyze_sentiment function."""
        result = analyze_sentiment("看好苹果，买入", mode="rule")
        assert result is not None
        assert result.score > 0


# =============================================================================
# New Analyzer Tests (Rule/LLM/Hybrid Modes)
# =============================================================================


class TestRuleBasedSentimentEngineNew:
    """Tests for the new RuleBasedSentimentEngine."""

    @pytest.fixture
    def engine(self):
        return RuleBasedSentimentEngine()

    def test_bullish_keywords_detection(self, engine):
        """Test detection of bullish keywords."""
        texts = [
            "NVDA看多，目标价150",
            "强烈推荐买入",
            "看好苹果的未来发展",
        ]
        for text in texts:
            result = engine.analyze(text)
            assert result.sentiment == SentimentType.BULLISH
            assert result.score > 0
            assert len(result.keywords) > 0

    def test_bearish_keywords_detection(self, engine):
        """Test detection of bearish keywords."""
        texts = [
            "看空特斯拉，建议减仓",
            "止损出局",
            "利空消息，回避",
        ]
        for text in texts:
            result = engine.analyze(text)
            assert result.sentiment == SentimentType.BEARISH
            assert result.score < 0

    def test_neutral_text(self, engine):
        """Test neutral sentiment."""
        result = engine.analyze("苹果公司发布了新的财报")
        assert result.sentiment == SentimentType.NEUTRAL
        assert abs(result.score) < 0.3

    def test_negation_reversal(self, engine):
        """Test negation affects sentiment."""
        result1 = engine.analyze("看好这个股票")
        assert result1.sentiment == SentimentType.BULLISH

        result2 = engine.analyze("不看好这个股票")
        # Negation should reduce confidence
        assert result2.confidence < result1.confidence

    def test_intensifier_amplification(self, engine):
        """Test intensifiers amplify sentiment."""
        result1 = engine.analyze("看好这个股票")
        result2 = engine.analyze("非常看好这个股票")
        # Both should be bullish
        assert result1.sentiment == SentimentType.BULLISH
        assert result2.sentiment == SentimentType.BULLISH

    def test_chinese_text(self, engine):
        """Test Chinese text analysis."""
        result = engine.analyze("强烈看好茅台，目标价2000，建议加仓")
        assert result.sentiment == SentimentType.BULLISH
        assert result.score > 0.5

    def test_english_text(self, engine):
        """Test English text analysis."""
        result = engine.analyze("AAPL looks bullish, strong buy signal")
        assert result.sentiment == SentimentType.BULLISH
        assert result.score > 0

    def test_mixed_language(self, engine):
        """Test mixed Chinese-English text."""
        result = engine.analyze("NVDA突破新高，very bullish，建议加仓")
        assert result.sentiment == SentimentType.BULLISH

    def test_empty_text(self, engine):
        """Test empty text handling."""
        result = engine.analyze("")
        assert result.sentiment == SentimentType.NEUTRAL
        assert result.score == 0.0

    def test_score_range(self, engine):
        """Test score is always in valid range."""
        texts = [
            "极其看多，超级看好，强烈买入",
            "看空看空看空，风险极大",
            "普通的一天",
        ]
        for text in texts:
            result = engine.analyze(text)
            assert -1.0 <= result.score <= 1.0


class TestSentimentAnalyzerNew:
    """Tests for the new SentimentAnalyzer with multiple modes."""

    def test_rule_mode(self):
        """Test rule-based mode."""
        analyzer = SentimentAnalyzer(mode="rule")
        result = analyzer.analyze("NVDA看多，目标价150")
        assert result.sentiment == SentimentType.BULLISH

    def test_llm_mode_with_mock(self):
        """Test LLM mode with mocked client."""
        mock_client = MagicMock()
        mock_client.chat_prompt.return_value = """
        {
            "sentiment": "bullish",
            "score": 0.8,
            "confidence": 0.9,
            "keywords": ["看多", "目标价"],
            "reasoning": "明确的看多表述"
        }
        """
        analyzer = SentimentAnalyzer(mode="llm", llm_client=mock_client)
        result = analyzer.analyze("NVDA看多，目标价150")
        assert result.sentiment == SentimentType.BULLISH
        assert result.score == 0.8

    def test_llm_mode_fallback(self):
        """Test LLM mode falls back to rule when LLM fails."""
        mock_client = MagicMock()
        mock_client.chat_prompt.side_effect = Exception("LLM error")
        analyzer = SentimentAnalyzer(mode="llm", llm_client=mock_client)
        result = analyzer.analyze("NVDA看多，目标价150")
        assert result.sentiment == SentimentType.BULLISH

    def test_hybrid_mode_high_confidence(self):
        """Test hybrid mode returns rule result when confidence is high."""
        analyzer = SentimentAnalyzer(mode="hybrid")
        result = analyzer.analyze("强烈看好，绝对买入，目标价翻倍")
        assert result.sentiment == SentimentType.BULLISH

    def test_hybrid_mode_low_confidence(self):
        """Test hybrid mode calls LLM when rule confidence is low."""
        mock_client = MagicMock()
        mock_client.chat_prompt.return_value = """
        {
            "sentiment": "uncertain",
            "score": 0.0,
            "confidence": 0.6,
            "keywords": [],
            "reasoning": "信息不明确"
        }
        """
        analyzer = SentimentAnalyzer(mode="hybrid", llm_client=mock_client)
        result = analyzer.analyze("可能有机会，但也存在风险")
        assert result.reasoning is not None

    def test_batch_analyze_new(self):
        """Test batch analysis with new analyzer."""
        analyzer = SentimentAnalyzer(mode="rule")
        texts = ["NVDA看多", "TSLA看空", "AAPL发布财报"]
        result = analyzer.batch_analyze(texts)
        assert len(result.results) == 3
        assert result.summary.get("bullish", 0) == 1
        assert result.summary.get("bearish", 0) == 1

    def test_batch_analyze_empty(self):
        """Test batch analysis with empty list."""
        analyzer = SentimentAnalyzer(mode="rule")
        result = analyzer.batch_analyze([])
        assert len(result.results) == 0
        assert result.average_score == 0.0

    def test_invalid_mode(self):
        """Test invalid mode raises error."""
        with pytest.raises(ValueError):
            SentimentAnalyzer(mode="invalid")


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_analysis(self):
        """Test concurrent sentiment analysis."""
        import concurrent.futures
        analyzer = SentimentAnalyzer(mode="rule")
        texts = ["NVDA看多", "TSLA看空", "AAPL中性"] * 10
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(analyzer.analyze, texts))
        assert len(results) == 30
        for result in results:
            assert isinstance(result, SentimentResult)


class TestConfidenceScoring:
    """Tests for confidence scoring."""

    @pytest.fixture
    def engine(self):
        return RuleBasedSentimentEngine()

    def test_high_confidence_with_multiple_keywords(self, engine):
        """Test high confidence with multiple keywords."""
        result = engine.analyze("强烈看好，建议买入，目标价150，加仓机会")
        assert result.confidence > 0.5

    def test_low_confidence_with_no_keywords(self, engine):
        """Test low confidence with no keywords."""
        result = engine.analyze("今天天气不错")
        assert result.confidence < 0.5
