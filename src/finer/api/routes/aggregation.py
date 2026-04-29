"""Aggregation API -- F2 Anchor 聚合层端点.

提供实体消歧、上下文聚合、观点时间线查询接口：
- GET  /entities/{entity}/timeline - 获取某实体的观点时间线
- GET  /entities/search           - 搜索实体，返回匹配的标准化结果
- POST /process                   - 处理文本，返回消歧后的实体和摘要
- POST /process-with-market       - 处理文本并注入市场数据
- GET  /entity-index              - 获取实体索引
- GET  /resolve/{text}            - 解析文本中的实体
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from finer.aggregation import L4AggregationLayer, EntityLinker, create_l4_layer

router = APIRouter()

logger = logging.getLogger(__name__)


# ============================================
# Request / Response Models
# ============================================

class EntityRefResponse(BaseModel):
    """实体引用响应."""
    raw_text: str = Field(..., description="原始表述，如 '腾讯'")
    normalized: str = Field(..., description="标准化代码，如 '0700.HK'")
    entity_type: str = Field(..., description="实体类型: ticker, company, index, concept")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    market: Optional[str] = Field(None, description="市场: US, HK, CN, CRYPTO")


class ProcessRequest(BaseModel):
    """文本处理请求."""
    text: str = Field(..., min_length=1, description="要处理的文本内容")
    content_id: str = Field(..., description="内容 ID")
    timestamp: Optional[str] = Field(None, description="时间戳 (ISO 8601)")
    author: Optional[str] = Field(None, description="作者")
    source_platform: Optional[str] = Field(None, description="来源平台")


class ProcessWithMarketRequest(ProcessRequest):
    """文本处理请求（含市场数据注入）."""
    pass


class ProcessResponse(BaseModel):
    """文本处理响应."""
    content_id: str
    entities: List[EntityRefResponse]
    summary: Optional[str] = None
    market_data: Optional[Dict[str, Any]] = None
    cross_references: List[str] = Field(default_factory=list)


class TimelineEntry(BaseModel):
    """时间线条目."""
    content_id: str
    timestamp: str
    summary: Optional[str] = None
    author: Optional[str] = None
    source: Optional[str] = None


class EntitySearchResult(BaseModel):
    """实体搜索结果."""
    raw_text: str
    normalized: str
    entity_type: str
    market: Optional[str] = None


class EntityIndexResponse(BaseModel):
    """实体索引响应."""
    entity_index: Dict[str, List[str]] = Field(
        ..., description="标准化实体 -> 内容 ID 列表"
    )
    total_entities: int
    total_contents: int


# ============================================
# Layer Singleton
# ============================================

_l4_layer: Optional[L4AggregationLayer] = None


def _get_l4_layer() -> L4AggregationLayer:
    """获取或创建 F2 聚合层单例."""
    global _l4_layer
    if _l4_layer is None:
        _l4_layer = create_l4_layer()
    return _l4_layer


def _entity_ref_to_response(ref) -> EntityRefResponse:
    """将 EntityReference dataclass 转换为响应模型."""
    return EntityRefResponse(
        raw_text=ref.raw_text,
        normalized=ref.normalized,
        entity_type=ref.entity_type,
        confidence=ref.confidence,
        market=ref.market,
    )


def _context_to_response(ctx, include_market: bool = False) -> ProcessResponse:
    """将 AggregatedContext dataclass 转换为响应模型."""
    return ProcessResponse(
        content_id=ctx.content_id,
        entities=[_entity_ref_to_response(e) for e in ctx.entities],
        summary=ctx.summary,
        market_data=ctx.market_data if include_market else None,
        cross_references=ctx.cross_references,
    )


def _parse_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """解析 ISO 8601 时间戳，失败时抛出 HTTPException."""
    if ts_str is None:
        return None
    try:
        return datetime.fromisoformat(ts_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timestamp format: {ts_str}. Expected ISO 8601.",
        )


# ============================================
# API Endpoints
# ============================================

@router.get("/entities/{entity}/timeline")
async def get_entity_timeline(entity: str):
    """获取某实体的观点时间线.

    Args:
        entity: 标准化实体代码，如 0700.HK, NVDA, 000001.SH

    Returns:
        按时间倒序排列的观点列表
    """
    try:
        layer = _get_l4_layer()
        timeline = layer.get_entity_timeline(entity)

        entries = [
            TimelineEntry(
                content_id=entry["content_id"],
                timestamp=entry["timestamp"],
                summary=entry.get("summary"),
                author=entry.get("author"),
                source=entry.get("source"),
            )
            for entry in timeline
        ]

        return {
            "ok": True,
            "data": {
                "entity": entity,
                "timeline": [e.model_dump() for e in entries],
                "total": len(entries),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get timeline for {entity}: {e}")
        raise HTTPException(status_code=500, detail=f"获取时间线失败: {e}")


@router.get("/entities/search")
async def search_entities(q: str = Query(..., min_length=1, description="搜索关键词")):
    """搜索实体，返回匹配的标准化结果.

    遍历实体注册表，返回所有 raw_text 或 normalized 包含关键词的实体。

    Args:
        q: 搜索关键词，如 "腾讯", "NVDA", "0700"

    Returns:
        匹配的实体列表（去重后）
    """
    try:
        linker = EntityLinker()
        results: List[EntitySearchResult] = []
        seen_normalized: set = set()

        for raw_text, (normalized, market, entity_type) in linker.entities.items():
            if q.lower() in raw_text.lower() or q.lower() in normalized.lower():
                if normalized not in seen_normalized:
                    seen_normalized.add(normalized)
                    results.append(EntitySearchResult(
                        raw_text=raw_text,
                        normalized=normalized,
                        entity_type=entity_type,
                        market=market,
                    ))

        return {
            "ok": True,
            "data": {
                "query": q,
                "results": [r.model_dump() for r in results],
                "total": len(results),
            },
        }

    except Exception as e:
        logger.error(f"Entity search failed: {e}")
        raise HTTPException(status_code=500, detail=f"实体搜索失败: {e}")


@router.post("/process")
async def process_text(request: ProcessRequest):
    """处理文本，返回消歧后的实体和摘要.

    执行 F2 聚合流程：实体消歧 -> 摘要生成 -> 上下文聚合。

    Args:
        request: 包含文本、content_id 及可选元数据的请求

    Returns:
        消歧后的实体列表和摘要
    """
    try:
        layer = _get_l4_layer()
        ts = _parse_timestamp(request.timestamp)

        context = layer.process_text(
            text=request.text,
            content_id=request.content_id,
            timestamp=ts,
            author=request.author,
            source_platform=request.source_platform,
        )

        return {
            "ok": True,
            "data": _context_to_response(context).model_dump(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Aggregation process failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")


@router.post("/process-with-market")
async def process_text_with_market(request: ProcessWithMarketRequest):
    """处理文本并注入市场数据.

    在 /process 基础上额外执行市场数据预注入（当前价格、52 周范围等）。

    Args:
        request: 包含文本、content_id 及可选元数据的请求

    Returns:
        消歧后的实体列表、摘要和市场数据
    """
    try:
        layer = _get_l4_layer()
        ts = _parse_timestamp(request.timestamp)

        context = await layer.process_with_market_data(
            text=request.text,
            content_id=request.content_id,
            timestamp=ts,
            author=request.author,
            source_platform=request.source_platform,
        )

        return {
            "ok": True,
            "data": _context_to_response(context, include_market=True).model_dump(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Aggregation process (with market) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")


@router.get("/entity-index")
async def get_entity_index():
    """获取实体索引.

    返回当前聚合器中 标准化实体 -> 内容 ID 列表 的完整映射。

    Returns:
        实体索引、实体总数、关联内容总数
    """
    try:
        layer = _get_l4_layer()
        index = layer.get_entity_index()

        all_contents: set = set()
        for content_ids in index.values():
            all_contents.update(content_ids)

        return {
            "ok": True,
            "data": EntityIndexResponse(
                entity_index=index,
                total_entities=len(index),
                total_contents=len(all_contents),
            ).model_dump(),
        }

    except Exception as e:
        logger.error(f"Failed to get entity index: {e}")
        raise HTTPException(status_code=500, detail=f"获取实体索引失败: {e}")


@router.get("/resolve/{text}")
async def resolve_entities(text: str):
    """解析文本中的实体.

    Args:
        text: 要解析的文本

    Returns:
        识别到的实体列表
    """
    try:
        linker = EntityLinker()
        entities = linker.resolve(text)

        return {
            "ok": True,
            "data": {
                "text": text,
                "entities": [_entity_ref_to_response(e).model_dump() for e in entities],
                "total": len(entities),
            },
        }

    except Exception as e:
        logger.error(f"Entity resolution failed: {e}")
        raise HTTPException(status_code=500, detail=f"实体解析失败: {e}")