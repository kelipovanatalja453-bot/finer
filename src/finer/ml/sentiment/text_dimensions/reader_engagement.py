"""Reader Engagement Analyzer — Dimension 12: 读者互动 (MEDIUM priority).

Measures:
- Direct address frequency
- Question frequency
- Interaction style
- Resonance triggers
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from finer.schemas.text_analysis import ReaderEngagementResult


class ReaderEngagementAnalyzer:
    """Analyze reader engagement - Audience interaction."""

    # Direct address markers
    DIRECT_ADDRESS_MARKERS = [
        "你", "您", "你们", "大家", "各位",
        "朋友们", "读者", "听众", "观众",
    ]

    # Question patterns
    QUESTION_PATTERNS = [
        r"[^？?]*[吗呢吧啊呀][？?]",
        r"为什么.{2,20}[？?]",
        r"怎么.{2,20}[？?]",
        r"如何.{2,20}[？?]",
    ]

    # Interaction style markers
    CONVERSATIONAL_MARKERS = ["吧", "呢", "啊", "呀", "哦"]
    GUIDING_MARKERS = ["首先", "其次", "然后", "最后", "注意"]
    CHALLENGING_MARKERS = ["试想", "想象一下", "如果", "假如"]

    # Resonance triggers
    RESONANCE_TRIGGERS = [
        "担心", "焦虑", "恐惧", "贪婪", "希望",
        "梦想", "未来", "成功", "失败", "风险",
    ]

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> ReaderEngagementResult:
        """Analyze reader engagement."""
        if not text.strip():
            return ReaderEngagementResult(interaction_style="neutral")

        # Direct address
        direct_count = sum(text.count(m) for m in self.DIRECT_ADDRESS_MARKERS)

        # Questions
        question_count = self._count_questions(text)
        question_frequency = question_count / (len(text) / 100) if text else 0

        # Interaction style
        style = self._detect_interaction_style(text)

        # Resonance triggers
        triggers = self._detect_resonance_triggers(text)

        return ReaderEngagementResult(
            direct_address_count=direct_count,
            question_count=question_count,
            question_frequency=min(1.0, question_frequency),
            interaction_style=style,
            resonance_triggers=triggers,
        )

    def _count_questions(self, text: str) -> int:
        count = text.count("？") + text.count("?")
        for pattern in self.QUESTION_PATTERNS:
            count += len(re.findall(pattern, text))
        return count

    def _detect_interaction_style(self, text: str) -> str:
        conversational = sum(text.count(m) for m in self.CONVERSATIONAL_MARKERS)
        guiding = sum(text.count(m) for m in self.GUIDING_MARKERS)
        challenging = sum(text.count(m) for m in self.CHALLENGING_MARKERS)

        if conversational > guiding and conversational > challenging:
            return "conversational"
        elif guiding > conversational and guiding > challenging:
            return "guiding"
        elif challenging > conversational and challenging > guiding:
            return "challenging"
        return "neutral"

    def _detect_resonance_triggers(self, text: str) -> List[str]:
        triggers = []
        for trigger in self.RESONANCE_TRIGGERS:
            if trigger in text:
                triggers.append(trigger)
        return triggers[:5]