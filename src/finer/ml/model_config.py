"""ML Model Configuration — Centralized model registry and configuration.

This module provides:
1. Model registry for all ML models used in Finer
2. Version management and deprecation
3. A/B testing support
4. Model-specific configuration (hyperparameters, etc.)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class ModelType(str, Enum):
    """Types of ML models used in Finer."""
    SENTIMENT = "sentiment"
    EXTRACTION = "extraction"
    ENTITY = "entity"
    KOL_SCORER = "kol_scorer"
    EMBEDDING = "embedding"


class ModelProvider(str, Enum):
    """Model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GLM = "glm"
    QWEN = "qwen"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"


# =============================================================================
# Model Configuration
# =============================================================================

@dataclass
class ModelConfig:
    """Configuration for a single model."""
    name: str
    model_type: ModelType
    provider: ModelProvider

    # Model identification
    model_id: str  # Full model ID (e.g., "ProsusAI/finbert")
    version: str = "v1.0"

    # Model settings
    enabled: bool = True
    is_primary: bool = False
    is_fallback: bool = False

    # Hyperparameters
    max_input_length: int = 512
    batch_size: int = 32
    temperature: float = 0.0
    timeout: float = 30.0

    # Resource requirements
    requires_gpu: bool = False
    memory_gb: float = 1.0

    # Metadata
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)

    # Custom parameters
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelRegistry:
    """Registry of all models."""
    models: Dict[str, ModelConfig] = field(default_factory=dict)

    # Default model for each type
    defaults: Dict[ModelType, str] = field(default_factory=dict)

    def register(self, config: ModelConfig) -> None:
        """Register a model."""
        self.models[config.name] = config
        if config.is_primary:
            self.defaults[config.model_type] = config.name

    def get(self, name: str) -> Optional[ModelConfig]:
        """Get model by name."""
        return self.models.get(name)

    def get_default(self, model_type: ModelType) -> Optional[ModelConfig]:
        """Get default model for a type."""
        default_name = self.defaults.get(model_type)
        if default_name:
            return self.models.get(default_name)
        return None

    def get_fallbacks(self, model_type: ModelType) -> List[ModelConfig]:
        """Get fallback models for a type."""
        return [
            m for m in self.models.values()
            if m.model_type == model_type and m.is_fallback and m.enabled
        ]

    def list_by_type(self, model_type: ModelType) -> List[ModelConfig]:
        """List all models of a type."""
        return [
            m for m in self.models.values()
            if m.model_type == model_type and m.enabled
        ]


# =============================================================================
# Default Models
# =============================================================================

def create_default_registry() -> ModelRegistry:
    """Create registry with default models."""
    registry = ModelRegistry()

    # Sentiment models
    registry.register(ModelConfig(
        name="finbert",
        model_type=ModelType.SENTIMENT,
        provider=ModelProvider.HUGGINGFACE,
        model_id="ProsusAI/finbert",
        version="v1.0",
        is_primary=True,
        description="FinBERT: Financial sentiment analysis model",
        tags=["financial", "english", "transformer"],
        requires_gpu=False,
        memory_gb=0.5,
    ))

    registry.register(ModelConfig(
        name="rule_based_sentiment",
        model_type=ModelType.SENTIMENT,
        provider=ModelProvider.LOCAL,
        model_id="finer/sentiment_rules",
        version="v1.0",
        is_fallback=True,
        description="Rule-based sentiment analyzer",
        tags=["rule-based", "fast", "bilingual"],
        requires_gpu=False,
        memory_gb=0.0,
    ))

    # Extraction models (LLM-based)
    registry.register(ModelConfig(
        name="qwen-max-extraction",
        model_type=ModelType.EXTRACTION,
        provider=ModelProvider.QWEN,
        model_id="qwen-max",
        version="v1.0",
        is_primary=True,
        description="Qwen Max for trade action extraction",
        tags=["llm", "chinese", "structured-output"],
        max_input_length=8192,
        temperature=0.0,
        params={
            "use_instructor": True,
            "response_model": "TradeAction",
        },
    ))

    registry.register(ModelConfig(
        name="glm-extraction",
        model_type=ModelType.EXTRACTION,
        provider=ModelProvider.GLM,
        model_id="glm-5.1",
        version="v1.0",
        is_fallback=True,
        description="GLM-5.1 for trade action extraction",
        tags=["llm", "chinese", "structured-output"],
        max_input_length=8192,
        temperature=0.0,
    ))

    # Entity recognition
    registry.register(ModelConfig(
        name="rule_based_entity",
        model_type=ModelType.ENTITY,
        provider=ModelProvider.LOCAL,
        model_id="finer/entity_rules",
        version="v1.0",
        is_primary=True,
        description="Rule-based entity recognizer with financial dictionary",
        tags=["rule-based", "financial-entities"],
    ))

    # KOL scorer
    registry.register(ModelConfig(
        name="weighted_scorer",
        model_type=ModelType.KOL_SCORER,
        provider=ModelProvider.LOCAL,
        model_id="finer/kol_scorer",
        version="v1.0",
        is_primary=True,
        description="Multi-dimensional KOL scorer with configurable weights",
        tags=["scoring", "explainable"],
        params={
            "weights": {
                "accuracy": 0.30,
                "timeliness": 0.15,
                "return": 0.30,
                "consistency": 0.15,
                "depth": 0.10,
            },
        },
    ))

    return registry


