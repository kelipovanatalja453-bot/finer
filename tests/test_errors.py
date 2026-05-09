"""Tests for canonical Finer error codes and API handlers."""

from __future__ import annotations

import re

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from finer.errors import (
    ERROR_CODE_DEFINITIONS,
    ErrorCode,
    FinerExternalServiceError,
    FinerError,
    get_error_info,
    list_error_codes,
    lookup_error_codes,
    parse_error_code,
    register_error_handlers,
)


CODE_PATTERN = re.compile(r"^[A-Z0-9]+_[A-Z]+_[0-9]{3}$")


def test_error_catalog_is_complete_and_searchable() -> None:
    assert len(ErrorCode) == 104
    assert len(ERROR_CODE_DEFINITIONS) == len(ErrorCode)
    assert len(list_error_codes()) == len(ErrorCode)

    for code in ErrorCode:
        info = get_error_info(code)
        assert info.code == code
        assert CODE_PATTERN.match(code.value)
        assert info.title
        assert info.root_cause
        assert info.fix_hint
        assert 400 <= info.status_code <= 599
        assert not code.value.startswith(("L0_", "L1_", "L2_", "L3_", "L4_", "L5_", "L6_", "L7_", "L8_"))
        assert not code.value.startswith(("V0_", "V1_", "V2_", "V3_", "V4_", "V5_", "V6_"))

    assert parse_error_code(ErrorCode.F15_IN_001) == ("F15", "IN", 1)
    assert [info.code for info in lookup_error_codes(domain="WX")] == [
        ErrorCode.WX_AUTH_001,
        ErrorCode.WX_EXT_001,
        ErrorCode.WX_TMO_001,
        ErrorCode.WX_NTF_001,
    ]


def test_finer_error_payload_uses_catalog_defaults() -> None:
    error = FinerExternalServiceError(
        ErrorCode.LLM_EXT_002,
        "Rate limited",
        service="mimo-api",
        details={"retry_after": 60},
    )

    assert error.status_code == 429
    assert error.error_code_str == "LLM_EXT_002"
    assert str(error) == "[LLM_EXT_002] Rate limited"
    assert error.to_payload() == {
        "ok": False,
        "error": {
            "code": "LLM_EXT_002",
            "message": "Rate limited",
            "details": {"retry_after": 60, "service": "mimo-api"},
        },
    }


def test_fastapi_handlers_serialize_finer_error() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise FinerExternalServiceError(
            ErrorCode.WX_EXT_001,
            "Exporter not responding",
            service="wechat-exporter",
        )

    client = TestClient(app)
    response = client.get("/boom", headers={"X-Request-ID": "req-1"})

    assert response.status_code == 502
    assert response.json() == {
        "ok": False,
        "error": {
            "code": "WX_EXT_001",
            "message": "Exporter not responding",
            "details": {
                "service": "wechat-exporter",
                "request_id": "req-1",
            },
        },
    }


def test_fastapi_handlers_wrap_legacy_http_exception() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/missing")
    def missing() -> None:
        raise HTTPException(status_code=404, detail="Session not found")

    client = TestClient(app)
    response = client.get("/missing", headers={"X-Request-ID": "req-404"})
    data = response.json()

    assert response.status_code == 404
    assert data["ok"] is False
    assert data["error"]["code"] == "SYS_NTF_001"
    assert data["error"]["message"] == "Session not found"
    assert data["error"]["details"]["request_id"] == "req-404"


def test_fastapi_handlers_wrap_request_validation_error() -> None:
    class Payload(BaseModel):
        content_id: str

    app = FastAPI()
    register_error_handlers(app)

    @app.post("/payload")
    def payload(_: Payload) -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    response = client.post("/payload", json={}, headers={"X-Request-ID": "req-422"})
    data = response.json()

    assert response.status_code == 422
    assert data["ok"] is False
    assert data["error"]["code"] == "SYS_IN_002"
    assert data["error"]["details"]["request_id"] == "req-422"
    assert data["error"]["details"]["errors"][0]["type"] == "missing"


def test_fastapi_handlers_wrap_unexpected_errors() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/unexpected")
    def unexpected() -> None:
        raise RuntimeError("database password should not leak")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/unexpected", headers={"X-Request-ID": "req-500"})
    data = response.json()

    assert response.status_code == 500
    assert data["ok"] is False
    assert data["error"]["code"] == "SYS_INT_001"
    assert data["error"]["details"]["exception_type"] == "RuntimeError"
    assert data["error"]["details"]["request_id"] == "req-500"
    assert "exception_message" not in data["error"]["details"]


def test_server_create_app_registers_finer_error_handler() -> None:
    from finer.api.server import create_app

    app = create_app()
    assert FinerError in app.exception_handlers
