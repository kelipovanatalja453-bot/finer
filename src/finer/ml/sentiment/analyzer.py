"""Sentiment Analyzer — Multi-mode sentiment analysis for investment content.

Supports three modes:
1. Rule mode: Keyword-based analysis (fast, no API calls)
2. LLM mode: Large language model analysis (accurate, requires API)
3. Hybrid mode: Rule first, LLM for low-confidence results
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Dict, List, Optional

from finer.llm import LLMClient
from finer.ml.sentiment.rules import RuleBasedSentimentEngine
from finer.ml.sentiment.schemas import (
    BatchSentimentResult,
    SentimentResult,
    SentimentType,
)

logger = logging.getLogger(__name__)

# Executor for concurrent batch processing
_executor = ThreadPoolExecutor(max_workers=4)


class SentimentMode(str, Enum):
    """Sentiment analysis mode."""

    RULE = "rule"  # Pure rule-based
    LLM = "llm"  # Pure LLM-based
    HYBRID = "hybrid"  # Rule + LLM for low confidence


# Confidence threshold for hybrid mode
HYBRID_LLM_THRESHOLD = 0.6


class SentimentAnalyzer:
    """Investment sentiment analyzer.

    Supports three modes:
    1. Rule mode: Keyword-based (default, no API required)
    2. LLM mode: Large language model (more accurate, requires API)
    3. Hybrid mode: Rule first + LLM for low-confidence results

    Thread-safe for concurrent usage.

    Example:
        >>> analyzer = SentimentAnalyzer()
        >>> result = analyzer.analyze("NVDA看多，目标价150")
        >>> print(result.sentiment)  # SentimentType.BULLISH

        >>> # Hybrid mode
        >>> analyzer = SentimentAnalyzer(mode="hybrid")
        >>> result = analyzer.analyze("可能有机会，但也存在风险")
    """

    def __init__(
        self,
        mode: str = "rule",
        llm_client: Optional[LLMClient] = None,
    ):
        """Initialize sentiment analyzer.

        Args:
            mode: Analysis mode - "rule", "llm", or "hybrid"
            llm_client: Optional LLM client for llm/hybrid modes.
                       If not provided, will use LLMClient.auto()
        """
        self.mode = SentimentMode(mode)
        self.llm_client = llm_client
        self._rule_engine = RuleBasedSentimentEngine()

        if self.mode in (SentimentMode.LLM, SentimentMode.HYBRID):
            if self.llm_client is None:
                self.llm_client = LLMClient.auto()

    def analyze(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SentimentResult:
        """Analyze sentiment of a single text.

        Args:
            text: Text to analyze
            context: Optional market context (e.g., ticker, price data)

        Returns:
            SentimentResult with sentiment type, score, confidence, keywords
        """
        if self.mode == SentimentMode.RULE:
            return self._rule_engine.analyze(text, context)
        elif self.mode == SentimentMode.LLM:
            return self._analyze_with_llm(text, context)
        else:  # HYBRID
            return self._analyze_hybrid(text, context)

    def batch_analyze(
        self,
        texts: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> BatchSentimentResult:
        """Batch analyze multiple texts.

        Concurrent processing for improved throughput.

        Args:
            texts: List of texts to analyze
            context: Optional shared market context

        Returns:
            BatchSentimentResult with all results and statistics
        """
        if not texts:
            return BatchSentimentResult(
                results=[],
                summary={},
                average_score=0.0,
            )

        # Process concurrently
        futures = [_executor.submit(self.analyze, text, context) for text in texts]
        results = [f.result() for f in futures]

        # Compute statistics
        summary: Dict[str, int] = {}
        for r in results:
            key = r.sentiment.value
            summary[key] = summary.get(key, 0) + 1

        avg_score = sum(r.score for r in results) / len(results)

        return BatchSentimentResult(
            results=results,
            summary=summary,
            average_score=avg_score,
        )

    async def batch_analyze_async(
        self,
        texts: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> BatchSentimentResult:
        """Async batch analyze.

        Args:
            texts: List of texts to analyze
            context: Optional shared market context

        Returns:
            BatchSentimentResult
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            lambda: self.batch_analyze(texts, context),
        )

    def _analyze_with_llm(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SentimentResult:
        """Analyze sentiment using LLM.

        Args:
            text: Text to analyze
            context: Optional market context

        Returns:
            SentimentResult with LLM-based analysis
        """
        if self.llm_client is None:
            logger.warning("LLM client not available, falling back to rule-based")
            return self._rule_engine.analyze(text, context)

        prompt = self._build_llm_prompt(text, context)

        try:
            response = self.llm_client.chat_prompt(prompt)
            return self._parse_llm_response(text, response, context)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}, falling back to rule-based")
            return self._rule_engine.analyze(text, context)

    def _analyze_hybrid(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SentimentResult:
        """Hybrid mode: Rule first, LLM for low-confidence results.

        Args:
            text: Text to analyze
            context: Optional market context

        Returns:
            SentimentResult
        """
        # First, use rule-based
        rule_result = self._rule_engine.analyze(text, context)

        # If confidence is high enough, return rule result
        if rule_result.confidence >= HYBRID_LLM_THRESHOLD:
            return rule_result

        # Otherwise, use LLM for refinement
        logger.debug(
            f"Rule confidence {rule_result.confidence:.2f} < {HYBRID_LLM_THRESHOLD}, "
            "using LLM for refinement"
        )

        if self.llm_client is None:
            logger.warning("LLM client not available for hybrid mode, returning rule result")
            return rule_result

        try:
            llm_result = self._analyze_with_llm(text, context)
            # Mark as hybrid in reasoning
            llm_result.reasoning = f"[Hybrid] Rule: {rule_result.sentiment.value} ({rule_result.confidence:.2f}), LLM: {llm_result.reasoning or 'N/A'}"
            return llm_result
        except Exception as e:
            logger.error(f"LLM refinement failed: {e}, returning rule result")
            return rule_result

    def _build_llm_prompt(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build prompt for LLM sentiment analysis.

        Args:
            text: Text to analyze
            context: Optional market context

        Returns:
            Prompt string
        """
        context_str = ""
        if context:
            ticker = context.get("ticker")
            price = context.get("current_price")
            if ticker:
                context_str += f"\n当前标的: {ticker}"
            if price:
                context_str += f"\n当前价格: {price}"

        return f"""分析以下投资相关文本的情绪倾向。

文本:
{text}
{context_str}

请从投资者角度分析情绪，输出 JSON 格式：
{{
  "sentiment": "bullish/bearish/neutral/uncertain",
  "score": -1到1之间的数字（负数看空，正数看多，0为中性）,
  "confidence": 0到1之间的置信度,
  "keywords": ["关键情绪词1", "关键情绪词2"],
  "reasoning": "简短的分析理由"
}}

注意：
1. bullish（看多）: 看涨、推荐买入、利好消息
2. bearish（看空）: 看跌、建议卖出、利空消息
3. neutral（中性）: 客观陈述，无明显倾向
4. uncertain（不确定）: 信息不足或矛盾
"""

    def _parse_llm_response(
        self,
        text: str,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SentimentResult:
        """Parse LLM response into SentimentResult.

        Args:
            text: Original text
            response: LLM response string
            context: Optional market context

        Returns:
            SentimentResult
        """
        import json
        import re

        # Default values
        sentiment = SentimentType.NEUTRAL
        score = 0.0
        confidence = 0.5
        keywords: List[str] = []
        reasoning = None

        try:
            # Extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                # Parse sentiment
                sentiment_str = data.get("sentiment", "neutral").lower()
                sentiment_map = {
                    "bullish": SentimentType.BULLISH,
                    "bearish": SentimentType.BEARISH,
                    "neutral": SentimentType.NEUTRAL,
                    "uncertain": SentimentType.UNCERTAIN,
                }
                sentiment = sentiment_map.get(sentiment_str, SentimentType.NEUTRAL)

                # Parse score
                score = float(data.get("score", 0.0))
                score = max(-1.0, min(1.0, score))

                # Parse confidence
                confidence = float(data.get("confidence", 0.5))
                confidence = max(0.0, min(1.0, confidence))

                # Parse keywords
                keywords = data.get("keywords", [])
                if isinstance(keywords, list):
                    keywords = [str(k) for k in keywords[:10]]
                else:
                    keywords = []

                # Parse reasoning
                reasoning = data.get("reasoning")

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # Try to infer from response text
            if "bullish" in response.lower() or "看多" in response:
                sentiment = SentimentType.BULLISH
                score = 0.5
            elif "bearish" in response.lower() or "看空" in response:
                sentiment = SentimentType.BEARISH
                score = -0.5

        return SentimentResult(
            text=text,
            sentiment=sentiment,
            score=score,
            confidence=confidence,
            keywords=keywords,
            market_context=context,
            reasoning=reasoning,
        )


# Convenience function
def analyze_sentiment(
    text: str,
    mode: str = "rule",
    context: Optional[Dict[str, Any]] = None,
) -> SentimentResult:
    """Quick sentiment analysis.

    Args:
        text: Text to analyze
        mode: Analysis mode ("rule", "llm", "hybrid")
        context: Optional market context

    Returns:
        SentimentResult
    """
    analyzer = SentimentAnalyzer(mode=mode)
    return analyzer.analyze(text, context)
