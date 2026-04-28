"""Audience Target Analyzer — Dimension 10: 受众定位 (MEDIUM priority).

Measures:
- Expertise level (expert/general/novice)
- Assumed knowledge
- Explanation depth
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from finer.schemas.text_analysis import AudienceTargetResult


class AudienceTargetAnalyzer:
    """Analyze audience targeting - Reader expertise."""

    # Expert markers
    EXPERT_MARKERS = [
        "alpha", "beta", "夏普比率", "最大回撤", "波动率",
        "市盈率", "市净率", "ROE", "ROA", "EBITDA",
        "技术分析", "基本面", "量化", "对冲", "套利",
    ]

    # Novice markers
    NOVICE_MARKERS = [
        "简单来说", "通俗地说", "换句话说", "打个比方",
        "什么是", "怎么理解", "什么意思",
    ]

    # Explanation depth markers
    DETAILED_EXPLANATION = [
        "具体来说", "详细", "深入", "全面", "系统",
    ]
    MINIMAL_EXPLANATION = [
        "不言而喻", "显而易见", "众所周知", "众所周知",
    ]

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> AudienceTargetResult:
        """Analyze audience targeting."""
        if not text.strip():
            return AudienceTargetResult(
                expertise_level="general",
                explanation_depth="moderate",
            )

        # Expertise level
        expertise = self._detect_expertise_level(text)

        # Assumed knowledge
        assumed = self._detect_assumed_knowledge(text)

        # Explanation depth
        depth = self._detect_explanation_depth(text)

        return AudienceTargetResult(
            expertise_level=expertise,
            assumed_knowledge=assumed,
            explanation_depth=depth,
        )

    def _detect_expertise_level(self, text: str) -> str:
        """Detect target expertise level."""
        expert_count = sum(text.count(m) for m in self.EXPERT_MARKERS)
        novice_count = sum(text.count(m) for m in self.NOVICE_MARKERS)

        if expert_count > novice_count * 2:
            return "expert"
        elif novice_count > expert_count * 2:
            return "novice"
        return "general"

    def _detect_assumed_knowledge(self, text: str) -> List[str]:
        """Detect assumed knowledge concepts."""
        # Find concepts mentioned without explanation
        concepts = []

        # Technical terms without explanation
        for marker in self.EXPERT_MARKERS:
            if marker in text:
                # Check if followed by explanation
                idx = text.find(marker)
                following = text[idx:idx+50]
                if not any(m in following for m in self.NOVICE_MARKERS):
                    concepts.append(marker)

        return concepts[:5]

    def _detect_explanation_depth(self, text: str) -> str:
        """Detect explanation depth."""
        detailed = sum(text.count(m) for m in self.DETAILED_EXPLANATION)
        minimal = sum(text.count(m) for m in self.MINIMAL_EXPLANATION)

        if detailed > minimal:
            return "detailed"
        elif minimal > detailed:
            return "minimal"
        return "moderate"