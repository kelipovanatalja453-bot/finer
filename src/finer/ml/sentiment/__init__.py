"""Sentiment Analysis Module.

This module provides sentiment analysis for KOL investment content:
- Rule-based sentiment analysis (offline, fast)
- LLM-based sentiment analysis (accurate, requires API)
- Hybrid mode (rule-based first, LLM for low-confidence cases)
- Emotion Arc analysis (paragraph-level emotion tracking, inspired by zhiziX)
"""

from __future__ import annotations

from finer.ml.sentiment.analyzer import SentimentAnalyzer, SentimentMode, analyze_sentiment
from finer.ml.sentiment.rules import RuleBasedSentimentEngine
from finer.ml.sentiment.schemas import (
    SentimentType,
    SentimentResult,
    BatchSentimentResult,
    SentimentRequest,
    BatchSentimentRequest,
    SentimentConfigResponse,
)
from finer.ml.sentiment.emotion_arc import (
    EmotionType,
    EmotionIntensity,
    TransitionType,
    ParagraphEmotion,
    EmotionTransition,
    EmotionPeak,
    EmotionArc,
    EmotionArcAnalyzer,
    analyze_emotion_arc,
    get_paragraph_emotions,
    detect_emotion_transitions,
)

# Legacy aliases for backward compatibility
RuleBasedSentimentAnalyzer = RuleBasedSentimentEngine
SentimentBatchResult = BatchSentimentResult
batch_analyze_sentiment = SentimentAnalyzer.batch_analyze

__all__ = [
    # Analyzer (rule/llm/hybrid modes)
    "SentimentAnalyzer",
    "SentimentMode",
    "analyze_sentiment",
    # Rule engine
    "RuleBasedSentimentEngine",
    # Schemas
    "SentimentType",
    "SentimentResult",
    "BatchSentimentResult",
    "SentimentRequest",
    "BatchSentimentRequest",
    "SentimentConfigResponse",
    # Legacy compatibility
    "RuleBasedSentimentAnalyzer",
    "SentimentBatchResult",
    "batch_analyze_sentiment",
    # Emotion Arc (zhiziX-inspired)
    "EmotionType",
    "EmotionIntensity",
    "TransitionType",
    "ParagraphEmotion",
    "EmotionTransition",
    "EmotionPeak",
    "EmotionArc",
    "EmotionArcAnalyzer",
    "analyze_emotion_arc",
    "get_paragraph_emotions",
    "detect_emotion_transitions",
]
