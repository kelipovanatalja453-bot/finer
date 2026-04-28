"""Argumentation Analyzer — Dimension 8: 论证策略 (HIGH priority).

Measures:
- Argument type (deductive/inductive/abductive)
- Logical validity and premise clarity
- Fallacy detection
- Persuasion techniques
- Counter-argument handling

For KOL analysis, this provides reasoning quality metrics.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from finer.schemas.text_analysis import ArgumentationResult


class ArgumentationAnalyzer:
    """Analyze argumentation strategy - Reasoning quality.

    Usage:
        analyzer = ArgumentationAnalyzer()
        result = analyzer.analyze("这是一段文本...")
        print(result.primary_argument_type, result.detected_fallacies)
    """

    # Argument type indicators
    DEDUCTIVE_MARKERS = [
        "因此", "所以", "故", "由此可见", "必然",
        "一定", "必定", "毫无疑问", "显然",
    ]

    INDUCTIVE_MARKERS = [
        "从数据来看", "统计显示", "调查显示", "研究表明",
        "观察发现", "经验表明", "实践证明", "案例说明",
    ]

    ABDUCTIVE_MARKERS = [
        "可能", "或许", "也许", "推测", "估计",
        "猜测", "推断", "假设", "如果", "假如",
    ]

    # Common fallacies
    FALLACY_PATTERNS = {
        "hasty_generalization": [
            r"所有.{2,10}都",
            r"凡是.{2,10}一定",
            r"没有.{2,10}不",
        ],
        "appeal_to_authority": [
            r"专家说",
            r"权威.{2,10}认为",
            r"官方.{2,10}表示",
        ],
        "appeal_to_emotion": [
            r"太可怕了",
            r"太震惊了",
            r"令人.{2,10}的是",
            r"不敢相信",
        ],
        "straw_man": [
            r"有人说.{2,30}其实",
            r"所谓的.{2,10}只是",
        ],
        "false_dichotomy": [
            r"要么.{2,10}要么",
            r"只有.{2,10}两种",
            r"非.{2,10}即",
        ],
        "slippery_slope": [
            r"如果.{2,10}就会.{2,10}最终",
            r"一旦.{2,10}必然导致",
        ],
    }

    # Persuasion techniques
    PERSUASION_TECHNIQUES = {
        "rhetorical_question": r"[？?]",  # High question density
        "repetition": r"(.{4,10}).{0,20}\1",  # Repeated phrases
        "social_proof": r"大家.{2,10}都|多数.{2,10}认为|普遍.{2,10}",
        "scarcity": r"仅剩|最后|有限|难得|错过",
        "authority": r"专家|权威|官方|官方认证",
    }

    # Counter-argument markers
    COUNTER_ARGUMENT_MARKERS = [
        "有人认为", "有人说", "反对者", "质疑",
        "但是", "然而", "不过", "有人反驳",
        "另一方面", "相反的观点", "不同看法",
    ]

    def __init__(self):
        pass

    def analyze(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ArgumentationResult:
        """Analyze argumentation strategy.

        Args:
            text: Text to analyze
            context: Optional context

        Returns:
            ArgumentationResult with reasoning quality
        """
        if not text.strip():
            return self._empty_result()

        # Argument type
        primary_argument_type = self._detect_argument_type(text)
        argument_strength = self._calc_argument_strength(text)

        # Reasoning quality
        logical_validity = self._calc_logical_validity(text)
        premise_clarity = self._calc_premise_clarity(text)
        conclusion_support = self._calc_conclusion_support(text)

        # Fallacy detection
        detected_fallacies = self._detect_fallacies(text)
        fallacy_risk_score = len(detected_fallacies) / 6  # Normalize

        # Persuasion techniques
        persuasion_techniques = self._detect_persuasion_techniques(text)
        emotional_appeal_ratio = self._calc_emotional_appeal(text)
        logical_appeal_ratio = 1 - emotional_appeal_ratio

        # Counter-argument handling
        addresses_counterarguments = self._check_counter_arguments(text)
        counterargument_quality = self._calc_counterargument_quality(text)

        return ArgumentationResult(
            primary_argument_type=primary_argument_type,
            argument_strength=argument_strength,
            logical_validity=logical_validity,
            premise_clarity=premise_clarity,
            conclusion_support=conclusion_support,
            detected_fallacies=detected_fallacies,
            fallacy_risk_score=fallacy_risk_score,
            persuasion_techniques=persuasion_techniques,
            emotional_appeal_ratio=emotional_appeal_ratio,
            logical_appeal_ratio=logical_appeal_ratio,
            addresses_counterarguments=addresses_counterarguments,
            counterargument_quality=counterargument_quality,
        )

    def _empty_result(self) -> ArgumentationResult:
        """Return empty result."""
        return ArgumentationResult(
            primary_argument_type="mixed",
            argument_strength=0.0,
        )

    def _detect_argument_type(self, text: str) -> str:
        """Detect primary argument type."""
        deductive_count = sum(text.count(m) for m in self.DEDUCTIVE_MARKERS)
        inductive_count = sum(text.count(m) for m in self.INDUCTIVE_MARKERS)
        abductive_count = sum(text.count(m) for m in self.ABDUCTIVE_MARKERS)

        total = deductive_count + inductive_count + abductive_count
        if total == 0:
            return "mixed"

        if deductive_count > inductive_count and deductive_count > abductive_count:
            return "deductive"
        elif inductive_count > deductive_count and inductive_count > abductive_count:
            return "inductive"
        elif abductive_count > deductive_count and abductive_count > inductive_count:
            return "abductive"
        else:
            return "mixed"

    def _calc_argument_strength(self, text: str) -> float:
        """Calculate argument strength."""
        # Count strong argument markers
        strong_markers = [
            "必然", "一定", "毫无疑问", "显然", "必然",
            "证明", "证实", "验证", "确认",
        ]
        strong_count = sum(text.count(m) for m in strong_markers)

        # Count weak markers
        weak_markers = [
            "可能", "或许", "也许", "猜测", "估计",
        ]
        weak_count = sum(text.count(m) for m in weak_markers)

        # Calculate strength
        if strong_count + weak_count == 0:
            return 0.5

        return strong_count / (strong_count + weak_count)

    def _calc_logical_validity(self, text: str) -> float:
        """Calculate logical validity."""
        # Check for logical connectors
        logical_connectors = [
            "因为", "所以", "由于", "因此", "导致",
            "使得", "造成", "引起", "产生",
        ]
        connector_count = sum(text.count(c) for c in logical_connectors)

        # Normalize
        return min(1.0, connector_count / 5)

    def _calc_premise_clarity(self, text: str) -> float:
        """Calculate premise clarity."""
        # Check for premise markers
        premise_markers = [
            "前提是", "基础是", "假设", "假定",
            "基于", "根据", "依据", "按照",
        ]
        premise_count = sum(text.count(p) for p in premise_markers)

        # Normalize
        return min(1.0, premise_count / 3)

    def _calc_conclusion_support(self, text: str) -> float:
        """Calculate conclusion support."""
        # Check for conclusion markers with supporting content
        conclusion_patterns = [
            r"因此[，,]?(.{10,50})",
            r"所以[，,]?(.{10,50})",
            r"结论是[：:]?(.{10,50})",
        ]

        supported_conclusions = 0
        for pattern in conclusion_patterns:
            matches = re.findall(pattern, text)
            supported_conclusions += len(matches)

        return min(1.0, supported_conclusions / 2)

    def _detect_fallacies(self, text: str) -> List[str]:
        """Detect logical fallacies."""
        fallacies = []

        for fallacy_type, patterns in self.FALLACY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    fallacies.append(fallacy_type)
                    break

        return fallacies

    def _detect_persuasion_techniques(self, text: str) -> List[str]:
        """Detect persuasion techniques."""
        techniques = []

        for technique, pattern in self.PERSUASION_TECHNIQUES.items():
            if technique == "rhetorical_question":
                # Check question density
                question_count = text.count("?") + text.count("？")
                if question_count > 3:
                    techniques.append(technique)
            else:
                if re.search(pattern, text):
                    techniques.append(technique)

        return techniques

    def _calc_emotional_appeal(self, text: str) -> float:
        """Calculate emotional appeal ratio."""
        emotional_markers = [
            "太", "非常", "极其", "特别", "相当",
            "令人", "震惊", "惊讶", "感动", "愤怒",
        ]
        emotional_count = sum(text.count(m) for m in emotional_markers)

        # Normalize
        return min(1.0, emotional_count / 10)

    def _check_counter_arguments(self, text: str) -> bool:
        """Check if counter-arguments are addressed."""
        return any(m in text for m in self.COUNTER_ARGUMENT_MARKERS)

    def _calc_counterargument_quality(self, text: str) -> float:
        """Calculate counter-argument handling quality."""
        if not self._check_counter_arguments(text):
            return 0.0

        # Check for rebuttal markers
        rebuttal_markers = [
            "实际上", "事实上", "真实情况",
            "这忽略了", "这忽视了", "这没有考虑到",
            "反驳", "回应", "澄清",
        ]
        rebuttal_count = sum(text.count(m) for m in rebuttal_markers)

        return min(1.0, rebuttal_count / 2 + 0.3)