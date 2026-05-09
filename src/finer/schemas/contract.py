from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, List, Optional

# Match EXACTLY with src/finer_dashboard/src/lib/contracts.ts
WorkflowStage = Literal["intake", "enrichment", "library", "parsing", "extraction", "review", "backtest"]
ReviewDirection = Literal["bullish", "bearish", "neutral", "watchlist", "risk_warning"]
ReviewActionStatus = Literal["draft", "active", "watch"]
SourceType = Literal["feishu", "notebooklm", "local", "wechat", "bilibili", "unknown"]

class ReviewActionPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    action_type: str = Field(alias="actionType")
    instrument_type: str = Field(alias="instrumentType")
    trigger_condition: str = Field(alias="triggerCondition")
    target_price_low: str = Field(alias="targetPriceLow")
    target_price_high: str = Field(alias="targetPriceHigh")
    confidence: float
    status: ReviewActionStatus

class ReviewPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticker: str
    direction: ReviewDirection
    time_horizon: str = Field(alias="timeHorizon")
    rationale: str
    evidence_text: str = Field(alias="evidenceText")
    confidence: float
    tags: List[str]
    ambiguity_notes: List[str] = Field(alias="ambiguityNotes")
    action_chain: List[ReviewActionPayload] = Field(alias="actionChain")

class AssetFile(BaseModel):
    """
    The unified canonical contract sent back to the Next.js Frontend.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    size: str
    date: str
    type: str
    status: str
    workflow_stage: WorkflowStage = Field(alias="workflowStage")
    stage_badge: str = Field(alias="stageBadge")
    creator_name: str = Field(alias="creatorName")
    source_platform: str = Field(alias="sourcePlatform")
    content_type: str = Field(alias="contentType")
    content_id: str = Field(alias="contentId")
    source_path: Optional[str] = Field(default=None, alias="sourcePath")

    manifest_path: Optional[str] = Field(default=None, alias="manifestPath")
    evidence_path: Optional[str] = Field(default=None, alias="evidencePath")
    candidate_event_path: Optional[str] = Field(default=None, alias="candidateEventPath")
    approved_event_path: Optional[str] = Field(default=None, alias="approvedEventPath")

    summary: str
    tags: List[str]
    review_payload: Optional[ReviewPayload] = Field(default=None, alias="reviewPayload")

    # Source classification fields
    source_type: SourceType = Field(default="unknown", alias="sourceType")
    source_group_id: Optional[str] = Field(default=None, alias="sourceGroupId")
    source_group_name: Optional[str] = Field(default=None, alias="sourceGroupName")
    file_timestamp: Optional[str] = Field(default=None, alias="fileTimestamp")

    # Semantic display fields (LLM-enhanced)
    file_type: Optional[str] = Field(default=None, alias="fileType", description="Display-friendly file type: 聊天记录/图片/PDF/文档")
    source_name: Optional[str] = Field(default=None, alias="sourceName", description="Human-readable source name (e.g. feishu chat name)")
    semantic_title: Optional[str] = Field(default=None, alias="semanticTitle", description="LLM-generated short title summarizing content")
