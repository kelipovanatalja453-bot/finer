"""ExecutionTiming builder — extracted from canonical_runner.

Deterministic timing computation for F5 TradeActions.
Delegates to MarketCalendarTimingPolicy for market-calendar-based logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from finer.schemas.content_envelope import ContentEnvelope
from finer.schemas.trade_action import ExecutionTiming, MarketSession


def build_execution_timing(
    envelope: ContentEnvelope,
    temporal_anchors: Optional[List[Any]] = None,
    market: str = "CN",
    intent_id: Optional[str] = None,
) -> ExecutionTiming:
    """Build ExecutionTiming using MarketCalendarTimingPolicy.

    Uses the deterministic market calendar timing policy to compute
    action_executable_at, instead of ad-hoc datetime arithmetic.

    Args:
        envelope: Content envelope with published_at.
        temporal_anchors: Temporal anchors from F2 (effective_trade_at / mentioned_at).
        market: Market code — CN, HK, or US.
        intent_id: Associated intent ID (for logging; unused in timing logic).

    Returns:
        ExecutionTiming with all fields populated.
    """
    from finer.execution.timing_policy import MarketCalendarTimingPolicy

    published_at = envelope.published_at or datetime.now()

    # Determine intent_effective_at from temporal anchors
    intent_effective_at = _resolve_intent_effective_at(temporal_anchors)

    # Determine timezone from market
    timezone_map = {
        "CN": "Asia/Shanghai",
        "HK": "Asia/Hong_Kong",
        "US": "America/New_York",
    }
    tz = timezone_map.get(market, "Asia/Shanghai")

    # Use MarketCalendarTimingPolicy for deterministic timing
    policy = MarketCalendarTimingPolicy()
    result = policy.compute_timing(
        published_at=published_at,
        market=market,
        timezone=tz,
        intent_effective_at=intent_effective_at,
    )

    return ExecutionTiming(
        intent_published_at=result.intent_published_at,
        intent_effective_at=intent_effective_at,
        action_decision_at=datetime.now(),
        action_executable_at=result.action_executable_at,
        market=result.market,
        timezone=result.timezone,
        market_session_at_publish=MarketSession(result.market_session_at_publish),
        timing_policy_id=result.timing_policy_id,
    )


def _resolve_intent_effective_at(
    temporal_anchors: Optional[List[Any]],
) -> Optional[datetime]:
    """Extract intent_effective_at from temporal anchors.

    Prefers 'effective_trade_at', falls back to 'mentioned_at'.
    """
    if not temporal_anchors:
        return None

    for anchor in temporal_anchors:
        if getattr(anchor, "anchor_type", None) == "effective_trade_at":
            resolved = getattr(anchor, "resolved_time", None)
            if resolved:
                return resolved

    for anchor in temporal_anchors:
        if getattr(anchor, "anchor_type", None) == "mentioned_at":
            resolved = getattr(anchor, "resolved_time", None)
            if resolved:
                return resolved

    return None
