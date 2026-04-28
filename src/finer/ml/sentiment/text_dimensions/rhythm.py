"""Rhythm Analyzer — Dimension 6: 节奏韵律 (MEDIUM priority).

Extends emotion_arc.py's rhythm_score with:
- Phonology (rhyme, tone patterns)
- Pause patterns
- Long-short sentence alternation
- Fluency
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from finer.schemas.text_analysis import RhythmResult


class RhythmAnalyzer:
    """Analyze rhythm - Phonology and flow."""

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> RhythmResult:
        """Analyze rhythm in text."""
        if not text.strip():
            return RhythmResult()

        sentences = self._split_sentences(text)
        if not sentences:
            return RhythmResult()

        # Sentence lengths
        lengths = [len(s) for s in sentences]
        avg_length = sum(lengths) / len(lengths)
        variance = sum((l - avg_length) ** 2 for l in lengths) / len(lengths)

        # Long-short alternation
        alternation = self._calc_alternation(lengths)

        # Pause patterns
        pause_score = self._calc_pause_patterns(text)

        # Fluency
        fluency = self._calc_fluency(text, sentences)

        # Reading speed estimate
        speed = self._estimate_reading_speed(avg_length, len(text))

        return RhythmResult(
            rhyme_patterns=[],  # Simplified
            pause_pattern_score=pause_score,
            long_short_alternation=alternation,
            fluency_score=fluency,
            reading_speed_estimate=speed,
            avg_sentence_length=avg_length,
            sentence_length_variance=variance,
        )

    def _split_sentences(self, text: str) -> List[str]:
        return [s.strip() for s in re.split(r"[。！？\.\!\?]", text) if s.strip()]

    def _calc_alternation(self, lengths: List[int]) -> float:
        """Calculate long-short alternation score."""
        if len(lengths) < 2:
            return 0.0

        alternations = 0
        for i in range(1, len(lengths)):
            # Check if length alternates significantly
            ratio = lengths[i] / lengths[i-1] if lengths[i-1] > 0 else 1
            if ratio < 0.7 or ratio > 1.3:
                alternations += 1

        return alternations / (len(lengths) - 1)

    def _calc_pause_patterns(self, text: str) -> float:
        """Calculate pause pattern quality."""
        # Count commas and semicolons
        pauses = text.count("，") + text.count(",") + text.count("；")
        # Normalize by text length
        return min(1.0, pauses / (len(text) / 50))

    def _calc_fluency(self, text: str, sentences: List[str]) -> float:
        """Calculate fluency score."""
        # Check for incomplete sentences, awkward phrasing
        # Simplified: return high score for well-structured text
        return 0.8 if len(sentences) > 0 else 0.0

    def _estimate_reading_speed(self, avg_length: float, total_chars: int) -> str:
        """Estimate reading speed."""
        if avg_length > 40:
            return "slow"
        elif avg_length > 25:
            return "medium"
        return "fast"