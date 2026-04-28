"""Unified LLM client package.

Usage:
    from finer.llm import LLMClient

    # Explicit configuration
    client = LLMClient(api_key="...", base_url="...", model="qwen-plus")

    # Registry-based with auto-fallback
    client = LLMClient.from_registry(get_text_registry())

    # Auto-configured from default text registry
    client = LLMClient.auto()

    # Chat with messages
    response = client.chat([{"role": "user", "content": "Hello"}])

    # Chat with plain prompt
    response = client.chat_prompt("Hello")

    # Vision
    response = client.chat_with_images("Describe this", base64_data)
"""

from finer.llm.client import LLMClient

__all__ = ["LLMClient"]
