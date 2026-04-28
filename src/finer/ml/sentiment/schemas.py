"""Sentiment Analysis Schemas.

Pydantic models for sentiment analysis results.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SentimentType(str, Enum):
    """Sentiment type enum."""

    BULLISH = "bullish"  # 看多
    BEARISH = "bearish"  # 看空
    NEUTRAL = "neutral"  # 中性
    UNCERTAIN = "uncertain"  # 不确定


class SentimentResult(BaseModel):
    """Sentiment analysis result for a single text."""

    text: str = Field(description="原始文本")
    sentiment: SentimentType = Field(description="情绪类型")
    score: float = Field(ge=-1.0, le=1.0, description="情绪分数 (-1 到 1, 负数看空，正数看多)")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    market_context: Optional[Dict[str, Any]] = Field(
        default=None, description="市场上下文（可选）"
    )
    reasoning: Optional[str] = Field(default=None, description="分析推理说明（LLM模式）")


class BatchSentimentResult(BaseModel):
    """Batch sentiment analysis result."""

    results: List[SentimentResult] = Field(description="各条文本的分析结果")
    summary: Dict[str, int] = Field(description="各情绪类型的数量统计")
    average_score: float = Field(description="平均情绪分数")


class SentimentRequest(BaseModel):
    """Request for single text sentiment analysis."""

    text: str = Field(description="待分析文本")
    context: Optional[Dict[str, Any]] = Field(default=None, description="市场上下文")
    mode: str = Field(default="rule", description="分析模式: rule, llm, hybrid")


class BatchSentimentRequest(BaseModel):
    """Request for batch sentiment analysis."""

    texts: List[str] = Field(description="待分析文本列表")
    context: Optional[Dict[str, Any]] = Field(default=None, description="市场上下文")
    mode: str = Field(default="rule", description="分析模式: rule, llm, hybrid")


class SentimentConfigResponse(BaseModel):
    """Response for sentiment configuration."""

    available_modes: List[str] = Field(description="可用分析模式")
    default_mode: str = Field(description="默认分析模式")
    supported_languages: List[str] = Field(description="支持的语言")
    llm_available: bool = Field(description="LLM 是否可用")