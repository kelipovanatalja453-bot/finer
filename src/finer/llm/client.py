"""Unified LLM client with model fallback and proxy compatibility.

Consolidates the three previous implementations:
- llm_client.LLMClient (explicit params, vision support)
- enrichment.LLMClient (registry-based, model fallback)
- services.llm.LLMService (stub, replaced by real implementation)
"""

from __future__ import annotations

import os
import json
import logging
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified HTTP client for LLM APIs with model fallback and curl User-Agent.

    Supports two construction modes:
    1. Explicit: LLMClient(api_key=..., base_url=..., model=...)
    2. Registry-based: LLMClient.from_registry(registry) or LLMClient() with auto-config
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        timeout: float = 60.0,
        registry: Optional[Any] = None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/") if base_url else None
        self._model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._registry = registry

    # -------------------------------------------------------------------------
    # Factory methods
    # -------------------------------------------------------------------------

    @classmethod
    def from_registry(cls, registry: Any, **kwargs) -> Optional["LLMClient"]:
        """Create a client from a model registry with auto-config."""
        model_config = registry.get_available_model()
        if not model_config:
            return None

        api_key = os.getenv(model_config.api_key_env)
        if not api_key:
            return None

        return cls(
            api_key=api_key,
            base_url=model_config.base_url,
            model=model_config.name,
            max_tokens=getattr(model_config, "max_tokens", 4096),
            registry=registry,
            **kwargs,
        )

    @classmethod
    def auto(cls, **kwargs) -> Optional["LLMClient"]:
        """Create a client using the default text registry."""
        try:
            from finer.model_config import get_text_registry
            return cls.from_registry(get_text_registry(), **kwargs)
        except Exception:
            logger.warning("Failed to create auto-configured LLM client")
            return None

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _resolve_config(self) -> Optional[Dict[str, Any]]:
        """Resolve API key, base_url, model — supports registry fallback."""
        if self._api_key and self._base_url and self._model:
            return {
                "api_key": self._api_key,
                "base_url": self._base_url,
                "model": self._model,
            }

        # Registry-based fallback
        if self._registry:
            model_config = self._registry.get_available_model()
            if not model_config:
                logger.error("No available models in registry")
                return None

            api_key = os.getenv(model_config.api_key_env)
            if not api_key:
                self._registry.mark_failed(model_config.name, "No API key")
                return self._resolve_config()  # Retry with next model

            return {
                "api_key": api_key,
                "base_url": model_config.base_url,
                "model": model_config.name,
            }

        logger.error("LLMClient not configured: provide api_key/base_url/model or registry")
        return None

    def _handle_error(self, model: str, error_msg: str) -> None:
        """Mark model as failed in registry if quota/rate-limit error."""
        if self._registry and any(
            x in error_msg.lower() for x in ["quota", "rate", "limit", "exhausted"]
        ):
            self._registry.mark_failed(model, error_msg)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def chat(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.3,
    ) -> Optional[str]:
        """Send a chat completion request with full message dicts."""
        config = self._resolve_config()
        if not config:
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
            "User-Agent": "curl/8.0",
        }

        data = {
            "model": config["model"],
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature,
        }

        try:
            with httpx.Client(timeout=self.timeout, http2=False) as client:
                response = client.post(
                    f"{config['base_url']}/chat/completions",
                    headers=headers,
                    json=data,
                )

                if response.status_code == 200:
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    error_msg = response.text[:200]
                    self._handle_error(config["model"], error_msg)
                    logger.error(f"LLM API error: {response.status_code} - {error_msg}")
                    return None

        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return None

    def chat_prompt(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.3,
        system: Optional[str] = None,
    ) -> Optional[str]:
        """Convenience method: send a plain string prompt."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, max_tokens=max_tokens, temperature=temperature)

    def chat_with_images(
        self,
        text: str,
        image_base64: str,
        mime_type: str = "image/png",
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """Send a chat completion request with an image (vision)."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}"
                        },
                    },
                ],
            }
        ]
        return self.chat(messages, max_tokens=max_tokens)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = True,
    ) -> Optional[Any]:
        """Chat completion with optional JSON parsing (replaces LLMService)."""
        raw = self.chat(messages)
        if raw is None:
            return None
        if json_mode:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw
        return raw
