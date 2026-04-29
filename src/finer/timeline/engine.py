"""F7 Timeline Engine — 时间线构建、查询与对比的核心逻辑.

职责：
1. 按 KOL 构建 TradeAction 时间线（时间倒序）
2. 支持按标的、方向、日期范围、置信度、验证状态过滤
3. 多 KOL 对比（共同标的、方向一致性）

依赖：
- services.repository.TradeActionRepository: TradeAction 数据查询
- schemas 中的 TradeAction, MarketDataSnapshot 等

禁止：
- 不直接读写文件系统（通过 Repository）
- 不调用 LLM 或外部 API
- 不依赖其他层模块（如 ingestion, extraction）
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Dict, List, Optional, Set

from finer.schemas.trade_action import TradeAction, TradeDirection, ValidationStatus
from finer.schemas.enriched_event import MarketDataSnapshot
from finer.services.repository import TradeActionRepository
from finer.timeline.models import (
    TimelineEntry,
    TimelineSummary,
    KOLTimeline,
    TimelineFilter,
    KOLComparison,
    KOLComparisonEntry,
)

logger = logging.getLogger(__name__)


class TimelineEngine:
    """KOL 时间线引擎.

    使用 TradeActionRepository 获取数据，构建和查询时间线。
    无状态设计，所有数据通过 Repository 获取。
    """

    def __init__(self, repo: TradeActionRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def build_timeline(self, kol_id: str) -> KOLTimeline:
        """构建指定 KOL 的完整时间线.

        Args:
            kol_id: KOL 唯一标识

        Returns:
            KOLTimeline，包含所有条目（时间倒序）和统计摘要
        """
        actions = self._repo.query_by_kol(kol_id)
        entries = self._actions_to_entries(actions)
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        summary = self._compute_summary(entries)

        kol_name = self._resolve_kol_name(kol_id, actions)

        return KOLTimeline(
            kol_id=kol_id,
            kol_name=kol_name,
            entries=entries,
            summary=summary,
        )

    def query_timeline(
        self,
        kol_id: str,
        filters: TimelineFilter,
    ) -> KOLTimeline:
        """按过滤条件查询 KOL 时间线.

        Args:
            kol_id: KOL 唯一标识
            filters: 过滤条件

        Returns:
            过滤后的 KOLTimeline
        """
        actions = self._repo.query_by_kol(kol_id)
        entries = self._actions_to_entries(actions)
        entries = self._apply_filters(entries, filters)
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        # 应用 limit
        if len(entries) > filters.limit:
            entries = entries[: filters.limit]

        summary = self._compute_summary(entries)
        kol_name = self._resolve_kol_name(kol_id, actions)

        return KOLTimeline(
            kol_id=kol_id,
            kol_name=kol_name,
            entries=entries,
            summary=summary,
        )

    def compare_kols(self, kol_ids: List[str]) -> KOLComparison:
        """对比多个 KOL 的时间线.

        计算共同覆盖标的、方向一致性等对比指标。
        使用批量查询避免 N+1 问题。

        Args:
            kol_ids: 要对比的 KOL ID 列表

        Returns:
            KOLComparison 对比结果
        """
        if len(kol_ids) < 2:
            raise ValueError("compare_kols requires at least 2 KOL IDs")

        # Batch fetch all KOL actions in one query (fixes N+1)
        actions_by_kol = self._repo.query_by_kols(kol_ids, limit_per_kol=500)

        kol_entries: List[KOLComparisonEntry] = []
        all_ticker_sets: List[Set[str]] = []
        all_direction_vectors: List[Dict[str, int]] = []

        for kol_id in kol_ids:
            actions = actions_by_kol.get(kol_id, [])
            entries = self._actions_to_entries(actions)
            summary = self._compute_summary(entries)

            # 标的频率统计
            ticker_counter: Counter = Counter()
            direction_counts: Dict[str, int] = {
                "bullish": 0,
                "bearish": 0,
                "neutral": 0,
            }

            for entry in entries:
                ticker = entry.action.target.ticker_normalized or entry.action.target.ticker
                if ticker:
                    ticker_counter[ticker] += 1
                direction = entry.action.direction
                if direction == TradeDirection.BULLISH:
                    direction_counts["bullish"] += 1
                elif direction == TradeDirection.BEARISH:
                    direction_counts["bearish"] += 1
                elif direction == TradeDirection.NEUTRAL:
                    direction_counts["neutral"] += 1

            top_tickers = [t for t, _ in ticker_counter.most_common(5)]
            kol_name = self._resolve_kol_name(kol_id, actions)

            kol_entries.append(
                KOLComparisonEntry(
                    kol_id=kol_id,
                    kol_name=kol_name,
                    summary=summary,
                    top_tickers=top_tickers,
                )
            )

            all_ticker_sets.append(set(ticker_counter.keys()))
            all_direction_vectors.append(direction_counts)

        # 共同标的
        shared_tickers = sorted(set.intersection(*all_ticker_sets)) if all_ticker_sets else []

        # 方向一致性：计算各 KOL 方向分布的余弦相似度均值
        direction_overlap = self._compute_direction_overlap(all_direction_vectors)

        return KOLComparison(
            kol_entries=kol_entries,
            shared_tickers=shared_tickers,
            direction_overlap=direction_overlap,
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _actions_to_entries(actions: List[TradeAction]) -> List[TimelineEntry]:
        """将 TradeAction 列表转换为 TimelineEntry 列表."""
        entries: List[TimelineEntry] = []
        for action in actions:
            ts = action.timestamp

            # 从 TradeAction.enrichment (MarketEnrichment) 构造 MarketDataSnapshot
            market_ctx: Optional[MarketDataSnapshot] = None
            if action.enrichment is not None:
                ticker = (
                    action.target.ticker_normalized
                    or action.target.ticker
                )
                market_ctx = MarketDataSnapshot(
                    ticker=ticker,
                    current_price=action.enrichment.market_price_at_time,
                    volume=int(action.enrichment.volume_at_time)
                    if action.enrichment.volume_at_time is not None
                    else None,
                    high_52wk=action.enrichment.high_52wk,
                    low_52wk=action.enrichment.low_52wk,
                    pe_ratio=action.enrichment.pe_ratio,
                    market_cap=action.enrichment.market_cap,
                    avg_iv=action.enrichment.implied_volatility,
                    timestamp=action.enrichment.data_timestamp or ts,
                    source=action.enrichment.data_source,
                    is_complete=len(action.enrichment.missing_fields) == 0,
                    missing_fields=action.enrichment.missing_fields,
                )

            entries.append(
                TimelineEntry(
                    timestamp=ts,
                    action=action,
                    market_context=market_ctx,
                    validation_status=action.validation_status,
                )
            )
        return entries

    @staticmethod
    def _apply_filters(
        entries: List[TimelineEntry],
        filters: TimelineFilter,
    ) -> List[TimelineEntry]:
        """对 TimelineEntry 列表应用过滤条件."""
        result = entries

        if filters.tickers:
            ticker_set = set(filters.tickers)
            result = [
                e for e in result
                if (
                    e.action.target.ticker_normalized in ticker_set
                    or e.action.target.ticker in ticker_set
                )
            ]

        if filters.directions:
            direction_set = set(filters.directions)
            result = [e for e in result if e.action.direction in direction_set]

        if filters.date_start:
            result = [e for e in result if e.timestamp >= filters.date_start]

        if filters.date_end:
            result = [e for e in result if e.timestamp <= filters.date_end]

        if filters.validation_status:
            status_set = set(filters.validation_status)
            result = [e for e in result if e.validation_status in status_set]

        if filters.min_confidence is not None:
            result = [
                e for e in result
                if e.action.confidence is not None
                and e.action.confidence >= filters.min_confidence
            ]

        return result

    @staticmethod
    def _compute_summary(entries: List[TimelineEntry]) -> TimelineSummary:
        """从 TimelineEntry 列表计算统计摘要."""
        if not entries:
            return TimelineSummary()

        total = len(entries)
        bullish = 0
        bearish = 0
        neutral = 0
        watchlist = 0
        risk_warning = 0
        ticker_set: Set[str] = set()
        confidence_sum = 0.0
        confidence_count = 0
        verified = 0
        pending = 0

        for entry in entries:
            action = entry.action
            direction = action.direction

            if direction == TradeDirection.BULLISH:
                bullish += 1
            elif direction == TradeDirection.BEARISH:
                bearish += 1
            elif direction == TradeDirection.NEUTRAL:
                neutral += 1
            elif direction == TradeDirection.WATCHLIST:
                watchlist += 1
            elif direction == TradeDirection.RISK_WARNING:
                risk_warning += 1

            ticker = action.target.ticker_normalized or action.target.ticker
            if ticker:
                ticker_set.add(ticker)

            if action.confidence is not None:
                confidence_sum += action.confidence
                confidence_count += 1

            if entry.validation_status == ValidationStatus.VERIFIED:
                verified += 1
            elif entry.validation_status == ValidationStatus.PENDING:
                pending += 1

        timestamps = [e.timestamp for e in entries]
        date_min = min(timestamps)
        date_max = max(timestamps)

        avg_confidence = confidence_sum / confidence_count if confidence_count > 0 else 0.0

        return TimelineSummary(
            total_actions=total,
            bullish_count=bullish,
            bearish_count=bearish,
            neutral_count=neutral,
            watchlist_count=watchlist,
            risk_warning_count=risk_warning,
            tickers_covered=sorted(ticker_set),
            date_range=(date_min, date_max),
            avg_confidence=round(avg_confidence, 4),
            verified_count=verified,
            pending_count=pending,
        )

    @staticmethod
    def _resolve_kol_name(kol_id: str, actions: List[TradeAction]) -> Optional[str]:
        """从 TradeAction 中提取 KOL 名称.

        TradeAction 不直接存储 creator 名称，
        尝试从 source.content_url 或 metadata 中提取，否则返回 None。
        """
        for action in actions:
            # 优先从 metadata 中获取
            if action.metadata and "creator_name" in action.metadata:
                return action.metadata["creator_name"]
        return None

    @staticmethod
    def _compute_direction_overlap(
        vectors: List[Dict[str, int]],
    ) -> float:
        """计算多个 KOL 方向分布的平均余弦相似度.

        将每个 KOL 的方向统计转为向量 [bullish, bearish, neutral]，
        计算所有两两组合的余弦相似度，取均值。
        """
        if len(vectors) < 2:
            return 0.0

        def to_vec(d: Dict[str, int]) -> List[float]:
            return [
                float(d.get("bullish", 0)),
                float(d.get("bearish", 0)),
                float(d.get("neutral", 0)),
            ]

        def cosine_sim(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        vecs = [to_vec(v) for v in vectors]
        sims: List[float] = []

        for i in range(len(vecs)):
            for j in range(i + 1, len(vecs)):
                sims.append(cosine_sim(vecs[i], vecs[j]))

        return round(sum(sims) / len(sims), 4) if sims else 0.0
