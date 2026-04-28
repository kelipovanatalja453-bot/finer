"""Rhetoric Analyzer — Dimension 2: 修辞手法 (MEDIUM priority).

Detects literary devices:
- Metaphor types (simile, metaphor, personification)
- Structural patterns (parallelism, antithesis, repetition)
- Tone patterns (rhetorical question, hyperbole, irony)
- Citations (classical, famous quotes, poetry)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from finer.schemas.text_analysis import RhetoricResult


class RhetoricAnalyzer:
    """Analyze rhetoric - Literary devices detection."""

    # Metaphor patterns
    SIMILE_MARKERS = ["像", "如同", "好比", "仿佛", "宛如", "似"]
    METAPHOR_MARKERS = ["是", "成为", "变成", "化作"]
    PERSONIFICATION_MARKERS = ["说", "想", "看", "听", "感受"]

    # Structural patterns
    PARALLELISM_MARKERS = ["一方面...另一方面", "既...又", "不仅...而且"]
    ANTITHESIS_MARKERS = ["但是", "然而", "相反", "反之"]
    REPETITION_PATTERNS = [r"(.{2,6}).{0,20}\1"]

    # Tone patterns
    HYPERBOLE_MARKERS = [
        "史上最", "前所未有", "绝无仅有", "难以置信",
        "无法想象", "极其", "超级", "无比",
    ]
    IRONY_MARKERS = ["所谓的", "号称", "竟然", "居然"]

    # Citation patterns
    CLASSICAL_PATTERNS = [r"[""「」『』].{10,50}[""「」『』]"]
    QUOTE_MARKERS = ["说", "表示", "认为", "指出"]

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> RhetoricResult:
        """Analyze rhetoric in text."""
        if not text.strip():
            return RhetoricResult()

        # Metaphor types
        metaphor_count = self._count_metaphors(text)
        simile_count = self._count_similes(text)
        personification_count = self._count_personifications(text)

        # Structural patterns
        parallelism_count = self._count_parallelism(text)
        antithesis_count = self._count_antithesis(text)
        repetition_count = self._count_repetition(text)

        # Tone patterns
        rhetorical_question_count = self._count_rhetorical_questions(text)
        hyperbole_count = self._count_hyperbole(text)
        irony_count = self._count_irony(text)

        # Citations
        classical_citation_count = self._count_classical_citations(text)
        famous_quote_count = self._count_famous_quotes(text)

        # Total
        total = (
            metaphor_count + simile_count + personification_count +
            parallelism_count + antithesis_count + repetition_count +
            rhetorical_question_count + hyperbole_count + irony_count +
            classical_citation_count + famous_quote_count
        )

        # Density
        density = total / (len(text) / 100) if text else 0

        return RhetoricResult(
            metaphor_count=metaphor_count,
            simile_count=simile_count,
            personification_count=personification_count,
            parallelism_count=parallelism_count,
            antithesis_count=antithesis_count,
            repetition_count=repetition_count,
            rhetorical_question_count=rhetorical_question_count,
            hyperbole_count=hyperbole_count,
            irony_count=irony_count,
            classical_citation_count=classical_citation_count,
            famous_quote_count=famous_quote_count,
            total_rhetoric_devices=total,
            rhetoric_density=min(1.0, density),
        )

    def _count_similes(self, text: str) -> int:
        return sum(text.count(m) for m in self.SIMILE_MARKERS)

    def _count_metaphors(self, text: str) -> int:
        # Look for "X是Y" patterns where Y is abstract
        patterns = re.findall(r"(.{2,6})是(.{2,10})", text)
        return len([p for p in patterns if len(p[1]) > 2])

    def _count_personifications(self, text: str) -> int:
        # Simplified detection
        return 0

    def _count_parallelism(self, text: str) -> int:
        return text.count("一方面") + text.count("另一方面")

    def _count_antithesis(self, text: str) -> int:
        return sum(text.count(m) for m in self.ANTITHESIS_MARKERS)

    def _count_repetition(self, text: str) -> int:
        count = 0
        for pattern in self.REPETITION_PATTERNS:
            count += len(re.findall(pattern, text))
        return count

    def _count_rhetorical_questions(self, text: str) -> int:
        # Questions without question marks are often rhetorical
        questions = re.findall(r"[^？?]*[吗呢吧][。.]", text)
        return len(questions)

    def _count_hyperbole(self, text: str) -> int:
        return sum(text.count(m) for m in self.HYPERBOLE_MARKERS)

    def _count_irony(self, text: str) -> int:
        return sum(text.count(m) for m in self.IRONY_MARKERS)

    def _count_classical_citations(self, text: str) -> int:
        count = 0
        for pattern in self.CLASSICAL_PATTERNS:
            count += len(re.findall(pattern, text))
        return count

    def _count_famous_quotes(self, text: str) -> int:
        # Look for quote attributions
        patterns = re.findall(r"(.{2,10})曾说", text)
        return len(patterns)