"""Annotation schemas — F+ Training Loop 人工标注数据契约.

标注工作台（annotation workbench）的数据模型，服务两类标注任务：

- ``eval_gold``：为 held-out 评测集标注 gold 抽取 + ``expected_abstain``，
  导出 ``data/dpo/eval/eval_set.jsonl`` 供 ``scripts/eval_compare.py`` 消费。
- ``pairs_review``：对 DPO 偏好对（``data/dpo/pairs.jsonl``）的 chosen 侧做
  人工抽检（accept / edit / reject），导出清洗后的 ``pairs_cleaned.jsonl``。

落盘形态为 ``data/dpo/**`` 下的 JSONL（文件即真相源，不引入 SQLite 表）。
方向/动作枚举以 ``schemas/trade_action.py`` 为唯一真相源，不重定义。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from finer.schemas.trade_action import ActionType, TradeDirection
from finer.services.annotation_validation import validate_extraction_object

AnnotationTaskId = Literal["eval_gold", "pairs_review"]
AnnotationExportMode = Literal["formal", "draft"]
AnnotationItemStatus = Literal["pending", "annotated", "excluded"]
EvalSampleVerdict = Literal["gold", "exclude"]

ANNOTATION_SCHEMA_VERSION = "2026-06-11.annotation.v3"
# 读取/合并时接受的历史版本；新提交只接受 ANNOTATION_SCHEMA_VERSION（store.submit 强制）
ACCEPTED_SCHEMA_VERSIONS = frozenset({"2026-06-10.annotation.v2", ANNOTATION_SCHEMA_VERSION})


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GoldActionStep(BaseModel):
    """gold 抽取中的单个动作步骤（简化抽取 JSON 的 action_chain 元素）。"""

    action_type: ActionType = Field(
        ..., description="动作类型，枚举以 schemas/trade_action.py 为真相源"
    )
    trigger_condition: Optional[str] = Field(
        None, description="触发条件，应在原文可溯（不编造数字）"
    )
    target_price_low: Optional[float] = Field(
        None, ge=0, description="目标价下限；只允许原文出现过的数字"
    )
    target_price_high: Optional[float] = Field(
        None, ge=0, description="目标价上限；只允许原文出现过的数字"
    )

    @model_validator(mode="after")
    def _price_range_ordered(self) -> "GoldActionStep":
        lo, hi = self.target_price_low, self.target_price_high
        if lo is not None and hi is not None and lo > hi:
            raise ValueError(f"价格区间倒挂: {lo} > {hi}")
        return self


class GoldExtraction(BaseModel):
    """评测集 gold 答案（简化抽取 JSON，非完整 canonical TradeAction）。

    与 scripts/eval_compare.py 的 ref-judge 消费字段对齐：
    ticker / direction / action_chain（承诺一致性由 action_chain 推导）。
    """

    ticker: str = Field(
        ..., min_length=1, description="标的代码；无明确标的（弃权项）时用 'NONE'"
    )
    direction: TradeDirection = Field(..., description="整体方向")
    action_chain: List[GoldActionStep] = Field(
        default_factory=list, description="动作链（可为空）"
    )
    conviction: Optional[float] = Field(
        None, ge=0, le=1, description="证据强度 0-1（迭代 2 conviction 轴，可选）"
    )
    rationale: Optional[str] = Field(None, description="判断理由（可选）")

    @model_validator(mode="after")
    def _lightweight_contract_valid(self) -> "GoldExtraction":
        errors = validate_extraction_object(self.model_dump(mode="json"))
        if errors:
            raise ValueError("; ".join(errors))
        return self


class ContextBlock(BaseModel):
    """标注者从源文件并入证据的邻近消息块。

    formal export 时按 offset 顺序拼进 eval 样本的 evidence_text，
    保证被测模型与标注者看到同样的输入（评测公平性）。
    """

    offset: int = Field(
        ..., description="相对当前段落的位置；-2 = 前面第 2 条，1 = 后面第 1 条；不允许 0"
    )
    timestamp: Optional[str] = Field(None, description="消息块时间戳（源文件块头）")
    content: str = Field(..., min_length=1, description="消息块清洗后文本")

    @model_validator(mode="after")
    def _offset_nonzero(self) -> "ContextBlock":
        if self.offset == 0:
            raise ValueError("context_blocks 不允许 offset=0（当前段落本身不是上下文）")
        return self


class EvalGoldAnnotation(BaseModel):
    """held-out 评测集单条人工标注。``id`` 对齐 passages.jsonl 的段落 id。"""

    id: str = Field(..., min_length=1, description="段落 id（psg_*）")
    reviewer_id: str = Field(..., min_length=1, description="标注者 id")
    annotation_schema_version: str = Field(
        ..., description="标注 schema 版本，用于阻断 legacy 行进入 formal export"
    )
    sample_verdict: EvalSampleVerdict = Field(
        "gold", description="gold=有效评测样本 / exclude=样本无效，不进入 eval_set"
    )
    exclude_reason: Optional[
        Literal["image_placeholder", "insufficient_context", "non_investment", "duplicate", "other"]
    ] = Field(None, description="sample_verdict=exclude 时必填")
    expected_abstain: bool = Field(
        False, description="证据不足、模型应当弃权（watchlist/hold）"
    )
    gold: Optional[GoldExtraction] = Field(None, description="人工标注的 gold 抽取")
    alt_golds: List[GoldExtraction] = Field(
        default_factory=list,
        description="次要标的的 gold（多标的段落）；评测时 match-any 计分",
    )
    context_blocks: List[ContextBlock] = Field(
        default_factory=list,
        description="并入证据的邻近消息块；formal export 时拼进 evidence_text",
    )
    notes: Optional[str] = Field(None, description="标注备注")
    duration_ms: Optional[int] = Field(None, ge=0, description="标注耗时毫秒（前端自动记录）")
    annotated_at: datetime = Field(
        default_factory=utc_now, description="标注时间"
    )

    @model_validator(mode="after")
    def _verdict_fields_valid(self) -> "EvalGoldAnnotation":
        if self.annotation_schema_version not in ACCEPTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"annotation_schema_version 必须属于 {sorted(ACCEPTED_SCHEMA_VERSIONS)}"
            )
        if self.sample_verdict == "gold" and self.gold is None:
            raise ValueError("sample_verdict=gold 必须提供 gold")
        if self.sample_verdict == "exclude" and not self.exclude_reason:
            raise ValueError("sample_verdict=exclude 必须提供 exclude_reason")
        if self.sample_verdict == "exclude" and self.alt_golds:
            raise ValueError("sample_verdict=exclude 不允许携带 alt_golds")
        if self.alt_golds:
            if self.gold is None:
                raise ValueError("alt_golds 需要主 gold 存在")
            primary = self.gold.ticker.strip().upper()
            seen = {primary}
            for alt in self.alt_golds:
                t = alt.ticker.strip().upper()
                if t in seen:
                    raise ValueError(f"alt_golds 中 ticker {t!r} 与主 gold 或其他备选重复")
                seen.add(t)
        offsets = [b.offset for b in self.context_blocks]
        if len(offsets) != len(set(offsets)):
            raise ValueError("context_blocks 中 offset 重复")
        return self


class PairReviewAnnotation(BaseModel):
    """DPO 偏好对 chosen 侧抽检结论。``pair_id`` 对齐 pairs.jsonl 的 meta.passage_id。"""

    pair_id: str = Field(..., min_length=1, description="偏好对 id（= passage_id）")
    reviewer_id: str = Field(..., min_length=1, description="审核者 id")
    annotation_schema_version: str = Field(
        ..., description="标注 schema 版本，用于阻断 legacy 行进入 formal export"
    )
    verdict: Literal["accept", "edit", "reject"] = Field(
        ..., description="accept=chosen 合格 / edit=修正 chosen / reject=整对剔除"
    )
    edited_chosen: Optional[str] = Field(
        None, description="verdict=edit 时的修正版 chosen（合法 JSON 串）"
    )
    notes: Optional[str] = Field(None, description="审核备注")
    duration_ms: Optional[int] = Field(None, ge=0, description="审核耗时毫秒（前端自动记录）")
    annotated_at: datetime = Field(
        default_factory=utc_now, description="审核时间"
    )

    @model_validator(mode="after")
    def _edit_requires_valid_json(self) -> "PairReviewAnnotation":
        if self.annotation_schema_version not in ACCEPTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"annotation_schema_version 必须属于 {sorted(ACCEPTED_SCHEMA_VERSIONS)}"
            )
        if self.verdict == "edit":
            if not self.edited_chosen or not self.edited_chosen.strip():
                raise ValueError("verdict=edit 必须提供 edited_chosen")
            try:
                obj = json.loads(self.edited_chosen)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"edited_chosen 不是合法 JSON: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError("edited_chosen 必须是 JSON 对象")
            errors = validate_extraction_object(obj)
            if errors:
                raise ValueError("edited_chosen 不符合抽取合同: " + "; ".join(errors))
        return self


class AnnotationQualityStatus(BaseModel):
    """质量闸状态，供任务面板和 formal export 阻断使用。"""

    bad_source_lines: int = 0
    bad_annotation_lines: int = 0
    dangling_annotations: int = 0
    legacy_missing_reviewer: int = 0
    invalid_annotations: int = 0
    train_eval_overlap_ids: List[str] = Field(default_factory=list)
    image_placeholder_items: int = 0
    weak_signal_items: int = 0
    unexcluded_image_placeholder_items: int = 0
    unexcluded_weak_signal_items: int = 0
    incomplete_items: int = 0
    excluded_items: int = 0
    effective_gold_items: int = 0
    pair_sample_size: Optional[int] = None
    pair_sample_reviewed: Optional[int] = None
    manifest_path: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None
    formal_blocking_reasons: List[str] = Field(default_factory=list)


class AnnotationTaskSummary(BaseModel):
    """单个标注任务的状态摘要（供前端任务列表/进度展示）。"""

    task_id: AnnotationTaskId
    title: str = Field(..., description="任务展示名")
    source_path: str = Field(..., description="任务源 JSONL（repo 相对路径）")
    annotations_path: str = Field(..., description="标注结果 JSONL（repo 相对路径）")
    export_path: str = Field(..., description="导出目标 JSONL（repo 相对路径）")
    ready: bool = Field(..., description="任务源是否存在且非空")
    total: int = Field(0, ge=0, description="任务源条目数")
    annotated: int = Field(0, ge=0, description="已标注条目数")
    fix_hint: Optional[str] = Field(
        None, description="任务未就绪时的修复提示（如何生成任务源）"
    )
    quality: AnnotationQualityStatus = Field(default_factory=AnnotationQualityStatus)
