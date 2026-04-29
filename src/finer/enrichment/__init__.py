"""F2 Anchor — Topic splitting, entity extraction, content linking, and market data.

This module provides the core functionality for the F2 Anchor stage:
1. Topic Splitter: Split long chat transcripts into topics
2. Entity Extractor: Extract tickers, companies, events from content
3. Content Linker: Build relationships between content pieces
4. Market Context Enricher: Enrich events with market data (P0)
5. Sentiment Fusion Enricher: Multi-source sentiment aggregation (P1)
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Dict

import httpx

from finer.model_config import get_text_registry, ModelProvider
from finer.llm import LLMClient
from finer.entity_registry import ENTITY_REGISTRY
from finer.enrichment.market_context import (
    MarketContextEnricher,
    PriceRangeValidator,
    EnrichmentStats,
    get_market_enricher,
)
from finer.enrichment.sentiment_fusion import (
    SentimentFusionEnricher,
    SentimentFusionStats,
    get_sentiment_enricher,
)

logger = logging.getLogger(__name__)

# Prompt for topic splitting
TOPIC_SPLIT_PROMPT = """分析以下聊天记录，按话题进行分割。对于每个话题，请提供：
1. 话题标题（简短，5-10字）
2. 涉及的主要标的/公司（如有）
3. 时间范围
4. 核心观点摘要（2-3句话）

聊天记录：
{content}

请以JSON格式输出，格式如下：
{{
  "topics": [
    {{
      "title": "话题标题",
      "tickers": ["标的1", "标的2"],
      "companies": ["公司1", "公司2"],
      "time_range": {{"start": "时间", "end": "时间"}},
      "summary": "核心观点摘要",
      "start_line": 起始行号,
      "end_line": 结束行号
    }}
  ]
}}
"""

# Prompt for entity extraction
ENTITY_EXTRACT_PROMPT = """从以下内容中提取关键实体：

内容：
{content}

