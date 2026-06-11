"""Shared validation helpers for annotation workbench extraction JSON."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from finer.schemas.trade_action import ActionType, TradeDirection

VALID_DIRECTIONS = {d.value for d in TradeDirection}
VALID_ACTION_TYPES = {a.value for a in ActionType}


def parse_extraction_json(raw: str) -> Dict[str, Any]:
    """Parse a model extraction JSON string into an object."""
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"不是合法 JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("必须是 JSON 对象")
    return obj


def validate_extraction_object(obj: Optional[Dict[str, Any]]) -> List[str]:
    """Return validation errors for the lightweight ExtractionOutput contract."""
    errors: List[str] = []
    if obj is None:
        return ["抽取结果为空"]

    ticker = obj.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        errors.append("ticker 缺失或非空字符串")

    direction = obj.get("direction")
    if direction not in VALID_DIRECTIONS:
        errors.append(f"direction 非法: {direction!r}")

    chain = obj.get("action_chain", [])
    if chain is None:
        chain = []
    if not isinstance(chain, list):
        errors.append("action_chain 必须是数组")
        return errors

    for i, step in enumerate(chain):
        if not isinstance(step, dict):
            errors.append(f"action_chain[{i}] 非对象")
            continue
        action_type = step.get("action_type")
        if action_type not in VALID_ACTION_TYPES:
            errors.append(f"action_chain[{i}].action_type 非法: {action_type!r}")
        lo = step.get("target_price_low")
        hi = step.get("target_price_high")
        for name, value in (("target_price_low", lo), ("target_price_high", hi)):
            if value is not None and (not isinstance(value, (int, float)) or value < 0):
                errors.append(f"action_chain[{i}].{name} 非法: {value!r}")
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi:
            errors.append(f"action_chain[{i}] 价格区间倒挂: {lo} > {hi}")
    return errors


def validate_extraction_json(raw: str) -> List[str]:
    """Validate a JSON string against the lightweight ExtractionOutput contract."""
    try:
        obj = parse_extraction_json(raw)
    except ValueError as exc:
        return [str(exc)]
    return validate_extraction_object(obj)
