"""Tests for finer.llm.client."""

from finer.llm.client import LLMClient


def test_llm_client_model_property() -> None:
    client = LLMClient(model="test-model")

    assert client.model == "test-model"


def test_llm_client_merges_provider_and_call_extra_body(monkeypatch) -> None:
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class FakeHTTPXClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("finer.llm.client.httpx.Client", FakeHTTPXClient)

    client = LLMClient(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="provider-model",
        extra_body={"stream": False, "thinking": {"type": "disabled"}},
    )

    result = client.chat(
        [{"role": "user", "content": "hello"}],
        extra_body={"stream": True, "metadata": {"probe": True}},
    )

    assert result == "ok"
    assert captured["json"]["stream"] is True
    assert captured["json"]["thinking"] == {"type": "disabled"}
    assert captured["json"]["metadata"] == {"probe": True}
