export type WorkflowStage =
  | "intake"
  | "enrichment"
  | "library"
  | "parsing"
  | "extraction"
  | "review"
  | "backtest";

export type ReviewDirection =
  | "bullish"
  | "bearish"
  | "neutral"
  | "watchlist"
  | "risk_warning";

export type SourceType = "feishu" | "notebooklm" | "local" | "unknown";

export type ReviewAction = {
  id: string;
  actionType: string;
  instrumentType: string;
  triggerCondition: string;
  targetPriceLow: string;
  targetPriceHigh: string;
  confidence: number;
  status: "draft" | "active" | "watch";
};

export type ReviewPayload = {
  ticker: string;
  direction: ReviewDirection;
  timeHorizon: string;
  rationale: string;
  evidenceText: string;
  confidence: number;
  tags: string[];
  ambiguityNotes: string[];
  actionChain: ReviewAction[];
};

export type AssetFile = {
  id: string;
  name: string;
  size: string;
  date: string;
  type: string;
  status: string;
  workflowStage: WorkflowStage;
  stageBadge: string;
  creatorName: string;
  sourcePlatform: string;
  contentType: string;
  contentId: string;
  sourcePath?: string;
  manifestPath?: string;
  evidencePath?: string;
  candidateEventPath?: string;
  approvedEventPath?: string;
  summary: string;
  tags: string[];
  reviewPayload?: ReviewPayload;
  // Source classification fields
  sourceType: SourceType;
  sourceGroupId?: string;
  sourceGroupName?: string;
  fileTimestamp?: string;
  // Semantic display fields (LLM-enhanced)
  fileType?: string; // Display-friendly: 聊天记录/图片/PDF/文档
  sourceName?: string; // Human-readable source name (e.g. feishu chat name)
  semanticTitle?: string; // LLM-generated short title summarizing content
};

export type KOL = {
  id: string;
  name: string;
  platform: "feishu" | "wechat" | "bilibili";
  platformId: string;
  avatar?: string;
  overallScore: number;
  dimensionScores: {
    accuracy: number;
    timeliness: number;
    clarity: number;
    depth: number;
    consistency: number;
  };
  accuracy: number;
  avgReturn: number;
  totalOpinions: number;
  lastActive: string;
  tags: string[];
  enabled: boolean;
};

export type KOLTimelineEvent = {
  id: string;
  kolId: string;
  date: string;
  ticker: string;
  direction: "bullish" | "bearish" | "neutral";
  summary: string;
  return?: number;
  evidenceText?: string;
};

export type BacktestTask = {
  id: string;
  name: string;
  kolIds: string[];
  kolNames: string[];
  status: "pending" | "running" | "completed" | "failed";
  startDate: string;
  endDate: string;
  createdAt: string;
  completedAt?: string;
  config: {
    initialCapital: number;
    positionSize: number;
  };
  metrics?: {
    totalReturn: number;
    annualizedReturn: number;
    sharpeRatio: number;
    maxDrawdown: number;
    winRate: number;
    totalTrades: number;
  };
  trades?: Array<{
    id: string;
    ticker: string;
    direction: "long" | "short";
    entryDate: string;
    exitDate: string;
    entryPrice: number;
    exitPrice: number;
    return: number;
    opinionId: string;
  }>;
};

export type SourceGroup = {
  id: string;
  name: string;
  type: "feishu" | "notebooklm";
  fileCount: number;
  lastSync?: string;
};

// =============================================================================
// Lineage & Version Control
// =============================================================================

export type DataLineage = {
  original_content_id: string;
  original_source?: string;
  enrichment_content_ids: string[];
  segment_ids: string[];
  event_ids: string[];
  extraction_id?: string;
  pipeline_run_id?: string;
  created_at: string;
};

export type VersionInfo = {
  schema_version: string;
  extraction_config_hash?: string;
  model_version?: string;
  model_provider?: string;
  prompt_version?: string;
  prompt_hash?: string;
  created_at: string;
  modified_at?: string;
  modified_by?: string;
  temperature?: number;
  additional_params: Record<string, unknown>;
};

export type PipelineRunInfo = {
  run_id: string;
  started_at: string;
  completed_at?: string;
  config_snapshot: Record<string, unknown>;
  items_processed: number;
  items_failed: number;
  status: "running" | "completed" | "failed";
  error_message?: string;
};

export type LineageResponse = {
  ok: boolean;
  data?: {
    trade_action_id?: string;
    lineage?: DataLineage;
    summary?: string;
    original_content_id?: string;
    original_source?: string;
    segment_ids?: string[];
    event_ids?: string[];
    content_id?: string;
    action_count?: number;
    action_ids?: string[];
    segment_id?: string;
    event_id?: string;
  };
  error?: {
    code: string;
    message: string;
  };
};

export type LineageStatsResponse = {
  total_actions_tracked: number;
  total_contents: number;
  total_segments: number;
  total_events: number;
  active_pipeline_runs: number;
  completed_pipeline_runs: number;
};
