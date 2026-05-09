"""Finer exception hierarchy backed by canonical error codes."""

from __future__ import annotations

from typing import Any

from finer.errors.codes import ErrorCode, coerce_error_code, get_error_info


class FinerError(Exception):
    """Base exception for all expected Finer failures."""

    def __init__(
        self,
        code: ErrorCode | str,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
        cause: BaseException | None = None,
        **context: Any,
    ) -> None:
        self.code = coerce_error_code(code)
        self.info = get_error_info(self.code)
        self.message = message or self.info.title
        self.status_code = status_code or self.info.status_code
        self.cause = cause
        self.details: dict[str, Any] = dict(details or {})
        self.details.update({key: value for key, value in context.items() if value is not None})
        super().__init__(self.message)

    @property
    def error_code_str(self) -> str:
        """Return the string value used in API responses and logs."""

        return self.code.value

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the canonical API error payload."""

        return {
            "ok": False,
            "error": {
                "code": self.error_code_str,
                "message": self.message,
                "details": dict(self.details),
            },
        }

    def __str__(self) -> str:
        return f"[{self.error_code_str}] {self.message}"


class FinerValidationError(FinerError):
    """Caller input failed validation."""


class FinerAuthenticationError(FinerError):
    """Authentication failed."""


class FinerAuthorizationError(FinerError):
    """Authenticated caller is not allowed to perform the operation."""


class FinerNotFoundError(FinerError):
    """Requested resource was not found."""


class FinerConflictError(FinerError):
    """Requested operation conflicts with current state."""


class FinerConfigurationError(FinerError):
    """Runtime configuration is invalid or missing."""


class FinerStateError(FinerError):
    """Pipeline or resource state is invalid for the requested operation."""


class FinerSchemaError(FinerError):
    """Canonical schema validation failed."""


class FinerExternalServiceError(FinerError):
    """External service or upstream dependency failed."""


class FinerTimeoutError(FinerError):
    """Operation exceeded its timeout."""


class FinerInternalError(FinerError):
    """Unexpected internal failure that should be narrowed later."""


__all__ = [
    "FinerAuthenticationError",
    "FinerAuthorizationError",
    "FinerConfigurationError",
    "FinerConflictError",
    "FinerError",
    "FinerExternalServiceError",
    "FinerInternalError",
    "FinerNotFoundError",
    "FinerSchemaError",
    "FinerStateError",
    "FinerTimeoutError",
    "FinerValidationError",
]