# =============================================================================
# Configuration Manager
# =============================================================================

class MLConfigManager:
    """Manager for ML model configurations."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self.registry = create_default_registry()

        if config_path and config_path.exists():
            self._load_config(config_path)

    def _load_config(self, path: Path) -> None:
        """Load configuration from YAML file."""
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))

            # Load model configurations
            for model_data in data.get("models", []):
                config = ModelConfig(
                    name=model_data["name"],
                    model_type=ModelType(model_data["type"]),
                    provider=ModelProvider(model_data["provider"]),
                    model_id=model_data["model_id"],
                    version=model_data.get("version", "v1.0"),
                    enabled=model_data.get("enabled", True),
                    is_primary=model_data.get("is_primary", False),
                    is_fallback=model_data.get("is_fallback", False),
                    max_input_length=model_data.get("max_input_length", 512),
                    batch_size=model_data.get("batch_size", 32),
                    temperature=model_data.get("temperature", 0.0),
                    params=model_data.get("params", {}),
                )
                self.registry.register(config)

            logger.info(f"Loaded ML config from {path}")

        except Exception as e:
            logger.warning(f"Failed to load ML config: {e}")

    def save_config(self, path: Path) -> None:
        """Save configuration to YAML file."""
        data = {
            "models": [
                {
                    "name": m.name,
                    "type": m.model_type.value,
                    "provider": m.provider.value,
                    "model_id": m.model_id,
                    "version": m.version,
                    "enabled": m.enabled,
                    "is_primary": m.is_primary,
                    "is_fallback": m.is_fallback,
                    "max_input_length": m.max_input_length,
                    "batch_size": m.batch_size,
                    "temperature": m.temperature,
                    "params": m.params,
                }
                for m in self.registry.models.values()
            ],
            "defaults": {
                t.value: n for t, n in self.registry.defaults.items()
            },
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
        logger.info(f"Saved ML config to {path}")

    def get_model(self, model_type: ModelType) -> ModelConfig:
        """Get the active model for a type (with fallback support)."""
        # Try primary
        primary = self.registry.get_default(model_type)
        if primary and primary.enabled:
            return primary

        # Try fallbacks
        fallbacks = self.registry.get_fallbacks(model_type)
        if fallbacks:
            return fallbacks[0]

        raise ValueError(f"No enabled model for type: {model_type}")


# =============================================================================
# Global Configuration
# =============================================================================

_config_manager: Optional[MLConfigManager] = None


def get_ml_config(config_path: Optional[Path] = None) -> MLConfigManager:
    """Get or create global ML config manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = MLConfigManager(config_path)
    return _config_manager
