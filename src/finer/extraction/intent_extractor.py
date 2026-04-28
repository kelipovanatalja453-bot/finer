"""Intent Extraction Result Schema — Minimal V1 for architecture validation.

This module defines the result container for intent extraction, holding
extracted intents along with evidence spans.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from finer.schemas.content_envelope import ContentEnvelope, ContentBlock
from finer.schemas.investment_intent import NormalizedInvestmentIntent
from finer.schemas.evidence import EvidenceSpan


class IntentExtractionResult(BaseModel):
    """Result container for intent extraction from a ContentEnvelope.

    Holds extracted intents with their evidence spans and extraction metadata.

    Attributes:
        envelope_id: ID of the source ContentEnvelope.
        intents: List of extracted NormalizedInvestmentIntent.
        evidence_spans: List of EvidenceSpan providing traceability.
        extraction_timestamp: When extraction was performed.
        extractor_version: Version identifier for this extractor.
        processing_notes: Any notes or warnings from extraction.
        metadata: Additional extensible metadata.
    """
    model_config = ConfigDict(strict=True)

    envelope_id: str = Field(
        ...,
        description="ID of the source ContentEnvelope"
    )

    intents: List[NormalizedInvestmentIntent] = Field(
        default_factory=list,
        description="List of extracted intents"
    )

    evidence_spans: List[EvidenceSpan] = Field(
        default_factory=list,
        description="Evidence spans for traceability"
    )

    extraction_timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When extraction was performed"
    )

    extractor_version: str = Field(
        "minimal_v1",
        description="Version identifier for this extractor"
    )

    processing_notes: List[str] = Field(
        default_factory=list,
        description="Notes or warnings from extraction process"
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional extensible metadata"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntentExtractionResult:
        """Create from dictionary."""
        if isinstance(data.get("extraction_timestamp"), str):
            data["extraction_timestamp"] = datetime.fromisoformat(
                data["extraction_timestamp"].replace("Z", "+00:00")
            )
        return cls.model_validate(data)


# =============================================================================
# Minimal V1 Rule-Based Intent Extractor
# =============================================================================

# Keyword patterns for direction detection
BULLISH_KEYWORDS = [
    "看好", "受益", "机会", "加仓", "抄底", "持有", "买入",
    "增持", "推荐", "优质", "低估",
]

BEARISH_KEYWORDS = [
    "看空", "减仓", "退出", "不及预期", "风险", "回避",
    "卖出", "清仓", "减持", "高估", "谨慎",
]

# Keyword patterns for actionability detection
EXPLICIT_ACTION_KEYWORDS = [
    "加仓", "抄底", "买入", "卖出", "减仓", "清仓", "退出",
    "增持", "减持", "建仓",
]

HOLD_ACTION_KEYWORDS = [
    "持有", "继续拿", "拿着", "不动", "继续持有",
]

OPINION_WATCH_KEYWORDS = [
    "看好", "关注", "观察", "留意", "值得",
]


def _find_keyword_spans(
    text: str,
    keywords: List[str],
    block_id: str,
) -> List[Tuple[str, int, int]]:
    """Find all keyword occurrences in text with their positions.

    Args:
        text: Text to search in.
        keywords: List of keywords to find.
        block_id: Block ID for evidence spans.

    Returns:
        List of (keyword, start, end) tuples.
    """
    spans = []
    for keyword in keywords:
        start = 0
        while True:
            pos = text.find(keyword, start)
            if pos == -1:
                break
            spans.append((keyword, pos, pos + len(keyword)))
            start = pos + 1
    return spans


def _create_evidence_span(
    block_id: str,
    text: str,
    start: int,
    end: int,
    span_type: str,
) -> EvidenceSpan:
    """Create an EvidenceSpan from text position.

    Args:
        block_id: Block ID.
        text: Full block text.
        start: Start position.
        end: End position.
        span_type: Type of evidence.

    Returns:
        EvidenceSpan instance.
    """
    return EvidenceSpan(
        block_id=block_id,
        char_start=start,
        char_end=end,
        text=text[start:end],
        confidence=0.8,  # Rule-based confidence
        span_type=span_type,
    )


def _detect_direction(text: str) -> Optional[str]:
    """Detect sentiment direction from text.

    Args:
        text: Text to analyze.

    Returns:
        'bullish', 'bearish', or None.
    """
    bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
    bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text)

    if bullish_count > bearish_count:
        return "bullish"
    elif bearish_count > bullish_count:
        return "bearish"
    elif bullish_count > 0 and bullish_count == bearish_count:
        return "mixed"
    return None


def _detect_actionability(text: str) -> Tuple[str, str]:
    """Detect actionability and position delta hint from text.

    Args:
        text: Text to analyze.

    Returns:
        Tuple of (actionability, position_delta_hint).
    """
    # Check for explicit actions first
    for kw in EXPLICIT_ACTION_KEYWORDS:
        if kw in text:
            # Determine position delta from keyword
            if kw in ["加仓", "抄底", "买入", "增持", "建仓"]:
                return "explicit_action", "add"
            elif kw in ["卖出", "减仓", "清仓", "退出", "减持"]:
                return "explicit_action", "reduce"

    # Check for hold actions
    for kw in HOLD_ACTION_KEYWORDS:
        if kw in text:
            return "explicit_action", "hold"

    # Check for opinion/watch
    for kw in OPINION_WATCH_KEYWORDS:
        if kw in text:
            if kw == "看好":
                return "opinion", "none"
            else:
                return "watch", "none"

    return "opinion", "none"


def _extract_target_entity(
    text: str,
    entity_anchors: List[Any],
) -> Tuple[str, Optional[str], str]:
    """Extract target entity from text or entity anchors.

    Args:
        text: Text to analyze.
        entity_anchors: Entity anchors from ContentEnvelope.

    Returns:
        Tuple of (target_name, target_symbol, target_type).
    """
    # Try to get from entity_anchors first
    if entity_anchors:
        anchor = entity_anchors[0]
        target_name = anchor.raw_text or anchor.resolved_name or "unknown"
        target_symbol = anchor.resolved_symbol
        target_type = anchor.entity_type if hasattr(anchor, 'entity_type') else "stock"
        return target_name, target_symbol, target_type

    # Fallback: try to find stock name patterns (minimal implementation)
    # Look for common patterns like "XX板块" or company names
    patterns = [
        r"([一-龥]{2,6})(板块|行业)",  # 行业板块
        r"([一-龥]{2,8})(股份|集团)",  # 公司名称
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0), None, "sector" if "板块" in match.group(0) else "stock"

    return "unknown", None, "unknown"


def extract_intents_from_envelope(
    envelope: ContentEnvelope,
) -> IntentExtractionResult:
    """Extract investment intents from a ContentEnvelope.

    This is a minimal V1 rule-based implementation for architecture validation.
    It uses simple keyword matching to detect:
    - Direction (bullish/bearish)
    - Actionability (opinion/watch/explicit_action)
    - Position delta hint

    Args:
        envelope: ContentEnvelope to extract intents from.

    Returns:
        IntentExtractionResult with extracted intents and evidence.

    Rules:
        - "看好/受益/机会/加仓/抄底/持有" -> bullish candidate
        - "看空/减仓/退出/不及预期/风险/回避" -> bearish or risk candidate
        - "加仓/抄底/买入" -> explicit_action, add/open
        - "持有/继续拿" -> explicit_action, hold
        - "看好/关注" -> opinion/watch, none
        - No clear entity -> target_name="unknown" with ambiguity flag

    Constraints:
        - Each intent must have at least one evidence span
        - sentiment_score is auxiliary, cannot override explicit action
        - Does not generate position ratio
        - Does not write TradeAction
    """
    intents: List[NormalizedInvestmentIntent] = []
    all_evidence_spans: List[EvidenceSpan] = []
    processing_notes: List[str] = []

    # Process each block
    for block in envelope.blocks:
        text = block.text
        if not text or len(text.strip()) == 0:
            continue

        # Detect direction
        direction = _detect_direction(text)
        if not direction:
            continue  # No investment intent found in this block

        # Detect actionability and position hint
        actionability, position_hint = _detect_actionability(text)

        # Extract target entity
        target_name, target_symbol, target_type = _extract_target_entity(
            text, envelope.entity_anchors
        )

        # Build evidence spans for this block
        block_evidence: List[EvidenceSpan] = []

        # Find keyword evidence
        all_keywords = BULLISH_KEYWORDS + BEARISH_KEYWORDS
        keyword_spans = _find_keyword_spans(text, all_keywords, block.block_id)

        for kw, start, end in keyword_spans:
            span = _create_evidence_span(
                block.block_id, text, start, end, "intent_keyword"
            )
            block_evidence.append(span)

        # Must have at least one evidence span
        if not block_evidence:
            processing_notes.append(
                f"Block {block.block_id}: direction detected but no keyword evidence found"
            )
            continue

        # Build ambiguity flags
        ambiguity_flags: List[str] = []
        if target_name == "unknown":
            ambiguity_flags.append("unknown_target")

        # Determine conviction and confidence
        conviction = 0.6  # Rule-based: moderate conviction
        confidence = 0.7  # Rule-based: moderate confidence

        # Adjust confidence based on entity resolution
        if target_name == "unknown":
            confidence = 0.4
        elif target_symbol:
            confidence = 0.8

        # Create intent
        intent = NormalizedInvestmentIntent(
            envelope_id=envelope.envelope_id,
            block_ids=[block.block_id],
            creator_id=envelope.creator_id,
            target_type=target_type,
            target_name=target_name,
            target_symbol=target_symbol,
            market=envelope.metadata.get("market"),
            direction=direction,
            actionability=actionability,
            position_delta_hint=position_hint,
            conviction=conviction,
            confidence=confidence,
            evidence_span_ids=[span.evidence_span_id for span in block_evidence],
            ambiguity_flags=ambiguity_flags,
        )

        intents.append(intent)
        all_evidence_spans.extend(block_evidence)

    # Build result
    result = IntentExtractionResult(
        envelope_id=envelope.envelope_id,
        intents=intents,
        evidence_spans=all_evidence_spans,
        processing_notes=processing_notes,
    )

    return result
