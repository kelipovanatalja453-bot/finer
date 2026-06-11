"""Annotation API — 人工标注工作台端点（F+ Training Loop / F6 支撑面）.

F-stage: F+（训练数据运维），消费 ``data/dpo/**`` JSONL，不触碰 F0-F8 主链路。
输入 schema: ``schemas/annotation.py``（EvalGoldAnnotation / PairReviewAnnotation）
输出契约: ``data/dpo/eval/eval_set.jsonl``（eval_compare）、``data/dpo/pairs_cleaned.jsonl``（to_bailian）

route 只做参数解析与响应格式化，业务逻辑在 ``services/annotation_store.py``。
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, ValidationError

from finer.errors.codes import ErrorCode
from finer.errors.exceptions import FinerError
from finer.schemas.annotation import (
    AnnotationExportMode,
    AnnotationItemStatus,
    AnnotationTaskId,
)
from finer.services.annotation_store import AnnotationStore

router = APIRouter()

_store = AnnotationStore()


def get_store() -> AnnotationStore:
    """模块级单例；测试可通过 monkeypatch 替换。"""
    return _store


class AnnotationSubmitRequest(BaseModel):
    """提交一条标注。annotation 结构由 task_id 决定（schema 在 schemas/annotation.py）。"""

    task_id: AnnotationTaskId
    annotation: Dict[str, Any] = Field(..., description="标注内容")


class AnnotationExportRequest(BaseModel):
    task_id: AnnotationTaskId
    mode: AnnotationExportMode = "formal"


class EvalSourceRebuildRequest(BaseModel):
    src: str = Field("data", description="搜索 chat_history_*.md 的根目录")
    limit: int = Field(30, ge=1, le=500)
    seed: int = Field(20260610)
    min_signal: int = Field(2, ge=0, le=3)
    min_len: int = Field(40, ge=1)
    max_len: int = Field(1200, ge=1)
    exclude_image_placeholders: bool = True


class RegistryGapRequest(BaseModel):
    """实体库缺口候补（人工 review 后才进 entity_registry）。"""

    alias: str = Field(..., min_length=1, description="原文中的实体别名")
    suggested_ticker: str = Field("", description="建议 ticker（可空）")
    market: str = Field("", description="建议市场 CN/HK/US（可空）")
    item_id: str = Field("", description="来源段落 id")
    reviewer_id: str = Field(..., min_length=1)


class KolNoteRequest(BaseModel):
    """KOL 风格速记，追加 data/kol_profiles/notes/{creator}.jsonl。"""

    creator: str = Field(..., min_length=1, description="creator slug（如 maodaren）")
    category: str = Field(..., description="style/discipline/preference/track_record")
    text: str = Field(..., min_length=1, description="速记内容（通常为原文选区）")
    source_item_id: str = Field("", description="来源段落 id")
    source_file: str = Field("", description="来源文件")
    reviewer_id: str = Field(..., min_length=1)


@router.get("/tasks")
def list_tasks() -> Dict[str, Any]:
    """标注任务列表 + 进度。"""
    summaries = [s.model_dump() for s in get_store().task_summaries()]
    return {"ok": True, "data": {"tasks": summaries}}


@router.get("/items")
def list_items(
    task_id: AnnotationTaskId,
    status: Optional[AnnotationItemStatus] = Query(None),
    sample_size: Optional[int] = Query(None, ge=1),
    seed: Optional[int] = Query(None),
) -> Dict[str, Any]:
    """任务条目（任务源 + 已有标注合并视图）。"""
    try:
        items = get_store().list_items(
            task_id,
            status=status,
            sample_size=sample_size,
            seed=seed,
        )
    except OSError as exc:
        raise FinerError(
            ErrorCode.SYS_IO_001,
            f"读取标注任务源失败: {exc}",
            stage="F+",
            operation="annotation_list_items",
            retryable=True,
        ) from exc
    return {"ok": True, "data": {"items": items, "total": len(items)}}


@router.get("/enums")
def annotation_enums() -> Dict[str, Any]:
    """Return enum truth sources for the UI."""
    return {"ok": True, "data": get_store().enums()}


@router.post("/submit")
def submit_annotation(body: AnnotationSubmitRequest) -> Dict[str, Any]:
    """校验并落盘一条标注（append-only，按 id last-wins）。"""
    try:
        progress = get_store().submit(body.task_id, body.annotation)
    except ValidationError as exc:
        raise FinerError(
            ErrorCode.API_IN_001,
            f"标注内容不符合 schema: {exc.errors()[0].get('msg', exc)}",
            stage="F+",
            operation="annotation_submit",
            retryable=False,
            fix_hint="对照 schemas/annotation.py 修正提交字段后重试",
        ) from exc
    except ValueError as exc:
        raise FinerError(
            ErrorCode.API_IN_001,
            str(exc),
            stage="F+",
            operation="annotation_submit",
            retryable=False,
            fix_hint="刷新页面以加载当前 schema 版本后重新提交",
        ) from exc
    except KeyError as exc:
        raise FinerError(
            ErrorCode.API_NTF_001,
            str(exc.args[0]) if exc.args else "标注目标不存在",
            stage="F+",
            operation="annotation_submit",
            retryable=False,
            fix_hint="刷新任务列表后重新标注（任务源可能已重新生成）",
        ) from exc
    except OSError as exc:
        raise FinerError(
            ErrorCode.SYS_IO_001,
            f"标注落盘失败: {exc}",
            stage="F+",
            operation="annotation_submit",
            retryable=True,
        ) from exc
    return {"ok": True, "data": {"progress": progress}}


@router.post("/export")
def export_annotations(body: AnnotationExportRequest) -> Dict[str, Any]:
    """导出标注产物（eval_set.jsonl / pairs_cleaned.jsonl）。"""
    try:
        result = get_store().export(body.task_id, body.mode)
    except ValueError as exc:
        raise FinerError(
            ErrorCode.API_STATE_001,
            str(exc),
            stage="F+",
            operation="annotation_export",
            retryable=False,
            fix_hint="在页面任务准备/质量状态中处理阻断项，或仅用于调试时选择 draft export",
        ) from exc
    except OSError as exc:
        raise FinerError(
            ErrorCode.SYS_IO_001,
            f"导出失败: {exc}",
            stage="F+",
            operation="annotation_export",
            retryable=True,
        ) from exc
    return {"ok": True, "data": result}


@router.get("/context")
def passage_context(
    item_id: str = Query(..., min_length=1),
    before: int = Query(5, ge=0, le=20),
    after: int = Query(5, ge=0, le=20),
) -> Dict[str, Any]:
    """eval 段落在源 chat_history 文件中的邻近消息块（上下文扩展）。"""
    try:
        result = get_store().context(item_id, before=before, after=after)
    except KeyError as exc:
        raise FinerError(
            ErrorCode.API_NTF_001,
            str(exc.args[0]) if exc.args else "段落不存在",
            stage="F+",
            operation="annotation_context",
            retryable=False,
            fix_hint="刷新任务列表后重试（任务源可能已重新生成）",
        ) from exc
    except FileNotFoundError as exc:
        raise FinerError(
            ErrorCode.API_NTF_001,
            str(exc),
            stage="F+",
            operation="annotation_context",
            retryable=False,
            fix_hint="源 chat_history 文件已移动或删除，无法提供上下文",
        ) from exc
    except ValueError as exc:
        raise FinerError(
            ErrorCode.API_STATE_001,
            str(exc),
            stage="F+",
            operation="annotation_context",
            retryable=False,
            fix_hint="源文件内容与任务源不一致，可重建评测集任务源",
        ) from exc
    except OSError as exc:
        raise FinerError(
            ErrorCode.SYS_IO_001,
            f"读取源文件失败: {exc}",
            stage="F+",
            operation="annotation_context",
            retryable=True,
        ) from exc
    return {"ok": True, "data": result}


@router.post("/registry-gap")
def submit_registry_gap(body: RegistryGapRequest) -> Dict[str, Any]:
    """记录实体库缺口候补。"""
    try:
        result = get_store().append_registry_gap(
            alias=body.alias,
            suggested_ticker=body.suggested_ticker,
            market=body.market,
            item_id=body.item_id,
            reviewer_id=body.reviewer_id,
        )
    except ValueError as exc:
        raise FinerError(
            ErrorCode.API_IN_001,
            str(exc),
            stage="F+",
            operation="annotation_registry_gap",
            retryable=False,
            fix_hint="alias 不能为空",
        ) from exc
    except OSError as exc:
        raise FinerError(
            ErrorCode.SYS_IO_001,
            f"候补落盘失败: {exc}",
            stage="F+",
            operation="annotation_registry_gap",
            retryable=True,
        ) from exc
    return {"ok": True, "data": result}


@router.post("/kol-note")
def submit_kol_note(body: KolNoteRequest) -> Dict[str, Any]:
    """KOL 风格速记落盘。"""
    try:
        result = get_store().append_kol_note(
            creator=body.creator,
            category=body.category,
            text=body.text,
            source_item_id=body.source_item_id,
            source_file=body.source_file,
            reviewer_id=body.reviewer_id,
        )
    except ValueError as exc:
        raise FinerError(
            ErrorCode.API_IN_001,
            str(exc),
            stage="F+",
            operation="annotation_kol_note",
            retryable=False,
            fix_hint="检查 creator/category/text 字段",
        ) from exc
    except OSError as exc:
        raise FinerError(
            ErrorCode.SYS_IO_001,
            f"速记落盘失败: {exc}",
            stage="F+",
            operation="annotation_kol_note",
            retryable=True,
        ) from exc
    return {"ok": True, "data": result}


@router.get("/market")
def market_window(
    ticker: str = Query(..., min_length=1),
    date: str = Query(..., min_length=8, description="锚定日期 YYYY-MM-DD"),
) -> Dict[str, Any]:
    """标注行情对照：本地 tushare 库锚定日 ±10 交易日窗口（降级态在 data.coverage）。"""
    from finer.services.market_lookup import lookup_market_window

    try:
        result = lookup_market_window(ticker, date)
    except ValueError as exc:
        raise FinerError(
            ErrorCode.API_IN_001,
            str(exc),
            stage="F+",
            operation="annotation_market",
            retryable=False,
            fix_hint="date 使用 YYYY-MM-DD 格式",
        ) from exc
    except OSError as exc:
        raise FinerError(
            ErrorCode.SYS_IO_001,
            f"本地行情查询失败: {exc}",
            stage="F+",
            operation="annotation_market",
            retryable=True,
        ) from exc
    return {"ok": True, "data": result}


@router.post("/eval-source/rebuild")
def rebuild_eval_source(body: EvalSourceRebuildRequest) -> Dict[str, Any]:
    """Rebuild held-out eval source from the UI-controlled selection parameters."""
    try:
        result = get_store().rebuild_eval_source(**body.model_dump())
    except FileNotFoundError as exc:
        raise FinerError(
            ErrorCode.API_NTF_001,
            str(exc),
            stage="F+",
            operation="annotation_eval_source_rebuild",
            retryable=False,
            fix_hint="检查 src 是否指向包含 chat_history_*.md 的目录",
        ) from exc
    except OSError as exc:
        raise FinerError(
            ErrorCode.SYS_IO_001,
            f"重建评测集任务源失败: {exc}",
            stage="F+",
            operation="annotation_eval_source_rebuild",
            retryable=True,
        ) from exc
    return {"ok": True, "data": result}