请提取以下类型的实体并以JSON格式输出：
{{
  "tickers": ["股票代码或简称"],
  "companies": ["公司名称"],
  "people": ["人物名称"],
  "events": ["事件名称"],
  "concepts": ["核心概念/主题"],
  "metrics": ["关键指标/数据"]
}}
"""


@dataclass
class Topic:
    """Represents a split topic from content."""
    title: str
    tickers: List[str] = field(default_factory=list)
    companies: List[str] = field(default_factory=list)
    time_range: Dict[str, str] = field(default_factory=dict)
    summary: str = ""
    start_line: int = 0
    end_line: int = 0
    content: str = ""


@dataclass
class EntityExtraction:
    """Extracted entities from content."""
    tickers: List[str] = field(default_factory=list)
    companies: List[str] = field(default_factory=list)
    people: List[str] = field(default_factory=list)
    events: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)


class TopicSplitter:
    """Split long content into topics using LLM."""

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient.auto()

    def split(self, content: str, min_lines: int = 50) -> List[Topic]:
        """Split content into topics."""
        # Skip short content
        lines = content.split("\n")
        if len(lines) < min_lines:
            logger.debug(f"Content too short ({len(lines)} lines), skipping split")
            return []

        prompt = TOPIC_SPLIT_PROMPT.format(content=content[:8000])  # Limit context
        response = self.llm.chat_prompt(prompt)

        if not response:
            return []

        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                topics = []
                for t in data.get("topics", []):
                    topic = Topic(
                        title=t.get("title", "未命名话题"),
                        tickers=t.get("tickers", []),
                        companies=t.get("companies", []),
                        time_range=t.get("time_range", {}),
                        summary=t.get("summary", ""),
                        start_line=t.get("start_line", 0),
                        end_line=t.get("end_line", 0),
                    )
                    # Extract content for this topic
                    if topic.start_line and topic.end_line:
                        topic.content = "\n".join(lines[topic.start_line:topic.end_line])
                    topics.append(topic)
                return topics
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse topic split response: {e}")

        return []


class EntityExtractor:
    """Extract entities from content using LLM."""

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient.auto()

        # Common stock tickers — unified entity registry (name → ticker)
        self.known_tickers = {name: entry[0] for name, entry in ENTITY_REGISTRY.items()}

    def extract(self, content: str) -> EntityExtraction:
        """Extract entities from content."""
        # First, do quick regex-based extraction for known patterns
        extraction = EntityExtraction()

        # Extract known tickers
        for name, ticker in self.known_tickers.items():
            if name in content:
                if ticker not in extraction.tickers:
                    extraction.tickers.append(ticker)
                if name not in extraction.companies:
                    extraction.companies.append(name)

        # Use LLM for more sophisticated extraction
        prompt = ENTITY_EXTRACT_PROMPT.format(content=content[:4000])
        response = self.llm.chat_prompt(prompt)

        if response:
            try:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    data = json.loads(json_match.group())
                    # Merge with regex results, with validation
                    for ticker in data.get("tickers", []):
                        # Validate ticker format: must be uppercase letters/numbers, 1-6 chars
                        # Chinese characters are NOT valid tickers
                        if self._is_valid_ticker(ticker):
                            if ticker not in extraction.tickers:
                                extraction.tickers.append(ticker)
                        else:
                            # Invalid ticker format - treat as company name
                            if ticker not in extraction.companies:
                                extraction.companies.append(ticker)
                    for company in data.get("companies", []):
                        if company not in extraction.companies:
                            extraction.companies.append(company)
                    # Filter events to only financial-related
                    extraction.people = data.get("people", [])
                    extraction.events = [e for e in data.get("events", []) if self._is_financial_event(e)]
                    extraction.concepts = [c for c in data.get("concepts", []) if self._is_financial_concept(c)]
                    extraction.metrics = data.get("metrics", [])
            except json.JSONDecodeError:
                pass

        return extraction

    def _is_valid_ticker(self, text: str) -> bool:
        """Check if text is a valid ticker format.

        Valid tickers:
        - US stocks: 1-5 uppercase letters (AAPL, NVDA, TSLA)
        - HK stocks: 4 digits + .HK (0700.HK, 9988.HK)
        - CN stocks: 6 digits + .SH/.SZ (600519.SH, 000001.SZ)
        - Crypto: 3-5 uppercase letters (BTC, ETH, SOL)
        """
        if not text:
            return False
        # Chinese characters are never valid tickers
        if re.search(r'[一-鿿]', text):
            return False
        # US stock pattern
        if re.match(r'^[A-Z]{1,5}$', text):
            return True
        # HK stock pattern
        if re.match(r'^\d{4}\.HK$', text):
            return True
        # CN stock pattern
        if re.match(r'^\d{6}\.(SH|SZ)$', text):
            return True
        # Crypto pattern
        if re.match(r'^(BTC|ETH|SOL|DOGE|XRP|ADA|AVAX|DOT|MATIC|BNB|UNI|LINK)$', text):
            return True
        return False

    def _is_financial_event(self, text: str) -> bool:
        """Check if text is a financial event (not a random noun)."""
        # Financial event keywords
        financial_keywords = [
            '财报', '业绩', '发布', '收购', '并购', 'IPO', '上市', '退市',
            '分红', '回购', '增发', '配股', '拆股', '合并',
            '会议', '峰会', '路演', '调研', '电话会',
            '政策', '法规', '监管', '处罚', '调查',
            '评级', '上调', '下调', '目标价', '买入', '卖出',
            'earnings', 'IPO', 'M&A', 'dividend', 'buyback',
        ]
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in financial_keywords)

    def _is_financial_concept(self, text: str) -> bool:
        """Check if text is a financial concept (not a tool/platform name)."""
        # Exclude non-financial terms
        exclude_terms = [
            '网盘', '会员', '体验', '同步', 'YouTube', 'B站', 'bilibili',
            '夸克', '百度网盘', '阿里云盘', '飞书', '钉钉', '微信',
            '课程', '专题', '讲座', '训练营',
        ]
        text_lower = text.lower()
        if any(ex in text_lower for ex in exclude_terms):
            return False
        # Financial concept keywords
        financial_keywords = [
            '估值', '市盈率', '市净率', 'ROE', 'ROA', '毛利率', '净利率',
            '增长', '下滑', '反弹', '回调', '突破', '支撑', '压力',
            '多头', '空头', '做多', '做空', '持仓', '仓位',
            '板块', '行业', '赛道', '龙头', '白马', '黑马',
            '周期', '景气', '拐点', '复苏', '衰退',
            'alpha', 'beta', '夏普', '波动率', '相关性',
        ]
        return any(kw.lower() in text_lower for kw in financial_keywords)


class ContentLinker:
    """Build relationships between content pieces."""

    def __init__(self):
        self.index: Dict[str, List[str]] = {}  # entity -> content_ids
        self.content_entities: Dict[str, EntityExtraction] = {}

    def index_content(self, content_id: str, entities: EntityExtraction):
        """Index content by its entities."""
        self.content_entities[content_id] = entities

        # Build reverse index
        for ticker in entities.tickers:
            if ticker not in self.index:
                self.index[ticker] = []
            self.index[ticker].append(content_id)

        for company in entities.companies:
            key = company.lower()
            if key not in self.index:
                self.index[key] = []
            self.index[key].append(content_id)

        for event in entities.events:
            key = event.lower()
            if key not in self.index:
                self.index[key] = []
            self.index[key].append(content_id)

    def find_related(self, content_id: str) -> List[str]:
        """Find content related to the given content_id."""
        if content_id not in self.content_entities:
            return []

        entities = self.content_entities[content_id]
        related = set()

        for ticker in entities.tickers:
            related.update(self.index.get(ticker, []))

        for company in entities.companies:
            related.update(self.index.get(company.lower(), []))

        related.discard(content_id)  # Remove self
        return list(related)

    def get_by_ticker(self, ticker: str) -> List[str]:
        """Get all content related to a ticker."""
        return self.index.get(ticker.upper(), [])

    def get_by_company(self, company: str) -> List[str]:
        """Get all content related to a company."""
        return self.index.get(company.lower(), [])

    def save_index(self, path: Path):
        """Save the index to disk."""
        data = {
            "index": self.index,
            "content_entities": {
                k: {
                    "tickers": v.tickers,
                    "companies": v.companies,
                    "people": v.people,
                    "events": v.events,
                    "concepts": v.concepts,
                    "metrics": v.metrics,
                }
                for k, v in self.content_entities.items()
            }
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Saved content index to {path}")

    def load_index(self, path: Path):
        """Load the index from disk."""
        if not path.exists():
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.index = data.get("index", {})
            self.content_entities = {
                k: EntityExtraction(**v)
                for k, v in data.get("content_entities", {}).items()
            }
            logger.info(f"Loaded content index from {path}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load index: {e}")


# Global linker instance
_linker: Optional[ContentLinker] = None


def get_content_linker(root: Optional[Path] = None) -> ContentLinker:
    """Get or create the global content linker."""
    global _linker
    if _linker is None:
        _linker = ContentLinker()
        if root:
            index_path = root / "data" / "L1_enrichment" / "content_index.json"
            if index_path.exists():
                _linker.load_index(index_path)
    return _linker
