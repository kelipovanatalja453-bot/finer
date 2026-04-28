"""Rule-Based Sentiment Analysis Engine.

A fast, offline sentiment analyzer using keyword matching and pattern recognition.
No API calls required, suitable for batch processing.
"""

from __future__ import annotations

import re
import threading
from typing import Dict, List, Optional, Set

from finer.ml.sentiment.schemas import SentimentResult, SentimentType


class RuleBasedSentimentEngine:
    """Rule-based sentiment analysis engine.

    Uses keyword matching and pattern recognition to determine sentiment.
    No API calls required, fast and suitable for batch processing.
    """

    # 看多关键词
    BULLISH_KEYWORDS: Set[str] = {
        # 中文
        "看多",
        "买入",
        "加仓",
        "看好",
        "上涨",
        "涨",
        "牛市",
        "抄底",
        "增持",
        "推荐",
        "利好",
        "突破",
        "新高",
        "反弹",
        "回升",
        "强势",
        "上涨趋势",
        "底部",
        "机会",
        "低估",
        "价值投资",
        "长期持有",
        "目标价",
        "看涨",
        "做多",
        "多头",
        "超买",
        "金叉",
        "放量",
        # English
        "bullish",
        "buy",
        "long",
        "upgrade",
        "outperform",
        "rally",
        "surge",
        "gain",
        "profit",
        "opportunity",
        "undervalued",
        "breakout",
        "support",
        "accumulate",
    }

    # 看空关键词
    BEARISH_KEYWORDS: Set[str] = {
        # 中文
        "看空",
        "卖出",
        "减仓",
        "看淡",
        "下跌",
        "跌",
        "熊市",
        "止损",
        "减持",
        "回避",
        "利空",
        "破位",
        "新低",
        "回调",
        "下滑",
        "弱势",
        "下跌趋势",
        "顶部",
        "风险",
        "高估",
        "泡沫",
        "清仓",
        "看跌",
        "做空",
        "空头",
        "超卖",
        "死叉",
        "缩量",
        "崩盘",
        # English
        "bearish",
        "sell",
        "short",
        "downgrade",
        "underperform",
        "drop",
        "decline",
        "loss",
        "risk",
        "overvalued",
        "bubble",
        "breakdown",
        "resistance",
        "distribute",
    }

    # 否定词（反转情绪）
    NEGATION_WORDS: Set[str] = {
        "不",
        "没",
        "无",
        "非",
        "别",
        "莫",
        "未",
        "勿",
        "难以",
        "不会",
        "没有",
        "not",
        "no",
        "never",
        "neither",
        "nor",
        "dont",
        "wont",
        "cant",
    }

    # 程度词（加强/减弱情绪）
    INTENSIFIERS: Dict[str, float] = {
        # 加强
        "非常": 1.5,
        "极其": 1.8,
        "特别": 1.5,
        "相当": 1.3,
        "很": 1.2,
        "真的": 1.3,
        "绝对": 1.8,
        "肯定": 1.5,
        "强烈": 1.6,
        "大幅": 1.5,
        "巨大": 1.5,
        "超级": 1.7,
        "非常": 1.5,
        "very": 1.5,
        "extremely": 1.8,
        "highly": 1.6,
        "strongly": 1.6,
        "absolutely": 1.8,
        # 减弱
        "稍微": 0.7,
        "有点": 0.7,
        "可能": 0.8,
        "或许": 0.6,
        "大概": 0.7,
        "似乎": 0.6,
        "稍微": 0.7,
        "略微": 0.7,
        "一点": 0.7,
        "slightly": 0.7,
        "somewhat": 0.7,
        "maybe": 0.7,
        "perhaps": 0.6,
        "might": 0.7,
    }

    # 句末标点（用于判断句子边界）
    SENTENCE_ENDINGS = {"。", "！", "！", ".", "!", "?"}

    def __init__(self) -> None:
        """Initialize the rule engine with thread-safe lock."""
        self._lock = threading.Lock()

    def analyze(self, text: str, context: Optional[Dict] = None) -> SentimentResult:
        """Analyze text sentiment using rules.

        Logic:
        1. Tokenize text (simple character/space split)
        2. Match bullish/bearish keywords
        3. Check negation words (reverse sentiment)
        4. Check intensifiers (adjust intensity)
        5. Calculate sentiment score and confidence

        Args:
            text: Text to analyze
            context: Optional market context (not used in rule mode)

        Returns:
            SentimentResult with sentiment type, score, confidence and keywords
        """
        with self._lock:
            return self._analyze_unsafe(text, context)

    def _analyze_unsafe(
        self, text: str, context: Optional[Dict] = None
    ) -> SentimentResult:
        """Internal analyze without lock (for reentrant calls)."""
        # Normalize text
        text_lower = text.lower()
        text_normalized = self._normalize_text(text)

        # Extract keywords
        bullish_keywords = self._extract_keywords(text_normalized, self.BULLISH_KEYWORDS)
        bearish_keywords = self._extract_keywords(text_normalized, self.BEARISH_KEYWORDS)

        # Count matches
        bullish_count = len(bullish_keywords)
        bearish_count = len(bearish_keywords)

        # Check for negations and intensifiers
        negation_factor = self._check_negation(text_normalized)
        intensifier_factor = self._check_intensifier(text_normalized)

        # Compute sentiment score
        raw_score = self._compute_score(bullish_count, bearish_count, intensifier_factor)

        # Apply negation (reverse if negation present)
        if negation_factor:
            raw_score = -raw_score * 0.8  # Negation reduces confidence

        # Determine sentiment type and confidence
        sentiment, confidence = self._determine_sentiment(
            raw_score, bullish_count, bearish_count, negation_factor
        )

        # Combine all keywords
        all_keywords = list(set(bullish_keywords + bearish_keywords))

        return SentimentResult(
            text=text,
            sentiment=sentiment,
            score=raw_score,
            confidence=confidence,
            keywords=all_keywords,
            market_context=context,
        )

    def _normalize_text(self, text: str) -> str:
        """Normalize text for analysis."""
        # Convert to lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        return text

    def _extract_keywords(self, text: str, keyword_set: Set[str]) -> List[str]:
        """Extract matching keywords from text."""
        matches = []
        for keyword in keyword_set:
            if keyword.lower() in text:
                matches.append(keyword)
        return matches

    def _check_negation(self, text: str) -> bool:
        """Check if text contains negation words.

        Only matches negation words that are standalone (not part of other words).
        """
        for neg in self.NEGATION_WORDS:
            # Find all occurrences
            idx = 0
            while True:
                idx = text.find(neg, idx)
                if idx == -1:
                    break

                # Check if it's a standalone word (not part of another word)
                # For single-char negations, check surrounding characters
                if len(neg) == 1:
                    # Skip common false positives
                    if neg == "非" and idx + 1 < len(text) and text[idx + 1] in "常规":
                        # "非常", "非规" are not negations in this context
                        idx += 1
                        continue
                    if neg == "未" and idx + 1 < len(text) and text[idx + 1] in "来曾经":
                        # "未来", "未曾" are not negations in this context
                        idx += 1
                        continue
                    if neg == "无" and idx + 1 < len(text) and text[idx + 1] in "数论所谓谓论":
                        # "无数", "无论", "无所谓" etc.
                        idx += 1
                        continue

                # Found a valid negation
                return True

        return False

    def _check_intensifier(self, text: str) -> float:
        """Check for intensifiers and return factor."""
        max_factor = 1.0
        for intensifier, factor in self.INTENSIFIERS.items():
            if intensifier in text:
                max_factor = max(max_factor, factor)
        return max_factor

    def _compute_score(
        self, bullish_count: int, bearish_count: int, intensifier_factor: float
    ) -> float:
        """Compute sentiment score from counts.

        Score range: -1 (strongly bearish) to 1 (strongly bullish)

        Args:
            bullish_count: Number of bullish keywords
            bearish_count: Number of bearish keywords
            intensifier_factor: Intensifier multiplier

        Returns:
            Sentiment score between -1 and 1
        """
        total = bullish_count + bearish_count

        if total == 0:
            return 0.0

        # Base score: difference / total, then scale
        diff = bullish_count - bearish_count
        base_score = diff / max(total, 1)

        # Apply intensifier
        score = base_score * intensifier_factor

        # Clamp to [-1, 1]
        return max(-1.0, min(1.0, score))

    def _determine_sentiment(
        self,
        score: float,
        bullish_count: int,
        bearish_count: int,
        has_negation: bool,
    ) -> tuple[SentimentType, float]:
        """Determine sentiment type and confidence from score.

        Args:
            score: Computed sentiment score
            bullish_count: Number of bullish keywords
            bearish_count: Number of bearish keywords
            has_negation: Whether negation words were found

        Returns:
            Tuple of (SentimentType, confidence)
        """
        total_keywords = bullish_count + bearish_count

        # No keywords = neutral with low confidence
        if total_keywords == 0:
            return SentimentType.NEUTRAL, 0.3

        # Confidence based on keyword count and score magnitude
        base_confidence = min(0.5 + 0.1 * total_keywords, 0.9)

        # Adjust confidence based on score clarity
        score_clarity = abs(score)
        confidence = base_confidence * (0.5 + 0.5 * score_clarity)

        # Negation reduces confidence
        if has_negation:
            confidence *= 0.7

        # Ensure confidence in valid range
        confidence = max(0.1, min(1.0, confidence))

        # Determine sentiment type
        if abs(score) < 0.1:
            sentiment = SentimentType.NEUTRAL
            confidence = min(confidence, 0.6)
        elif score > 0:
            sentiment = SentimentType.BULLISH
        else:
            sentiment = SentimentType.BEARISH

        # Very low confidence -> uncertain
        if confidence < 0.4 and sentiment != SentimentType.NEUTRAL:
            sentiment = SentimentType.UNCERTAIN

        return sentiment, confidence