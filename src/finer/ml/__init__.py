"""ML Module — Machine Learning components for Finer.

This module provides:
- DPO (Direct Preference Optimization) training utilities
- KOL multi-dimensional scoring
- Sentiment analysis (rule-based and ML-based)
- Model configuration and management
- Training data processing pipelines
"""

from finer.ml.dpo_trainer import (
    DPOConfig,
    DPOExporter,
    DPOTrainingItem,
    DPODatasetStats,
    format_dpo_prompt,
    export_dpo_dataset,
    validate_dpo_data,
    TRADE_ACTION_SYSTEM_PROMPT,
    TRADE_ACTION_USER_TEMPLATE,
    TRADE_ACTION_JSON_SCHEMA,
)

from finer.ml.kol_scorer import (
    ScorerConfig,
    KOLScorer,
    DimensionScore,
    DimensionScores,
    compute_kol_score,
    # Task-specified exports
    DimensionWeights,
    ScoringExplanation,
    KOLScoreResult,
    DimensionScoresV2,
    KOLScorerV2,
)

from finer.ml.sentiment import (
    SentimentResult,
    BatchSentimentResult,
    SentimentAnalyzer,
    SentimentMode,
    RuleBasedSentimentEngine,
    RuleBasedSentimentAnalyzer,
    SentimentType,
    analyze_sentiment,
    # Legacy aliases
    SentimentBatchResult,
    batch_analyze_sentiment,
)

from finer.ml.model_config import (
    ModelType,
    ModelProvider,
    ModelConfig,
    ModelRegistry,
    MLConfigManager,
    get_ml_config,
)

__all__ = [
    # DPO
    "DPOConfig",
    "DPOExporter",
    "DPOTrainingItem",
    "DPODatasetStats",
    "format_dpo_prompt",
    "export_dpo_dataset",
    "validate_dpo_data",
    "TRADE_ACTION_SYSTEM_PROMPT",
    "TRADE_ACTION_USER_TEMPLATE",
    "TRADE_ACTION_JSON_SCHEMA",
    # KOL Scorer
    "ScorerConfig",
    "KOLScorer",
    "DimensionScore",
    "DimensionScores",
    "compute_kol_score",
    # KOL Scorer V2 (Task-specified)
    "DimensionWeights",
    "ScoringExplanation",
    "KOLScoreResult",
    "DimensionScoresV2",
    "KOLScorerV2",
    # Sentiment
    "SentimentResult",
    "BatchSentimentResult",
    "SentimentAnalyzer",
    "SentimentMode",
    "RuleBasedSentimentEngine",
    "RuleBasedSentimentAnalyzer",
    "SentimentType",
    "analyze_sentiment",
    "SentimentBatchResult",
    "batch_analyze_sentiment",
    # Model Config
    "ModelType",
    "ModelProvider",
    "ModelConfig",
    "ModelRegistry",
    "MLConfigManager",
    "get_ml_config",
]
