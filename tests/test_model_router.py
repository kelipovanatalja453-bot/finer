"""Tests for ModelRouter — task-type-based LLM routing with fallback."""

from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from finer.model_config import (
    BaseModelRegistry,
    ModelConfig,
    ModelProvider,
    ReasoningModelRegistry,
    TextModelRegistry,
    VisionModelRegistry,
    get_reasoning_registry,
)
from finer.llm.router import ModelRouter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_text_registry() -> BaseModelRegistry:
    """A text registry with one fake model."""
    return TextModelRegistry(
        models=[
            ModelConfig(
                name="test-text-model",
                provider=ModelProvider.DEEPSEEK,
                api_key_env="TEST_TEXT_API_KEY",
                base_url="https://test.example.com/v1",
                max_tokens=4096,
                priority=0,
            ),
        ]
    )


@pytest.fixture()
def mock_reasoning_registry() -> BaseModelRegistry:
    """A reasoning registry with one fake model."""
    return ReasoningModelRegistry(
        models=[
            ModelConfig(
                name="test-reasoning-model",
                provider=ModelProvider.MIMO,
                api_key_env="TEST_REASONING_API_KEY",
                base_url="https://test-reasoning.example.com/v1",
                max_tokens=8192,
                priority=0,
                api_key_header="api-key",
                api_key_scheme=None,
                max_tokens_field="max_completion_tokens",
            ),
        ]
    )


@pytest.fixture()
def router(
    mock_text_registry: BaseModelRegistry,
    mock_reasoning_registry: BaseModelRegistry,
) -> ModelRouter:
    """A ModelRouter with mocked registries."""
    return ModelRouter(
        text_registry=mock_text_registry,
        reasoning_registry=mock_reasoning_registry,
    )


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------


class TestModelRouterInit:
    def test_init_with_explicit_registries(self, mock_text_registry):
        router = ModelRouter(text_registry=mock_text_registry)
        assert "text" in router._registries

    def test_init_empty_uses_lazy_registries(self):
        router = ModelRouter()
        # Should not raise on init — registries are lazy
        assert len(router._registries) == 0

    def test_unknown_task_type_raises(self):
        router = ModelRouter()
        with pytest.raises(ValueError, match="Unknown task_type"):
            router._get_registry("unknown_type")


# ---------------------------------------------------------------------------
# call() tests
# ---------------------------------------------------------------------------


class TestModelRouterCall:
    @patch("finer.llm.router.LLMClient")
    def test_call_text_returns_response(self, MockLLMClient, router):
        mock_client = MagicMock()
        mock_client.chat.return_value = "Hello from model"
        MockLLMClient.from_registry.return_value = mock_client

        result = router.call("test prompt", task_type="text")
        assert result == "Hello from model"
        mock_client.chat.assert_called_once()

    @patch("finer.llm.router.LLMClient")
    def test_call_with_system_prompt(self, MockLLMClient, router):
        mock_client = MagicMock()
        mock_client.chat.return_value = "response"
        MockLLMClient.from_registry.return_value = mock_client

        router.call("test", task_type="text", system_prompt="You are helpful")
        call_args = mock_client.chat.call_args
        messages = call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful"
        assert messages[1]["role"] == "user"

    @patch("finer.llm.router.LLMClient")
    def test_call_no_system_prompt(self, MockLLMClient, router):
        mock_client = MagicMock()
        mock_client.chat.return_value = "response"
        MockLLMClient.from_registry.return_value = mock_client

        router.call("test", task_type="text")
        call_args = mock_client.chat.call_args
        messages = call_args[0][0]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    @patch("finer.llm.router.LLMClient")
    def test_call_returns_none_when_no_client(self, MockLLMClient, router):
        MockLLMClient.from_registry.return_value = None
        result = router.call("test", task_type="text")
        assert result is None

    @patch("finer.llm.router.LLMClient")
    def test_call_reasoning_uses_reasoning_registry(self, MockLLMClient, router):
        mock_client = MagicMock()
        mock_client.chat.return_value = "reasoning result"
        MockLLMClient.from_registry.return_value = mock_client

        result = router.call("complex task", task_type="reasoning")
        assert result == "reasoning result"
        # Verify from_registry was called with the reasoning registry
        MockLLMClient.from_registry.assert_called_once()
        registry_arg = MockLLMClient.from_registry.call_args[0][0]
        assert isinstance(registry_arg, ReasoningModelRegistry)


# ---------------------------------------------------------------------------
# call_json() tests
# ---------------------------------------------------------------------------


class TestModelRouterCallJson:
    @patch("finer.llm.router.LLMClient")
    def test_call_json_parses_valid_json(self, MockLLMClient, router):
        mock_client = MagicMock()
        mock_client.chat.return_value = '{"key": "value"}'
        MockLLMClient.from_registry.return_value = mock_client

        result = router.call_json("extract data", task_type="text")
        assert result == {"key": "value"}

    @patch("finer.llm.router.LLMClient")
    def test_call_json_strips_markdown_fences(self, MockLLMClient, router):
        mock_client = MagicMock()
        mock_client.chat.return_value = '```json\n{"key": "value"}\n```'
        MockLLMClient.from_registry.return_value = mock_client

        result = router.call_json("extract data", task_type="text")
        assert result == {"key": "value"}

    @patch("finer.llm.router.LLMClient")
    def test_call_json_returns_none_on_invalid_json(self, MockLLMClient, router):
        mock_client = MagicMock()
        mock_client.chat.return_value = "not json at all"
        MockLLMClient.from_registry.return_value = mock_client

        result = router.call_json("extract data", task_type="text")
        assert result is None

    @patch("finer.llm.router.LLMClient")
    def test_call_json_with_response_model(self, MockLLMClient, router):
        from pydantic import BaseModel

        class MyModel(BaseModel):
            name: str
            value: int

        mock_client = MagicMock()
        mock_client.chat.return_value = '{"name": "test", "value": 42}'
        MockLLMClient.from_registry.return_value = mock_client

        result = router.call_json("extract", response_model=MyModel, task_type="text")
        assert result == {"name": "test", "value": 42}

    @patch("finer.llm.router.LLMClient")
    def test_call_json_returns_none_when_no_response(self, MockLLMClient, router):
        MockLLMClient.from_registry.return_value = None
        result = router.call_json("test", task_type="text")
        assert result is None


