"""Trade Action Extraction API — F5 Execute 层事件提取端点.

提供 Trade Action 提取管线的前端触发接口：
- POST /api/extraction/extract - 从文本提取 Trade Actions
- POST /api/extraction/batch - 批量提取
- POST /api/extraction/pipeline - 运行完整 F5 管线
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import json
import logging
import asyncio

from finer.paths import REPO_ROOT, DATA_ROOT

router = APIRouter()

logger = logging.getLogger(__name__)
L5_CANDIDATE_DIR = DATA_ROOT / "L5_candidate"   # legacy dir; canonical is data/F5_executed
L4_PARSED_DIR = DATA_ROOT / "L4_parsed"         # legacy dir; canonical is data/F2_anchored


# ============================================
# Request/Response Models
# ============================================

class ExtractionRequest(BaseModel):
    """提取请求."""
    text: str = Field(..., description="要分析的文本内容")
    source_id: Optional[str] = Field(None, description="来源ID")
    author: Optional[str] = Field(None, description="作者")
    timestamp: Optional[str] = Field(None, description="时间戳")
    enable_enrichment: bool = Field(True, description="是否启用市场数据富化")


class BatchExtractionRequest(BaseModel):
    """批量提取请求."""
    items: List[Dict[str, Any]] = Field(..., description="待提取项目列表")
    parallel: bool = Field(True, description="是否并行处理")
    max_concurrency: int = Field(5, description="最大并发数")


class ActionStepResponse(BaseModel):
    """操作步骤响应."""
    sequence: int
    action_type: str
    trigger_condition: Optional[str] = None
    trigger_type: Optional[str] = None
    target_price_low: Optional[str] = None
    target_price_high: Optional[str] = None
    position_size_pct: Optional[float] = None
    notes: Optional[str] = None


class TradeActionResponse(BaseModel):
    """Trade Action 响应."""
    ticker: str
    ticker_normalized: Optional[str] = None
    market: Optional[str] = None
    direction: str
    confidence: float
    action_chain: List[ActionStepResponse]
    time_horizon: Optional[str] = None
    rationale: Optional[str] = None
    evidence_text: Optional[str] = None
    validation_status: str = "pending"
    requires_manual_review: bool = False


class ExtractionResponse(BaseModel):
    """提取响应."""
    success: bool
    actions: List[TradeActionResponse]
    total_actions: int
    avg_confidence: float
    model: str
    processing_time_ms: float
    error: Optional[str] = None


class PipelineStatusResponse(BaseModel):
    """管线状态响应."""
    status: str
    total_files: int
    processed: int
    failed: int
    pending: int
    last_run: Optional[str] = None


# ============================================
# Helper Functions
# ============================================

def _action_to_response(action) -> TradeActionResponse:
    """将 TradeAction 对象转换为响应模型."""
    return TradeActionResponse(
        ticker=action.target.ticker,
        ticker_normalized=action.target.ticker_normalized,
        market=action.target.market,
        direction=action.direction.value,
        confidence=action.confidence,
        action_chain=[
            ActionStepResponse(
                sequence=step.sequence,
                action_type=step.action_type.value,
                trigger_condition=step.trigger_condition,
                trigger_type=step.trigger_type.value if step.trigger_type else None,
                target_price_low=step.target_price_low,
                target_price_high=step.target_price_high,
                position_size_pct=step.position_size_pct,
                notes=step.notes,
            )
            for step in action.action_chain
        ],
        time_horizon=action.time_horizon,
        rationale=action.rationale,
        evidence_text=action.source.evidence_text if action.source else None,
        validation_status=action.validation_status.value if hasattr(action.validation_status, 'value') else "pending",
        requires_manual_review=action.requires_manual_review,
    )


# ============================================
# API Endpoints
# ============================================

@router.post("/extract", response_model=ExtractionResponse)
async def extract_trade_actions(request: ExtractionRequest):
    """从文本提取 Trade Actions.

    这是 F5 Execute 层的核心端点，使用 GLM-5.1 + Finance-Skills 混合策略。

    Args:
        request: 包含文本和可选上下文的请求

    Returns:
        ExtractionResponse 包含提取的 Trade Actions
    """
    import time
    start_time = time.time()

    try:
        from finer.extraction.trade_action_extractor import TradeActionExtractor

        # 创建提取器
        extractor = TradeActionExtractor(enable_enrichment=request.enable_enrichment)

        # 构建上下文
        context = {
            "source_id": request.source_id or "api_request",
        }
        if request.author:
            context["author"] = request.author
        if request.timestamp:
            context["timestamp"] = request.timestamp

        # 执行提取
        result = await extractor.extract_from_text(request.text, context)

        if not result.success:
            return ExtractionResponse(
                success=False,
                actions=[],
                total_actions=0,
                avg_confidence=0.0,
                model=extractor.model_version,
                processing_time_ms=(time.time() - start_time) * 1000,
                error=result.error or "提取失败",
            )

        # 转换结果
        actions = [_action_to_response(a) for a in result.actions]

        return ExtractionResponse(
            success=True,
            actions=actions,
            total_actions=len(actions),
            avg_confidence=result.avg_confidence,
            model=extractor.model_version,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    except ImportError as e:
        logger.error(f"Failed to import TradeActionExtractor: {e}")
        raise HTTPException(status_code=500, detail=f"模块导入失败: {e}")
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提取失败: {e}")


@router.post("/batch", response_model=List[ExtractionResponse])
async def batch_extract(request: BatchExtractionRequest):
    """批量提取 Trade Actions.

    Args:
        request: 包含多个待提取项目的请求

    Returns:
        List[ExtractionResponse] 每个项目的提取结果
    """
    try:
        from finer.extraction.trade_action_extractor import TradeActionExtractor

        extractor = TradeActionExtractor()

        # 执行批量提取
        results = await extractor.batch_extract(
            items=request.items,
            parallel=request.parallel,
            max_concurrency=request.max_concurrency,
        )

        # 转换结果
        responses = []
        for result in results:
            if result.success:
                actions = [_action_to_response(a) for a in result.actions]
                responses.append(ExtractionResponse(
                    success=True,
                    actions=actions,
                    total_actions=len(actions),
                    avg_confidence=result.avg_confidence,
                    model=extractor.model_version,
                    processing_time_ms=0,
                ))
            else:
                responses.append(ExtractionResponse(
                    success=False,
                    actions=[],
                    total_actions=0,
                    avg_confidence=0.0,
                    model=extractor.model_version,
                    processing_time_ms=0,
                    error=result.error,
                ))

        return responses

    except Exception as e:
        logger.error(f"Batch extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量提取失败: {e}")


@router.post("/pipeline")
async def run_extraction_pipeline(
    background_tasks: BackgroundTasks,
    input_dir: Optional[str] = Query(None, description="输入目录 (legacy L4/F2 解析产物)"),
    output_dir: Optional[str] = Query(None, description="输出目录 (legacy L5/F5 候选事件)"),
    limit: int = Query(100, description="最大处理文件数"),
):
    """运行完整的 F5 提取管线.

    从 data/L4_parsed (legacy) 读取解析产物，提取 Trade Actions，写入 data/L5_candidate (legacy)。

    Args:
        background_tasks: FastAPI 后台任务
        input_dir: 输入目录，默认 data/L4_parsed
        output_dir: 输出目录，默认 data/L5_candidate
        limit: 最大处理文件数

    Returns:
        任务状态
    """
    input_path = Path(input_dir) if input_dir else L4_PARSED_DIR
    output_path = Path(output_dir) if output_dir else L5_CANDIDATE_DIR

    # 确保输出目录存在
    output_path.mkdir(parents=True, exist_ok=True)

    # 定义后台任务
    def run_pipeline():
        import asyncio
        asyncio.run(_run_extraction_pipeline_async(input_path, output_path, limit))

    background_tasks.add_task(run_pipeline)

    return {
        "status": "started",
        "input_dir": str(input_path),
        "output_dir": str(output_path),
        "limit": limit,
        "message": "F5 提取管线已在后台启动",
    }


async def _run_extraction_pipeline_async(input_path: Path, output_path: Path, limit: int):
    """异步执行提取管线."""
    try:
        from finer.extraction.trade_action_extractor import TradeActionExtractor

        extractor = TradeActionExtractor()

        # 查找输入文件
        input_files = list(input_path.glob("**/*.json"))[:limit]
        logger.info(f"Found {len(input_files)} files to process in {input_path}")

        processed = 0
        failed = 0

        for file_path in input_files:
            try:
                # 读取文件内容
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 提取文本内容
                text = data.get("text") or data.get("content") or data.get("clean_text", "")
                if not text:
                    logger.warning(f"No text content in {file_path}")
                    continue

                # 执行提取
                context = {
                    "source_id": str(file_path),
                    "source_file": file_path.name,
                }
                result = await extractor.extract_from_text(text, context)

                if result.success and result.actions:
                    # 保存结果
                    output_file = output_path / f"{file_path.stem}_actions.json"
                    output_data = {
                        "source_file": str(file_path),
                        "extracted_at": datetime.now().isoformat(),
                        "model": extractor.model_version,
                        "actions": [a.model_dump() for a in result.actions],
                    }
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(output_data, f, ensure_ascii=False, indent=2)
                    processed += 1
                    logger.info(f"Extracted {len(result.actions)} actions from {file_path.name}")
                else:
                    failed += 1
                    logger.warning(f"No actions extracted from {file_path.name}: {result.error}")

            except Exception as e:
                failed += 1
                logger.error(f"Failed to process {file_path}: {e}")

        logger.info(f"Pipeline completed: {processed} processed, {failed} failed")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)


@router.get("/status", response_model=PipelineStatusResponse)
async def get_extraction_status():
    """获取 F5 提取管线状态."""
    # 统计 L5_candidate 目录中的文件
    total_files = 0
    processed = 0
    failed = 0
    pending = 0

    if L5_CANDIDATE_DIR.exists():
        for f in L5_CANDIDATE_DIR.glob("*.json"):
            total_files += 1
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                if data.get("actions"):
                    processed += 1
                else:
                    failed += 1
            except:
                failed += 1

    # 统计 L4_parsed (legacy) 中待处理的文件
    if L4_PARSED_DIR.exists():
        for f in L4_PARSED_DIR.glob("**/*.json"):
            # 检查是否已在 L5 (legacy) 中处理
            l5_file = L5_CANDIDATE_DIR / f"{f.stem}_actions.json"
            if not l5_file.exists():
                pending += 1

    return PipelineStatusResponse(
        status="idle" if pending == 0 else "pending",
        total_files=total_files,
        processed=processed,
        failed=failed,
        pending=pending,
        last_run=None,
    )
