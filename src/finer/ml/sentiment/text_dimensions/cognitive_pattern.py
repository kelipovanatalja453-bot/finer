"""Cognitive Pattern Analyzer — Dimension 5: 认知模式 (MEDIUM priority).

Measures:
- Thinking mode (inductive/deductive/analogy)
- Abstraction level
- Conceptual metaphors
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from finer.schemas.text_analysis import CognitivePatternResult


class CognitivePatternAnalyzer:
    """Analyze cognitive patterns - Thinking mode detection."""

    # Thinking mode markers
    INDUCTIVE_MARKERS = [
        "从数据来看", "观察发现", "案例说明", "经验表明",
        "实践证明", "统计显示", "调查发现",
    ]
    DEDUCTIVE_MARKERS = [
        "因此", "所以", "必然", "一定", "显然",
        "由此可见", "毫无疑问",
    ]
    ANALOGICAL_MARKERS = [
        "类似", "相似", "好比", "就像", "如同",
        "相当于", "可以理解为",
    ]

    # Abstraction markers
    ABSTRACT_MARKERS = [
        "本质", "根本", "核心", "关键", "原理",
        "规律", "机制", "逻辑", "理论",
    ]
    CONCRETE_MARKERS = [
        "例如", "比如", "具体", "实际上", "事实上",
        "案例", "实例", "例子",
    ]

    # Conceptual metaphors
    METAPHOR_DOMAINS = {
        "market_as_war": ["战场", "进攻", "防守", "策略", "胜败", "敌人"],
        "market_as_game": ["博弈", "游戏", "规则", "玩家", "赢", "输"],
        "market_as_weather": ["风暴", "晴朗", "阴云", "波动", "周期"],
        "market_as_organism": ["生长", "衰退", "复苏", "周期", "生命力"],
    }

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> CognitivePatternResult:
        """Analyze cognitive patterns."""
        if not text.strip():
            return CognitivePatternResult(
                primary_thinking_mode="mixed",
                abstraction_level="mixed",
            )

        # Thinking mode
        primary_mode = self._detect_thinking_mode(text)
        distribution = self._calc_mode_distribution(text)

        # Abstraction level
        abstraction_level = self._detect_abstraction_level(text)
        shift_count = self._count_abstraction_shifts(text)

        # Conceptual metaphors
        metaphors = self._detect_metaphors(text)
        consistency = self._calc_metaphor_consistency(metaphors)

        return CognitivePatternResult(
            primary_thinking_mode=primary_mode,
            thinking_mode_distribution=distribution,
            abstraction_level=abstraction_level,
            abstraction_shift_count=shift_count,
            conceptual_metaphors=metaphors,
            metaphor_consistency=consistency,
        )

    def _detect_thinking_mode(self, text: str) -> str:
        """Detect primary thinking mode."""
        inductive = sum(text.count(m) for m in self.INDUCTIVE_MARKERS)
        deductive = sum(text.count(m) for m in self.DEDUCTIVE_MARKERS)
        analogical = sum(text.count(m) for m in self.ANALOGICAL_MARKERS)

        total = inductive + deductive + analogical
        if total == 0:
            return "mixed"

        if inductive > deductive and inductive > analogical:
            return "inductive"
        elif deductive > inductive and deductive > analogical:
            return "deductive"
        elif analogical > inductive and analogical > deductive:
            return "analogical"
        return "mixed"

    def _calc_mode_distribution(self, text: str) -> Dict[str, float]:
        """Calculate thinking mode distribution."""
        inductive = sum(text.count(m) for m in self.INDUCTIVE_MARKERS)
        deductive = sum(text.count(m) for m in self.DEDUCTIVE_MARKERS)
        analogical = sum(text.count(m) for m in self.ANALOGICAL_MARKERS)

        total = inductive + deductive + analogical
        if total == 0:
            return {"inductive": 0.33, "deductive": 0.33, "analogical": 0.34}

        return {
            "inductive": inductive / total,
            "deductive": deductive / total,
            "analogical": analogical / total,
        }

    def _detect_abstraction_level(self, text: str) -> str:
        """Detect abstraction level."""
        abstract = sum(text.count(m) for m in self.ABSTRACT_MARKERS)
        concrete = sum(text.count(m) for m in self.CONCRETE_MARKERS)

        if abstract > concrete * 1.5:
            return "abstract"
        elif concrete > abstract * 1.5:
            return "concrete"
        return "mixed"

    def _count_abstraction_shifts(self, text: str) -> int:
        """Count shifts between abstraction levels."""
        # Simplified: count transitions between abstract and concrete markers
        return 0

    def _detect_metaphors(self, text: str) -> List[str]:
        """Detect conceptual metaphors."""
        metaphors = []
        for domain, markers in self.METAPHOR_DOMAINS.items():
            if any(m in text for m in markers):
                metaphors.append(domain)
        return metaphors

    def _calc_metaphor_consistency(self, metaphors: List[str]) -> float:
        """Calculate metaphor consistency."""
        if len(metaphors) <= 1:
            return 1.0
        # More diverse metaphors = less consistency
        return 1.0 / len(metaphors)