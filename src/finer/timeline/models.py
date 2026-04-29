"""Timeline 数据模型.

定义 F7 时间线层的 Pydantic 模型，与现有 schema 体系对齐。
所有时间线相关的数据结构只在此文件定义，不重复定义在其他模块。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field, ConfigDict

from finer.schemas.trade_action import TradeAction, TradeDirection, ValidationStatus
from finer.schemas.enriched_event import MarketDataSnapshot


class TimelineEntry(BaseModel):
    """时间线中的单条记录，包装 TradeAction 及其市场上下文."""

    model_config = ConfigDict(strict=True)

    timestamp: datetime = Field(
        ...,
        description="操作时间戳，用于排序",
    )
    action: TradeAction = Field(
        ...,
        description="关联的 TradeAction",
    )
    market_context: Optional[MarketDataSnapshot] = Field(
        None,
        description="操作时的市场快照（可选）",
    )
    validation_status: ValidationStatus = Field(
        ValidationStatus.PENDING,
        description="验证状态",
    )


class TimelineSummary(BaseModel):
    """KOL 时间线的统计摘要."""

    model_config = ConfigDict(strict=True)

    total_actions: int = Field(
        0,
        ge=0,
        description="总操作数",
    )
    bullish_count: int = Field(
        0,
        ge=0,
        description="看多操作数",
    )
    bearish_count: int = Field(
        0,
        ge=0,
        description="看空操作数",
    )
    neutral_count: int = Field(
        0,
        ge=0,
        description="中性操作数",
    )
    watchlist_count: int = Field(
        0,
        ge=0,
        description="观察列表操作数",
    )
    risk_warning_count: int = Field(
        0,
        ge=0,
        description="风险预警操作数",
    )
    tickers_covered: List[str] = Field(
        default_factory=list,
        description="覆盖的标的列表",
    )
    date_range: Optional[Tuple[datetime, datetime]] = Field(
        None,
        description="时间范围 (最早, 最新)",
    )
    avg_confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="平均置信度",
    )
    verified_count: int = Field(
        0,
        ge=0,
        description="已验证操作数",
    )
    pending_count: int = Field(
        0,
        ge=0,
        description="待验证操作数",
    )


class KOLTimeline(BaseModel):
    """KOL 的时间线，包含所有操作条目和统计摘要."""

    model_config = ConfigDict(strict=True)

    kol_id: str = Field(
        ...,
        description="KOL 唯一标识",
    )
    kol_name: Optional[str] = Field(
        None,
        description="KOL 显示名称",
    )
    entries: List[TimelineEntry] = Field(
        default_factory=list,
        description="时间线条目（时间倒序）",
    )
    summary: TimelineSummary = Field(
        default_factory=TimelineSummary,
        description="统计摘要",
    )


class TimelineFilter(BaseModel):
    """时间线查询过滤条件."""

    model_config = ConfigDict(strict=True)

    tickers: Optional[List[str]] = Field(
        None,
        description="按标的过滤（标准化 ticker 列表）",
    )
    directions: Optional[List[TradeDirection]] = Field(
        None,
        description="按方向过滤",
    )
    date_start: Optional[datetime] = Field(
        None,
        description="起始日期",
    )
    date_end: Optional[datetime] = Field(
        None,
        description="截止日期",
    )
    validation_status: Optional[List[ValidationStatus]] = Field(
        None,
        description="按验证状态过滤",
    )
    min_confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="最低置信度",
    )
    limit: int = Field(
        200,
        ge=1,
        le=1000,
        description="最大返回条目数",
    )


class KOLComparisonEntry(BaseModel):
    """KOL 对比中的单个 KOL 摘要."""

    model_config = ConfigDict(strict=True)

    kol_id: str = Field(..., description="KOL ID")
    kol_name: Optional[str] = Field(None, description="KOL 名称")
    summary: TimelineSummary = Field(..., description="统计摘要")
    top_tickers: List[str] = Field(
        default_factory=list,
        description="最常提及的标的（前5）",
    )


class KOLComparison(BaseModel):
    """多 KOL 对比结果."""

    model_config = ConfigDict(strict=True)

    kol_entries: List[KOLComparisonEntry] = Field(
        default_factory=list,
        description="各 KOL 的对比数据",
    )
    shared_tickers: List[str] = Field(
        default_factory=list,
        description="共同覆盖的标的",
    )
    direction_overlap: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="方向一致性（0=完全不一致，1=完全一致）",
    )
