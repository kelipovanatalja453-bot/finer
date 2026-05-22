"""ModelRouter — task-type-based LLM routing with automatic fallback.

Routes LLM calls to the appropriate registry based on task_type:
- "text"    → TextModelRegistry (DeepSeek, Qwen, GLM)
- "vision"  → VisionModelRegistry (MiMo-V2.5)
- "reasoning" → ReasoningModelRegistry (MiMo-V2.5-Pro)

Each call automatically falls back to the next available model in the
selected registry when the primary model fails.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Type

from finer.llm.client import LLMClient
from finer.model_config import (
    BaseModelRegistry,
    get_text_registry,
    get_vision_registry,
    get_reasoning_registry,
)

logger = logging.getLogger(__name__)

_TASK_TYPE_TO_REGISTRY = {
    "text": get_text_registry,
    "vision": get_vision_registry,
    "reasoning": get_reasoning_registry,
}


class ModelRouter:
    """Routes LLM calls to the right registry based on task_type.

    On each call, tries every available model in the registry (ordered by
    priority). If a model fails (returns None or raises), it is marked as
    failed and the next model is tried. Returns None only if all models fail.

    Usage:
        router = ModelRouter()
        response = router.call("Summarize this text", task_type="text")
        result = router.call_json("Extract intents", response_model=IntentModel)
    """

    def __init__(
        self,
        text_registry: Optional[BaseModelRegistry] = None,
        vision_registry: Optional[BaseModelRegistry] = None,
        reasoning_registry: Optional[BaseModelRegistry] = None,
    ):
        self._registries: Dict[str, BaseModelRegistry] = {}
        if text_registry is not None:
            self._registries["text"] = text_registry
        if vision_registry is not None:
            self._registries["vision"] = vision_registry
        if reasoning_registry is not None:
            self._registries["reasoning"] = reasoning_registry

    def _get_registry(self, task_type: str) -> BaseModelRegistry:
        """Get or lazily initialize the registry for a task type."""
        if task_type not in self._registries:
            factory = _TASK_TYPE_TO_REGISTRY.get(task_type)
            if factory is None:
                raise ValueError(
                    f"Unknown task_type '{task_type}'. "
                    f"Supported: {list(_TASK_TYPE_TO_REGISTRY.keys())}"
                )
            self._registries[task_type] = factory()
        return self._registries[task_type]

    def call(
        self,
        prompt: str,
        *,
        task_type: str = "text",
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """Send a prompt to the appropriate model with automatic fallback.

        Tries each available model in the registry (ordered by priority).
        If a model fails, marks it failed and retries with the next one.

        Args:
            prompt: The user prompt text.
            task_type: One of "text", "vision", "reasoning".
            system_prompt: Optional system message prepended to the conversation.
            temperature: Sampling temperature.
            max_tokens: Max tokens in the response.

        Returns:
            The model's response string, or None if all models fail.
        """
        registry = self._get_registry(task_type)
        n_models = len(registry.models)

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error: Optional[str] = None
        for _ in range(n_models):
            client = LLMClient.from_registry(registry)
            if client is None:
                break  # No more available models

            model_name = client.model
            try:
                result = client.chat(messages, temperature=temperature, max_tokens=max_tokens)
                if result is not None:
                    return result
                last_error = f"Model {model_name} returned None"
                registry.mark_failed(model_name, last_error)
            except Exception as e:
                last_error = f"Model {model_name} raised {type(e).__name__}: {e}"
                registry.mark_failed(model_name, last_error)

        logger.error(f"All models failed for task_type='{task_type}': {last_error}")
        return None

    def call_json(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        response_model: Optional[Type] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        task_type: str = "text",
    ) -> Optional[Dict[str, Any]]:
        """Send a prompt expecting JSON output, optionally validated against a Pydantic model.

        Args:
            prompt: The user prompt text.
            system_prompt: Optional system message.
            response_model: Optional Pydantic model to validate the response against.
            temperature: Sampling temperature.
            max_tokens: Max tokens in the response.
            task_type: One of "text", "vision", "reasoning".

        Returns:
            Parsed JSON dict, or None on failure.
        """
        raw = self.call(
            prompt,
            task_type=task_type,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if raw is None:
            return None

        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from model response: {raw[:200]}")
            return None

        if response_model is not None:
            try:
                validated = response_model.model_validate(data)
                return validated.model_dump()
            except Exception as e:
                logger.warning(f"Response validation failed against {response_model.__name__}: {e}")
                return data  # Return raw parsed JSON even if validation fails

        return data
