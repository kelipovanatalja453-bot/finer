"""Model Config — Multi-model configuration with automatic fallback.

Supports multiple vision and text models with automatic switching
when quota is exhausted.

Text tasks: GLM-5.1 via SVIPS proxy (primary)
Vision tasks: Qwen-VL-Plus via Dashscope (primary, most stable)
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    """Supported model providers."""
    GLM_SVIPS = "glm_svips"  # GLM via SVIPS proxy (text only)
    DASHSCOPE = "dashscope"  # Alibaba Cloud (Qwen) - vision + text fallback
    OPENAI = "openai"
    ZHIPU = "zhipu"  # GLM native
    DEEPSEEK = "deepseek"


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    name: str
    provider: ModelProvider
    api_key_env: str  # Environment variable name for API key
    base_url: Optional[str] = None
    max_tokens: int = 1024
    enabled: bool = True
    priority: int = 0  # Lower = higher priority


@dataclass
class BaseModelRegistry:
    """Base registry with shared fallback logic."""

    models: List[ModelConfig] = field(default_factory=list)
    failed_models: Dict[str, str] = field(default_factory=dict)

    def get_available_model(self) -> Optional[ModelConfig]:
        """Get the highest priority available model."""
        for model in sorted(self.models, key=lambda m: m.priority):
            if not model.enabled:
                continue
            if model.name in self.failed_models:
                continue
            api_key = os.getenv(model.api_key_env)
            if api_key:
                return model
        return None

    def mark_failed(self, model_name: str, error: str):
        """Mark a model as failed, trigger fallback."""
        self.failed_models[model_name] = error
        logger.warning(f"Model {model_name} failed: {error}. Trying fallback...")

    def reset_failures(self):
        """Reset failed models (e.g., after quota refresh)."""
        self.failed_models.clear()
        logger.info("Reset all model failures")


@dataclass
class VisionModelRegistry(BaseModelRegistry):
    """Registry of vision models with automatic fallback."""

    models: List[ModelConfig] = field(default_factory=lambda: [
        ModelConfig(
            name="qwen-vl-plus",
            provider=ModelProvider.DASHSCOPE,
            api_key_env="DASHSCOPE_API_KEY",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            max_tokens=2048,
            priority=0,
        ),
        ModelConfig(
            name="GLM-5.1",
            provider=ModelProvider.GLM_SVIPS,
            api_key_env="GLM_API_KEY",
            base_url="https://api.svips.org/v1",
            max_tokens=4096,
            priority=1,
        ),
        ModelConfig(
            name="qwen-vl-max",
            provider=ModelProvider.DASHSCOPE,
            api_key_env="DASHSCOPE_API_KEY",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            max_tokens=2048,
            priority=2,
        ),
    ])


@dataclass
class TextModelRegistry(BaseModelRegistry):
    """Registry of text/chat models for L1 enrichment."""

    models: List[ModelConfig] = field(default_factory=lambda: [
        ModelConfig(
            name="qwen-plus",
            provider=ModelProvider.DASHSCOPE,
            api_key_env="DASHSCOPE_API_KEY",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            max_tokens=4096,
            priority=0,
        ),
        ModelConfig(
            name="GLM-5.1",
            provider=ModelProvider.GLM_SVIPS,
            api_key_env="GLM_API_KEY",
            base_url="https://api.svips.org/v1",
            max_tokens=4096,
            priority=1,
        ),
    ])


# Global registry instances
_vision_registry: Optional[VisionModelRegistry] = None
_text_registry: Optional[TextModelRegistry] = None


def get_vision_registry() -> VisionModelRegistry:
    """Get or create the global vision model registry."""
    global _vision_registry
    if _vision_registry is None:
        _vision_registry = VisionModelRegistry()
    return _vision_registry


def get_text_registry() -> TextModelRegistry:
    """Get or create the global text model registry."""
    global _text_registry
    if _text_registry is None:
        _text_registry = TextModelRegistry()
    return _text_registry
