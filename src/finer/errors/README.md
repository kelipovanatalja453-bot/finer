# Finer Error Codes

F-stage: cross-stage infrastructure.

This package is the canonical error system for Finer API and pipeline code. It
does not own business logic for any single F-stage; it provides stable error
identity, root-cause lookup, and unified API serialization for all stages.

## Structure

```text
src/finer/errors/
├── __init__.py      # public imports
├── codes.py         # ErrorCode catalog and lookup metadata
├── exceptions.py    # FinerError hierarchy
├── handler.py       # FastAPI exception handlers
└── README.md        # package rules and usage
```

## Code Format

```text
{DOMAIN}_{CATEGORY}_{SEQUENCE}
```

Examples:

- `SYS_IN_001`: invalid request payload
- `WX_EXT_001`: WeChat exporter unavailable
- `LLM_EXT_002`: LLM provider rate limited or overloaded
- `BILI_NTF_001`: Bilibili resource not found

`F15` is the error-code domain for the canonical F1.5 Topic Assembly stage.

## Usage

```python
from finer.errors import FinerError, FinerExternalServiceError
from finer.errors.codes import ErrorCode

raise FinerError(ErrorCode.SYS_IN_001, "Missing content_id")

raise FinerExternalServiceError(
    ErrorCode.LLM_EXT_002,
    "Rate limited",
    service="mimo-api",
    details={"retry_after": 60},
)
```

API responses are serialized as:

```json
{
  "ok": false,
  "error": {
    "code": "WX_EXT_001",
    "message": "Exporter not responding",
    "details": {
      "service": "wechat-exporter",
      "request_id": "..."
    }
  }
}
```

## Rules

- Add a new `ErrorCode` member before using a new code in business code.
- Every code must have catalog metadata: title, root cause, and fix hint.
- Prefer the most specific F-stage or integration domain.
- Do not introduce legacy `L0-L8` or `V0-V6` naming in error codes.
- Sensitive values must not be placed in `details`.
