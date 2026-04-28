"""
Event Schemas — L5 extraction output models.

This module defines lightweight event models for extraction layer.
TradingAction provides compatibility with ActionStep from trade_action.py
through bidirectional conversion methods.

ActionStep (from trade_action.py) is the authoritative definition for L7+ layers.
TradingAction exists for L5 extraction and backward compatibility.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal, Any
from datetime import datetime


# =============================================================================
# Action Type Literal (for L5 extraction, compatible with ActionType enum)
# =============================================================================

ACTION_TYPE_LITERAL = Literal[
    "long", "short", "close_long", "close_short",
    "buy_call", "sell_call", "buy_put", "sell_put",
    "hold", "watch", "buy_and_hold"
]

INSTRUMENT_TYPE_LITERAL = Literal[
    "stock", "option", "etf", "index_future", "crypto", "unspecified"
]


class TradingAction(BaseModel):
    """
    Lightweight trading action for L5 extraction layer.

    This model is designed for extraction and provides seamless conversion
    to/from ActionStep (the authoritative model in trade_action.py).

    Key differences from ActionStep:
    - Uses Literal types instead of Enums (easier for LLM extraction)
    - Has `confidence` field (per-action confidence score)
    - Has `instrument_type` field (convenience field)
    - Uses `sequence_order` instead of `sequence` (historical naming)

    For L7+ layers, convert to ActionStep using `to_action_step()`.
    """
    model_config = ConfigDict(strict=True)

    action_type: ACTION_TYPE_LITERAL = Field(
        ..., description="The type of trading operation"
    )

    instrument_type: INSTRUMENT_TYPE_LITERAL = Field(
        "unspecified", description="The asset class involved"
    )

    trigger_condition: Optional[str] = Field(
        None, description="Natural language or numeric condition (e.g., 'price < 480', 'breakout')"
    )

    target_price_low: Optional[float] = Field(
        None, ge=0, description="Lower bound of targeted price range"
    )

    target_price_high: Optional[float] = Field(
        None, ge=0, description="Upper bound of targeted price range"
    )

    sequence_order: int = Field(
        1, ge=1, description="Order in a multi-step execution chain (1 = first step)"
    )

    confidence: float = Field(
        1.0, ge=0.0, le=1.0, description="Model's confidence in this specific action extraction"
    )

    def to_action_step(self) -> "ActionStep":
        """
        Convert to ActionStep (authoritative model for L7+ layers).

        Returns:
            ActionStep instance with mapped fields.
        """
        from finer.schemas.trade_action import ActionStep, ActionType

        # Map action_type string to ActionType enum
        action_type_map = {
            "long": ActionType.LONG,
            "short": ActionType.SHORT,
            "close_long": ActionType.CLOSE_LONG,
            "close_short": ActionType.CLOSE_SHORT,
            "buy_call": ActionType.BUY_CALL,
            "sell_call": ActionType.SELL_CALL,
            "buy_put": ActionType.BUY_PUT,
            "sell_put": ActionType.SELL_PUT,
            "hold": ActionType.HOLD,
            "watch": ActionType.WATCH,
            "buy_and_hold": ActionType.BUY_AND_HOLD,
        }

        return ActionStep(
            sequence=self.sequence_order,
            action_type=action_type_map[self.action_type],
            trigger_condition=self.trigger_condition,
            target_price_low=self.target_price_low,
            target_price_high=self.target_price_high,
        )

    @classmethod
    def from_action_step(
        cls,
        step: "ActionStep",
        confidence: float = 1.0,
        instrument_type: INSTRUMENT_TYPE_LITERAL = "unspecified"
    ) -> "TradingAction":
        """
        Create TradingAction from ActionStep.

        Args:
            step: ActionStep instance to convert.
            confidence: Confidence score for this action.
            instrument_type: Asset class.

        Returns:
            TradingAction instance.
        """
        return cls(
            action_type=step.action_type.value,  # Convert enum to string
            instrument_type=instrument_type,
            trigger_condition=step.trigger_condition,
            target_price_low=step.target_price_low,
            target_price_high=step.target_price_high,
            sequence_order=step.sequence,
            confidence=confidence,
        )

class EventWithActions(BaseModel):
    """
    A unified investment event containing the analyzed view and predicted actions.
    """
    model_config = ConfigDict(strict=True)

    event_id: Optional[str] = Field(None, description="Unique identifier for the high-level event")
    content_id: Optional[str] = Field(None, description="Reference to the source material")
    
    ticker: str = Field(..., description="Ticker symbol or canonical name of the asset")
    direction: Literal["bullish", "bearish", "neutral", "watchlist", "risk_warning"] = Field(
        ..., description="Overall sentiment/direction of the view"
    )
    
    evidence_text: str = Field(..., description="The raw segment text acting as evidence")
    rationale: Optional[str] = Field(None, description="Brief explanation of the logic behind this view")
    
    action_chain: List[TradingAction] = Field(
        default_factory=list, description="Ordered chain of trading intents (e.g., watch then long)"
    )
    
    time_horizon: Optional[str] = Field(None, description="Expected time range (e.g., '1 week', 'long term')")
    
    metadata: dict = Field(default_factory=dict, description="Additional extraction metadata")

class ExtractionResult(BaseModel):
    """
    Container for multiple events extracted from a single processing run.
    """
    events: List[EventWithActions]
