"""L4 Aggregation Layer — 实体消歧 + 上下文聚合 + 摘要生成 + 市场预注入.

L4 层位于 L3 解析和 L5 抽取之间，负责：
1. 实体消歧与链接：将不同表述的同一实体统一化
2. 跨内容上下文聚合：同一标的在不同内容中的观点汇总
3. 结构化摘要生成：为 L5 提供精炼的上下文
4. 市场数据预注入：当前价格、52周范围等，供 L5 判断 trigger

数据流：
L3 解析产物 (clean_segments) → L4 聚合 → L5 抽取
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from finer.entity_registry import ENTITY_REGISTRY

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

@dataclass
class EntityReference:
    """实体引用，包含原始表述和标准化结果."""
    raw_text: str  # 原始表述，如 "腾讯"、"大企鹅"
    normalized: str  # 标准化代码，如 "0700.HK"
    entity_type: str  # ticker, company, index, concept
    confidence: float = 1.0
    market: Optional[str] = None  # US, HK, CN, CRYPTO


@dataclass
class AggregatedContext:
    """L4 聚合后的上下文，供 L5 抽取使用."""
    content_id: str
    clean_text: str
    entities: List[EntityReference]
    summary: Optional[str] = None
    market_data: Optional[Dict[str, Any]] = None
    cross_references: List[str] = field(default_factory=list)  # 关联内容 ID
    timestamp: Optional[datetime] = None
    author: Optional[str] = None
    source_platform: Optional[str] = None


@dataclass
class AggregationResult:
    """L4 聚合结果."""
    success: bool
    contexts: List[AggregatedContext]
    entity_index: Dict[str, List[str]]  # normalized_entity -> content_ids
    error: Optional[str] = None


# ============================================
# Entity Linker
# ============================================

class EntityLinker:
    """实体消歧与链接.

    将不同表述的同一实体统一化：
    - "腾讯" / "TCEHY" / "0700.HK" → "0700.HK"
    - "大A" / "A股" / "上证" → "000001.SH"
    """

    # 已知实体映射表 — uses unified entity registry
    KNOWN_ENTITIES = ENTITY_REGISTRY

    # Ticker 格式正则
    TICKER_PATTERNS = [
        # 美股：全大写字母，1-5位
        (r"\b([A-Z]{1,5})\b", "US"),
        # 港股：4位数字 + .HK
        (r"\b(\d{4})\.HK\b", "HK"),
        # A股：6位数字 + .SH/.SZ
        (r"\b(\d{6})\.(SH|SZ)\b", "CN"),
        # 加密货币：大写字母
        (r"\b(BTC|ETH|SOL|DOGE|XRP|ADA|AVAX|DOT|MATIC)\b", "CRYPTO"),
    ]

    def __init__(self, custom_entities: Optional[Dict[str, Tuple[str, str, str]]] = None):
        """初始化实体链接器.

        Args:
            custom_entities: 自定义实体映射，格式同 KNOWN_ENTITIES
        """
        self.entities = {**self.KNOWN_ENTITIES}
        if custom_entities:
            self.entities.update(custom_entities)

    def resolve(self, text: str) -> List[EntityReference]:
        """从文本中识别并消歧实体.

        Args:
            text: 输入文本

        Returns:
            识别到的实体列表（已消歧）
        """
        references = []
        seen = set()

        # 1. 先匹配已知实体（优先级最高）
        for raw_text, (normalized, market, entity_type) in self.entities.items():
            if raw_text in text:
                key = (normalized, raw_text)
                if key not in seen:
                    seen.add(key)
                    references.append(EntityReference(
                        raw_text=raw_text,
                        normalized=normalized,
                        entity_type=entity_type,
                        confidence=1.0,
                        market=market,
                    ))

        # 2. 匹配标准 ticker 格式
        for pattern, market in self.TICKER_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                ticker = match if isinstance(match, str) else match[0]
                # 检查是否已被已知实体覆盖
                if ticker in self.entities:
                    continue
                key = (ticker, ticker)
                if key not in seen:
                    seen.add(key)
                    references.append(EntityReference(
                        raw_text=ticker,
                        normalized=ticker,
                        entity_type="ticker",
                        confidence=0.8,
                        market=market,
                    ))

        return references

    def normalize_ticker(self, raw_ticker: str) -> Optional[str]:
        """将原始 ticker 标准化.

        Args:
            raw_ticker: 原始 ticker 或公司名

        Returns:
            标准化后的 ticker，如无法识别返回 None
        """
        if raw_ticker in self.entities:
            return self.entities[raw_ticker][0]
        # 检查是否已经是标准格式
        if re.match(r"^[A-Z]{1,5}$", raw_ticker):
            return raw_ticker
        if re.match(r"^\d{4}\.HK$", raw_ticker):
            return raw_ticker
        if re.match(r"^\d{6}\.(SH|SZ)$", raw_ticker):
            return raw_ticker
        return None


# ============================================
# Context Aggregator
# ============================================

class ContextAggregator:
    """跨内容上下文聚合.

    将同一标的在不同内容中的观点汇总，构建时间线。
    支持 SQLite 持久化，重启后可恢复。
    """

    def __init__(self, storage: Optional["AggregationStorage"] = None):
        """初始化聚合器.

        Args:
            storage: 持久化存储实例，为 None 则使用纯内存模式
        """
        self.storage = storage
        self.entity_index: Dict[str, List[str]] = {}  # normalized_entity -> content_ids
        self.content_store: Dict[str, AggregatedContext] = {}

        # 如果有存储，从数据库加载已有数据
        if self.storage:
            self._load_from_storage()

    def _load_from_storage(self) -> None:
        """从存储加载数据（冷启动恢复）."""
        if not self.storage:
            return

        try:
            self.entity_index = self.storage.load_entity_index()
            self.content_store = self.storage.load_all_contexts()
            logger.info(
                f"Loaded {len(self.content_store)} contexts, "
                f"{len(self.entity_index)} entities from storage"
            )
        except Exception as e:
            logger.warning(f"Failed to load from storage: {e}, starting fresh")
            self.entity_index = {}
            self.content_store = {}

    def add_context(self, context: AggregatedContext) -> None:
        """添加上下文到聚合器.

        Args:
            context: L4 聚合后的上下文
        """
        self.content_store[context.content_id] = context

        # 更新实体索引
        for entity in context.entities:
            if entity.normalized not in self.entity_index:
                self.entity_index[entity.normalized] = []
            if context.content_id not in self.entity_index[entity.normalized]:
                self.entity_index[entity.normalized].append(context.content_id)

        # 持久化
        if self.storage:
            try:
                self.storage.save_context(context)
                for entity in context.entities:
                    self.storage.update_entity_index(entity.normalized, context.content_id)
            except Exception as e:
                logger.warning(f"Failed to persist context {context.content_id}: {e}")

    def get_related_contents(self, entity: str) -> List[AggregatedContext]:
        """获取与某实体相关的所有内容.

        Args:
            entity: 标准化后的实体

        Returns:
            相关上下文列表
        """
        content_ids = self.entity_index.get(entity, [])
        return [self.content_store[cid] for cid in content_ids if cid in self.content_store]

    def build_entity_timeline(self, entity: str) -> List[Dict[str, Any]]:
        """构建某实体的观点时间线.

        Args:
            entity: 标准化后的实体

        Returns:
            按时间排序的观点列表
        """
        contexts = self.get_related_contents(entity)
        timeline = []

        for ctx in contexts:
            if ctx.timestamp:
                timeline.append({
                    "content_id": ctx.content_id,
                    "timestamp": ctx.timestamp.isoformat(),
                    "summary": ctx.summary,
                    "author": ctx.author,
                    "source": ctx.source_platform,
                })

        # 按时间排序
        timeline.sort(key=lambda x: x["timestamp"], reverse=True)
        return timeline


# ============================================
# Market Pre-Injector
# ============================================

class MarketPreInjector:
    """市场数据预注入.

    为 L5 抽取提供市场上下文：
    - 当前价格
    - 52周最高/最低
    - PE、市值等基本面数据
    """

    def __init__(self, finance_client=None):
        """初始化市场数据注入器.

        Args:
            finance_client: Finance-Skills 客户端（可选）
        """
        self.finance_client = finance_client
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def inject(self, context: AggregatedContext) -> AggregatedContext:
        """为上下文注入市场数据.

        Args:
            context: L4 聚合后的上下文

        Returns:
            注入市场数据后的上下文
        """
        if not self.finance_client:
            return context

        # 获取主要实体
        primary_entity = None
        for entity in context.entities:
            if entity.entity_type == "ticker":
                primary_entity = entity.normalized
                break

        if not primary_entity:
            return context

        # 检查缓存
        if primary_entity in self._cache:
            context.market_data = self._cache[primary_entity]
            return context

        try:
            # 获取市场数据
            market_data = await self.finance_client.get_market_data(primary_entity)

            if market_data:
                context.market_data = {
                    "ticker": primary_entity,
                    "current_price": market_data.get("currentPrice"),
                    "high_52wk": market_data.get("fiftyTwoWeekHigh"),
                    "low_52wk": market_data.get("fiftyTwoWeekLow"),
                    "pe_ratio": market_data.get("trailingPE"),
                    "market_cap": market_data.get("marketCap"),
                    "volume_avg": market_data.get("averageVolume"),
                    "data_timestamp": datetime.now().isoformat(),
                }
                self._cache[primary_entity] = context.market_data

        except Exception as e:
            logger.warning(f"Failed to inject market data for {primary_entity}: {e}")

        return context


# ============================================
# L4 Aggregation Layer
# ============================================

class L4AggregationLayer:
    """L4 聚合层主类.

    整合实体消歧、上下文聚合、摘要生成、市场预注入。
    """

    def __init__(
        self,
        finance_client=None,
        summary_generator=None,
        custom_entities: Optional[Dict[str, Tuple[str, str, str]]] = None,
        storage: Optional["AggregationStorage"] = None,
    ):
        """初始化 L4 聚合层.

        Args:
            finance_client: Finance-Skills 客户端
            summary_generator: 摘要生成器
            custom_entities: 自定义实体映射
            storage: 持久化存储实例
        """
        self.entity_linker = EntityLinker(custom_entities)
        self.context_aggregator = ContextAggregator(storage=storage)
        self.market_injector = MarketPreInjector(finance_client)
        self.summary_generator = summary_generator

    def process_text(
        self,
        text: str,
        content_id: str,
        timestamp: Optional[datetime] = None,
        author: Optional[str] = None,
        source_platform: Optional[str] = None,
    ) -> AggregatedContext:
        """处理单个文本内容.

        Args:
            text: 清洗后的文本
            content_id: 内容 ID
            timestamp: 时间戳
            author: 作者
            source_platform: 来源平台

        Returns:
            聚合后的上下文
        """
        # 1. 实体消歧
        entities = self.entity_linker.resolve(text)

        # 2. 构建上下文
        context = AggregatedContext(
            content_id=content_id,
            clean_text=text,
            entities=entities,
            timestamp=timestamp,
            author=author,
            source_platform=source_platform,
        )

        # 3. 生成摘要（如果生成器可用）
        if self.summary_generator:
            try:
                summary_result = self.summary_generator.summarize_text(text)
                context.summary = summary_result.get("summary")
            except Exception as e:
                logger.warning(f"Summary generation failed: {e}")

        # 4. 添加到聚合器
        self.context_aggregator.add_context(context)

        return context

    async def process_with_market_data(
        self,
        text: str,
        content_id: str,
        timestamp: Optional[datetime] = None,
        author: Optional[str] = None,
        source_platform: Optional[str] = None,
    ) -> AggregatedContext:
        """处理文本并注入市场数据.

        Args:
            text: 清洗后的文本
            content_id: 内容 ID
            timestamp: 时间戳
            author: 作者
            source_platform: 来源平台

        Returns:
            聚合后并注入市场数据的上下文
        """
        context = self.process_text(text, content_id, timestamp, author, source_platform)
        context = await self.market_injector.inject(context)
        return context

    def get_entity_index(self) -> Dict[str, List[str]]:
        """获取实体索引.

        Returns:
            实体 -> 内容 ID 列表的映射
        """
        return self.context_aggregator.entity_index

    def get_entity_timeline(self, entity: str) -> List[Dict[str, Any]]:
        """获取某实体的观点时间线.

        Args:
            entity: 标准化后的实体

        Returns:
            按时间排序的观点列表
        """
        return self.context_aggregator.build_entity_timeline(entity)


# ============================================
# Convenience Functions
# ============================================

def create_l4_layer(
    finance_client=None,
    summary_generator=None,
    storage: Optional["AggregationStorage"] = None,
    db_path: Optional[Path] = None,
) -> L4AggregationLayer:
    """创建 L4 聚合层实例.

    Args:
        finance_client: Finance-Skills 客户端
        summary_generator: 摘要生成器
        storage: 持久化存储实例（优先使用）
        db_path: 数据库路径，若提供则自动创建 storage

    Returns:
        L4AggregationLayer 实例
    """
    # 如果提供了 db_path 但没有 storage，自动创建
    if storage is None and db_path is not None:
        from finer.aggregation.storage import AggregationStorage
        storage = AggregationStorage(db_path)

    return L4AggregationLayer(
        finance_client=finance_client,
        summary_generator=summary_generator,
        storage=storage,
    )
