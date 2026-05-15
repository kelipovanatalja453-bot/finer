"""Opinion Timeline API — 观点时间线数据查询.

Reads real TradeAction data from F5/F6 layers via TradeActionRepository.
Returns FinerError canonical envelope when data is unavailable.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from finer.paths import DATA_ROOT
from finer.errors.codes import ErrorCode
from finer.errors.exceptions import FinerError
from finer.schemas.trade_action import (
    ActionStep as TradeActionStep,
    TradeAction,
    ValidationStatus,
)
from finer.services.repository import TradeActionRepository
from finer.services.storage import DateRange

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================
# 类型定义
# ============================================

class ActionStep(BaseModel):
    id: str
    actionType: Literal["watch", "long", "short", "close_long", "close_short"]
    triggerCondition: Optional[str] = None
    targetPriceLow: Optional[str] = None
    targetPriceHigh: Optional[str] = None


class TimelineOpinion(BaseModel):
    id: str
    timestamp: str
    ticker: str
    tickerName: Optional[str] = None
    direction: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(..., ge=0, le=1)
    verificationStatus: Literal["success", "failed", "pending"]

    # 验证结果
    priceChange: Optional[float] = None
    holdingDays: Optional[int] = None

    # 来源信息
    sourceText: str
    author: Optional[str] = None
    platform: Optional[str] = None

    # Action Chain
    actionChain: Optional[List[ActionStep]] = None

    # RLHF 状态
    rlhfStatus: Optional[Literal["pending", "reviewed", "skipped"]] = None
    rlhfRating: Optional[int] = None


class TimelineData(BaseModel):
    opinions: List[TimelineOpinion]
    total: int
    hasMore: bool
    nextCursor: Optional[str] = None


class TimelineMeta(BaseModel):
    tickers: List[str]
    kols: List[str]
    totalOpinions: int
    timeRange: Dict[str, str]


# ============================================
# Repository 单例
# ============================================

_repository: Optional[TradeActionRepository] = None


def _get_repository() -> TradeActionRepository:
    """Get or create the TradeActionRepository singleton."""
    global _repository
    if _repository is None:
        _repository = TradeActionRepository()
    return _repository


# ============================================
# TradeAction -> TimelineOpinion 转换
# ============================================

# ActionType 枚举值到前端展示值的映射
_ACTION_TYPE_MAP = {
    "long": "long",
    "short": "short",
    "close_long": "close_long",
    "close_short": "close_short",
    "buy_call": "long",
    "sell_call": "close_long",
    "buy_put": "short",
    "sell_put": "close_short",
    "hold": "watch",
    "watch": "watch",
    "buy_and_hold": "long",
}

# TradeDirection 枚举值到前端方向值的映射
_DIRECTION_MAP = {
    "bullish": "bullish",
    "bearish": "bearish",
    "neutral": "neutral",
    "watchlist": "neutral",
    "risk_warning": "bearish",
}

# ValidationStatus 枚举值到前端验证状态值的映射
_VALIDATION_STATUS_MAP = {
    "pending": "pending",
    "verified": "success",
    "failed": "failed",
    "under_review": "pending",
}


def _convert_action_step(step: TradeActionStep) -> ActionStep:
    """Convert a schema ActionStep to the API ActionStep model."""
    action_type_value = step.action_type.value
    mapped_type = _ACTION_TYPE_MAP.get(action_type_value, "watch")

    return ActionStep(
        id=f"step-{step.sequence}",
        actionType=mapped_type,  # type: ignore[arg-type]
        triggerCondition=step.trigger_condition,
        targetPriceLow=str(step.target_price_low) if step.target_price_low is not None else None,
        targetPriceHigh=str(step.target_price_high) if step.target_price_high is not None else None,
    )


def trade_action_to_opinion(action: TradeAction) -> TimelineOpinion:
    """Convert a TradeAction to a TimelineOpinion for the API response."""
    direction_value = action.direction.value
    mapped_direction = _DIRECTION_MAP.get(direction_value, "neutral")

    status_value = action.validation_status.value
    mapped_status = _VALIDATION_STATUS_MAP.get(status_value, "pending")

    # Extract price change from backtest result
    price_change = None
    holding_days = None
    if action.backtest_result:
        price_change = action.backtest_result.return_pct
        holding_days = action.backtest_result.holding_days

    # Map RLHF feedback
    rlhf_status: Optional[str] = None
    rlhf_rating: Optional[int] = None
    if action.rlhf_feedback:
        if action.rlhf_feedback.rating is not None:
            rlhf_status = "reviewed"
            rlhf_rating = action.rlhf_feedback.rating
        elif action.rlhf_feedback.is_correct is not None:
            rlhf_status = "reviewed"
        else:
            rlhf_status = "pending"

    # Convert action chain
    action_chain: Optional[List[ActionStep]] = None
    if action.action_chain:
        action_chain = [_convert_action_step(s) for s in action.action_chain]

    # Extract author from source info
    author = action.source.creator_id
    # Platform is not directly available in TradeAction; use content_url domain or leave empty
    platform = None

    # Ticker name from target info
    ticker_name = action.target.company_name

    return TimelineOpinion(
        id=action.trade_action_id,
        timestamp=action.timestamp.isoformat(),
        ticker=action.target.ticker_normalized or action.target.ticker,
        tickerName=ticker_name,
        direction=mapped_direction,  # type: ignore[arg-type]
        confidence=round(action.confidence, 2),
        verificationStatus=mapped_status,  # type: ignore[arg-type]
        priceChange=round(price_change, 2) if price_change is not None else None,
        holdingDays=holding_days,
        sourceText=action.source.evidence_text,
        author=author,
        platform=platform,
        actionChain=action_chain,
        rlhfStatus=rlhf_status,  # type: ignore[arg-type]
        rlhfRating=rlhf_rating,
    )


# ============================================
# 真实数据查询
# ============================================

def _load_actions_from_dir(action_dir: Path) -> List[TradeAction]:
    """Load all TradeAction JSON files from a directory (recursive)."""
    actions: List[TradeAction] = []
    if not action_dir.exists():
        return actions
    for file_path in action_dir.glob("**/*.action.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            actions.append(TradeAction.from_dict(data))
        except Exception as e:
            logger.warning("Failed to load TradeAction from %s: %s", file_path, e)
    return actions


def _query_real_timeline(
    ticker_list: List[str],
    direction_list: List[str],
    kol_list: List[str],
    start_time: datetime,
    end_time: datetime,
    offset: int,
    limit: int,
) -> tuple[List[TimelineOpinion], int]:
    """Query real TradeAction data and convert to TimelineOpinion list.

    Reads from F5 (via repository index) and F6 (direct file scan).
    Deduplicates by trade_action_id.

    Returns:
        Tuple of (opinions, total_count).
    """
    repo = _get_repository()

    # Collect all actions, deduplicated by trade_action_id
    seen_ids: set[str] = set()
    all_actions: List[TradeAction] = []

    # --- F5 data: use repository index for efficient querying ---
    date_range = DateRange(start=start_time, end=end_time)

    if len(kol_list) == 1:
        # Single KOL: use DB-level filter
        records = repo.db.query(
            creator_id=kol_list[0],
            direction=direction_list[0] if len(direction_list) == 1 else None,
            date_range=date_range,
            limit=10000,
            offset=0,
        )
    else:
        records = repo.db.query(
            direction=direction_list[0] if len(direction_list) == 1 else None,
            date_range=date_range,
            limit=10000,
            offset=0,
        )

    for record in records:
        file_path = record.get("file_path")
        if not file_path:
            continue
        try:
            action = repo._load_from_file(Path(file_path))
            if action.trade_action_id not in seen_ids:
                seen_ids.add(action.trade_action_id)
                all_actions.append(action)
        except Exception as e:
            logger.warning("Failed to load TradeAction from %s: %s", file_path, e)

    # --- F6 data: direct file scan (reviewed actions) ---
    l6_dir = DATA_ROOT / "F6_reviewed"
    for action in _load_actions_from_dir(l6_dir):
        if action.trade_action_id not in seen_ids:
            seen_ids.add(action.trade_action_id)
            all_actions.append(action)

    # --- In-memory filters for multi-value fields ---
    if len(kol_list) > 1:
        all_actions = [a for a in all_actions if a.source.creator_id in kol_list]
    if len(direction_list) > 1:
        all_actions = [a for a in all_actions if a.direction.value in direction_list]
    if ticker_list:
        normalized_tickers = {t.upper() for t in ticker_list}
        all_actions = [
            a for a in all_actions
            if (a.target.ticker_normalized or a.target.ticker).upper() in normalized_tickers
        ]

    # Sort by timestamp descending
    all_actions.sort(key=lambda a: a.timestamp, reverse=True)

    total = len(all_actions)

    # Apply pagination
    paginated = all_actions[offset: offset + limit]

    # Convert to TimelineOpinion
    opinions = [trade_action_to_opinion(a) for a in paginated]

    return opinions, total


def _load_all_actions() -> List[TradeAction]:
    """Load all TradeAction data from F5 (via repository) and F6 (file scan).

    Deduplicates by trade_action_id.
    """
    repo = _get_repository()
    seen_ids: set[str] = set()
    all_actions: List[TradeAction] = []

    # F5 data via repository index
    records = repo.db.query(limit=100000, offset=0)
    for record in records:
        file_path = record.get("file_path")
        if not file_path:
            continue
        try:
            action = repo._load_from_file(Path(file_path))
            if action.trade_action_id not in seen_ids:
                seen_ids.add(action.trade_action_id)
                all_actions.append(action)
        except Exception as e:
            logger.warning("Failed to load TradeAction from %s: %s", file_path, e)

    # F6 data via direct file scan
    l6_dir = DATA_ROOT / "F6_reviewed"
    for action in _load_actions_from_dir(l6_dir):
        if action.trade_action_id not in seen_ids:
            seen_ids.add(action.trade_action_id)
            all_actions.append(action)

    return all_actions


def _get_real_meta() -> TimelineMeta:
    """Get meta information from real data (F5 + F6)."""
    all_actions = _load_all_actions()

    tickers_set: set[str] = set()
    kols_set: set[str] = set()
    timestamps: List[str] = []

    for action in all_actions:
        tickers_set.add(action.target.ticker_normalized or action.target.ticker)
        if action.source.creator_id:
            kols_set.add(action.source.creator_id)
        timestamps.append(action.timestamp.isoformat())

    now = datetime.now()
    time_range = {
        "min": min(timestamps) if timestamps else (now - timedelta(days=365)).isoformat(),
        "max": max(timestamps) if timestamps else now.isoformat(),
    }

    return TimelineMeta(
        tickers=sorted(tickers_set),
        kols=sorted(kols_set),
        totalOpinions=len(all_actions),
        timeRange=time_range,
    )


def _get_real_stats(time_range: str, ticker: Optional[str]) -> Dict[str, Any]:
    """Get statistics summary from real data (F5 + F6)."""
    all_actions = _load_all_actions()

    now = datetime.now()
    time_range_map = {
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "1Y": timedelta(days=365),
        "ALL": timedelta(days=365 * 2),
    }
    start_time = now - time_range_map.get(time_range, timedelta(days=30))

    # Filter by time range and ticker
    filtered: List[TradeAction] = []
    for action in all_actions:
        if action.timestamp < start_time:
            continue
        if ticker and (action.target.ticker_normalized or action.target.ticker).upper() != ticker.upper():
            continue
        filtered.append(action)

    if not filtered:
        return {
            "total": 0,
            "byDirection": {"bullish": 0, "bearish": 0, "neutral": 0},
            "byStatus": {"success": 0, "failed": 0, "pending": 0},
            "avgConfidence": 0.0,
            "avgPriceChange": 0.0,
            "topTickers": [],
            "topKols": [],
        }

    # Aggregate
    by_direction: Dict[str, int] = {"bullish": 0, "bearish": 0, "neutral": 0}
    by_status: Dict[str, int] = {"success": 0, "failed": 0, "pending": 0}
    confidences: List[float] = []
    price_changes: List[float] = []
    ticker_counts: Dict[str, int] = {}
    ticker_success: Dict[str, List[bool]] = {}
    kol_counts: Dict[str, int] = {}

    for action in filtered:
        # Direction
        d = action.direction.value
        if d in by_direction:
            by_direction[d] += 1
        elif d == "watchlist":
            by_direction["neutral"] += 1
        elif d == "risk_warning":
            by_direction["bearish"] += 1

        # Validation status
        s = action.validation_status.value
        mapped_s = _VALIDATION_STATUS_MAP.get(s, "pending")
        if mapped_s in by_status:
            by_status[mapped_s] += 1

        confidences.append(action.confidence)

        # Backtest price change
        if action.backtest_result and action.backtest_result.return_pct is not None:
            price_changes.append(action.backtest_result.return_pct)

        # Ticker counts
        t = action.target.ticker_normalized or action.target.ticker
        ticker_counts[t] = ticker_counts.get(t, 0) + 1
        if action.validation_status == ValidationStatus.VERIFIED:
            ticker_success.setdefault(t, []).append(True)
        elif action.validation_status == ValidationStatus.FAILED:
            ticker_success.setdefault(t, []).append(False)

        # KOL counts
        kol = action.source.creator_id or ""
        if kol:
            kol_counts[kol] = kol_counts.get(kol, 0) + 1

    avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    avg_price_change = round(sum(price_changes) / len(price_changes), 2) if price_changes else 0.0

    # Top tickers
    top_tickers = sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_ticker_list = [
        {
            "ticker": t,
            "count": cnt,
            "successRate": round(
                sum(1 for v in ticker_success.get(t, []) if v) / len(ticker_success[t]), 2
            ) if t in ticker_success and ticker_success[t] else 0.0,
        }
        for t, cnt in top_tickers
    ]

    # Top KOLs
    top_kols = sorted(kol_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_kol_list = [
        {"author": k, "count": cnt, "avgRating": 0.0}
        for k, cnt in top_kols
    ]

    return {
        "total": len(filtered),
        "byDirection": by_direction,
        "byStatus": by_status,
        "avgConfidence": avg_confidence,
        "avgPriceChange": avg_price_change,
        "topTickers": top_ticker_list,
        "topKols": top_kol_list,
    }



# ============================================
# API 端点
# ============================================

@router.get("/timeline", response_model=TimelineData)
async def get_timeline(
    timeRange: str = Query("1M", description="时间范围: 1W, 1M, 3M, 1Y, ALL"),
    tickers: Optional[str] = Query(None, description="标的列表，逗号分隔"),
    directions: Optional[str] = Query(None, description="方向列表，逗号分隔"),
    kols: Optional[str] = Query(None, description="KOL列表，逗号分隔"),
    cursor: Optional[str] = Query(None, description="分页游标"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """获取观点时间线数据."""
    ticker_list = tickers.split(",") if tickers else []
    direction_list = directions.split(",") if directions else []
    kol_list = kols.split(",") if kols else []

    now = datetime.now()
    time_range_map = {
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "1Y": timedelta(days=365),
        "ALL": timedelta(days=365 * 2),
    }
    start_time = now - time_range_map.get(timeRange, timedelta(days=30))
    offset = int(cursor) if cursor else 0

    try:
        opinions, total = _query_real_timeline(
            ticker_list=ticker_list,
            direction_list=direction_list,
            kol_list=kol_list,
            start_time=start_time,
            end_time=now,
            offset=offset,
            limit=limit,
        )
    except Exception as e:
        logger.error("Failed to query timeline data: %s", e, exc_info=True)
        raise FinerError(
            ErrorCode.F7_INT_001,
            f"时间线数据查询失败: {e}",
            stage="F7",
            operation="get_timeline",
            retryable=True,
            fix_hint="检查 F5/F6 数据目录是否存在有效的 TradeAction 文件",
        )

    has_more = offset + limit < total
    next_cursor = str(offset + limit) if has_more else None

    return TimelineData(
        opinions=opinions,
        total=total,
        hasMore=has_more,
        nextCursor=next_cursor,
    )


@router.get("/meta", response_model=TimelineMeta)
async def get_timeline_meta():
    """获取时间线元数据（可选的标的、KOL等）."""
    try:
        return _get_real_meta()
    except Exception as e:
        logger.error("Failed to query timeline meta: %s", e, exc_info=True)
        raise FinerError(
            ErrorCode.F7_INT_001,
            f"时间线元数据查询失败: {e}",
            stage="F7",
            operation="get_timeline_meta",
            retryable=True,
            fix_hint="检查 F5/F6 数据目录是否存在有效的 TradeAction 文件",
        )


@router.get("/stats/summary")
async def get_stats_summary(
    timeRange: str = Query("1M", description="时间范围"),
    ticker: Optional[str] = Query(None, description="标的筛选"),
):
    """获取统计摘要."""
    try:
        return {"ok": True, "data": _get_real_stats(timeRange, ticker)}
    except Exception as e:
        logger.error("Failed to query stats summary: %s", e, exc_info=True)
        raise FinerError(
            ErrorCode.F7_INT_001,
            f"统计摘要查询失败: {e}",
            stage="F7",
            operation="get_stats_summary",
            retryable=True,
            fix_hint="检查 F5/F6 数据目录是否存在有效的 TradeAction 文件",
        )


@router.get("/{opinion_id}", response_model=TimelineOpinion)
async def get_opinion_detail(opinion_id: str):
    """获取单个观点详情."""
    try:
        # F5 via repository
        repo = _get_repository()
        action = repo.load(opinion_id)
        if action:
            return trade_action_to_opinion(action)

        # F6 via direct file scan
        l6_dir = DATA_ROOT / "F6_reviewed"
        for file_path in l6_dir.glob("**/*.action.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                candidate = TradeAction.from_dict(data)
                if candidate.trade_action_id == opinion_id:
                    return trade_action_to_opinion(candidate)
            except Exception:
                continue
    except FinerError:
        raise
    except Exception as e:
        logger.error("Failed to load opinion %s: %s", opinion_id, e, exc_info=True)
        raise FinerError(
            ErrorCode.F7_INT_001,
            f"观点详情查询失败: {e}",
            stage="F7",
            operation="get_opinion_detail",
            retryable=True,
            fix_hint="检查 F5/F6 数据目录是否存在有效的 TradeAction 文件",
        )

    raise FinerError(
        ErrorCode.F7_NTF_001,
        f"观点 {opinion_id} 未找到",
        stage="F7",
        operation="get_opinion_detail",
        retryable=False,
        fix_hint="检查 opinion_id 是否正确，或确认 F5/F6 数据已导入",
    )