# ---------------------------------------------------------------------------
# ReasoningModelRegistry tests
# ---------------------------------------------------------------------------


class TestReasoningModelRegistry:
    def test_default_model_is_mimo_v25_pro(self):
        registry = ReasoningModelRegistry()
        assert len(registry.models) == 1
        assert registry.models[0].name == "mimo-v2.5-pro"

    def test_default_base_url(self):
        registry = ReasoningModelRegistry()
        assert registry.models[0].base_url == "https://token-plan-cn.xiaomimimo.com/v1"

    def test_auth_header_is_api_key(self):
        registry = ReasoningModelRegistry()
        assert registry.models[0].api_key_header == "api-key"
        assert registry.models[0].api_key_scheme is None

    def test_max_tokens_field(self):
        registry = ReasoningModelRegistry()
        assert registry.models[0].max_tokens_field == "max_completion_tokens"

    def test_mimo_extra_body_disables_thinking(self):
        registry = ReasoningModelRegistry()
        assert registry.models[0].extra_body == {
            "stream": False,
            "thinking": {"type": "disabled"},
        }

    def test_get_reasoning_registry_singleton(self):
        r1 = get_reasoning_registry()
        r2 = get_reasoning_registry()
        assert r1 is r2


class TestTextModelRegistry:
    def test_qwen_plus_uses_dashscope_bearer_and_max_tokens(self):
        registry = TextModelRegistry()
        qwen = next(model for model in registry.models if model.name == "qwen-plus")

        assert qwen.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert qwen.api_key_env == "DASHSCOPE_API_KEY"
        assert qwen.api_key_header == "Authorization"
        assert qwen.api_key_scheme == "Bearer"
        assert qwen.max_tokens_field == "max_tokens"
        assert qwen.extra_body == {}

    def test_env_mimo_text_model_gets_mimo_extra_body(self, monkeypatch):
        monkeypatch.setenv("FINER_LLM_MODEL", "mimo-v2.5-pro")
        registry = TextModelRegistry()

        assert registry.models[0].extra_body == {
            "stream": False,
            "thinking": {"type": "disabled"},
        }


class TestModelRouterFallback:
    """Test that ModelRouter falls back to next model on failure."""

    def test_primary_failure_falls_back_to_secondary(self):
        """When primary model fails, router should try the next model."""
        registry = TextModelRegistry(models=[
            ModelConfig(
                name="primary-model",
                provider=ModelProvider.DEEPSEEK,
                api_key_env="FAKE_KEY_ENV_1",
                base_url="https://api.deepseek.com",
                max_tokens=1024,
                priority=0,
            ),
            ModelConfig(
                name="secondary-model",
                provider=ModelProvider.DASHSCOPE,
                api_key_env="FAKE_KEY_ENV_2",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                max_tokens=1024,
                priority=1,
            ),
        ])

        models_called = []

        def make_client_side_effect(registry_obj, **kwargs):
            model = registry_obj.get_available_model()
            if model is None:
                return None
            mock_client = MagicMock()
            mock_client.model = model.name

            def chat_fn(messages, **kw):
                models_called.append(model.name)
                if model.name == "primary-model":
                    return None  # Primary fails
                return '{"ok": true}'  # Secondary succeeds

            mock_client.chat = chat_fn
            return mock_client

        router = ModelRouter(text_registry=registry)
        with patch("finer.llm.client.LLMClient.from_registry", side_effect=make_client_side_effect), \
             patch.dict("os.environ", {"FAKE_KEY_ENV_1": "fake1", "FAKE_KEY_ENV_2": "fake2"}):
            result = router.call("test prompt")

        assert result == '{"ok": true}'
        assert len(models_called) == 2
        assert models_called[0] == "primary-model"
        assert models_called[1] == "secondary-model"

    def test_all_models_fail_returns_none(self):
        """When all models fail, router returns None."""
        registry = TextModelRegistry(models=[
            ModelConfig(
                name="model-a",
                provider=ModelProvider.DEEPSEEK,
                api_key_env="FAKE_KEY_ENV_1",
                base_url="https://api.deepseek.com",
                max_tokens=1024,
                priority=0,
            ),
            ModelConfig(
                name="model-b",
                provider=ModelProvider.DASHSCOPE,
                api_key_env="FAKE_KEY_ENV_2",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                max_tokens=1024,
                priority=1,
            ),
        ])

        def make_client_side_effect(registry_obj, **kwargs):
            model = registry_obj.get_available_model()
            if model is None:
                return None
            mock_client = MagicMock()
            mock_client.model = model.name
            mock_client.chat.return_value = None  # All fail
            return mock_client

        router = ModelRouter(text_registry=registry)
        with patch("finer.llm.client.LLMClient.from_registry", side_effect=make_client_side_effect), \
             patch.dict("os.environ", {"FAKE_KEY_ENV_1": "fake1", "FAKE_KEY_ENV_2": "fake2"}):
            result = router.call("test prompt")

        assert result is None
        assert "model-a" in registry.failed_models
        assert "model-b" in registry.failed_models
