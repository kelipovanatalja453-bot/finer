"""Surface Style Analyzer — Dimension 1: 表层风格 (HIGH priority).

Measures quantifiable text surface features across 5 layers:
- Lexical: pronoun ratios, colloquialism, term density, self-deprecation
- Syntactic: sentence length, complexity, special patterns, passive voice
- Paragraph: length, transitions, opening patterns
- Discourse: opening/closing patterns, memorable phrase density
- Pragmatic: argumentation style, reader relation, values orientation

For KOL analysis, this provides a "voice fingerprint" for identifying
and clustering KOLs by writing style.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from finer.schemas.text_analysis import SurfaceStyleResult


class SurfaceStyleAnalyzer:
    """Analyze surface style - KOL voice fingerprint.

    Usage:
        analyzer = SurfaceStyleAnalyzer()
        result = analyzer.analyze("这是一段文本...")
        print(result.formality_score, result.writing_style)
    """

    # Chinese pronouns
    FIRST_PERSON_PRONOUNS = {"我", "我们", "咱", "咱们", "本人", "笔者"}
    SECOND_PERSON_PRONOUNS = {"你", "您", "你们", "各位", "大家"}
    THIRD_PERSON_PRONOUNS = {"他", "她", "它", "他们", "她们", "它们"}

    # Colloquial markers
    COLLOQUIAL_MARKERS = {
        "啊", "吧", "呢", "嘛", "哦", "呀", "哈", "呗",
        "就是", "其实", "反正", "怎么说呢", "怎么说",
        "那个", "这个", "然后", "所以", "对吧",
    }

    # Formal markers
    FORMAL_MARKERS = {
        "因此", "故", "鉴于", "综上所述", "由此可见",
        "首先", "其次", "最后", "总之", "综上所述",
        "应当", "应", "须", "需", "可", "将",
        "关于", "对于", "针对", "就", "在",
    }

    # Professional/technical terms
    TECHNICAL_PATTERNS = [
        r"\d+%",  # Percentages
        r"\d+\.?\d*亿",  # Large numbers (亿)
        r"\d+\.?\d*万",  # Large numbers (万)
        r"[A-Z]{2,}",  # Acronyms (GDP, CPI, etc.)
        r"[\d,]+点",  # Points/indices
    ]

    # Sentence ending patterns
    SENTENCE_ENDINGS = re.compile(r"[。！？\.\!\?]")

    def __init__(self):
        pass

    def analyze(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SurfaceStyleResult:
        """Analyze surface style of text.

        Args:
            text: Text to analyze
            context: Optional context (KOL info, topic, etc.)

        Returns:
            SurfaceStyleResult with voice fingerprint
        """
        if not text.strip():
            return self._empty_result()

        # Split into sentences and paragraphs
        sentences = self._split_sentences(text)
        paragraphs = self._split_paragraphs(text)

        # Lexical analysis
        pronoun_ratio = self._calc_pronoun_ratio(text)
        colloquialism_score = self._calc_colloquialism(text)
        term_density = self._calc_term_density(text)

        # Syntactic analysis
        sentence_lengths = [len(s) for s in sentences if s.strip()]
        avg_sentence_length = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0
        sentence_complexity = self._calc_sentence_complexity(sentences)

        # Paragraph analysis
        paragraph_lengths = [len(p) for p in paragraphs if p.strip()]
        avg_paragraph_length = sum(paragraph_lengths) / len(paragraph_lengths) if paragraph_lengths else 0

        # Formality score (0=colloquial, 1=formal)
        formality_score = self._calc_formality(text, colloquialism_score)

        # Emotional tone
        emotional_tone = self._detect_emotional_tone(text)

        # Writing style
        writing_style = self._classify_writing_style(
            formality_score,
            sentence_complexity,
            colloquialism_score,
        )

        # Vocabulary level
        vocabulary_level = self._classify_vocabulary(term_density, avg_sentence_length)

        # Expertise level
        expertise_level = self._calc_expertise(term_density, sentence_complexity)

        # Personal brand keywords
        personal_brand_keywords = self._extract_brand_keywords(text)

        # Signature phrases
        signature_phrases = self._extract_signature_phrases(text)

        # Tone consistency
        tone_consistency = self._calc_tone_consistency(paragraphs)

        return SurfaceStyleResult(
            formality_score=formality_score,
            emotional_tone=emotional_tone,
            expertise_level=expertise_level,
            writing_style=writing_style,
            vocabulary_level=vocabulary_level,
            sentence_complexity=sentence_complexity,
            pronoun_ratio=pronoun_ratio,
            colloquialism_score=colloquialism_score,
            term_density=term_density,
            personal_brand_keywords=personal_brand_keywords,
            signature_phrases=signature_phrases,
            tone_consistency=tone_consistency,
        )

    def _empty_result(self) -> SurfaceStyleResult:
        """Return empty result for empty text."""
        return SurfaceStyleResult(
            formality_score=0.5,
            emotional_tone="neutral",
            expertise_level=0.5,
            writing_style="neutral",
            vocabulary_level="moderate",
            sentence_complexity=0.5,
        )

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        return [s.strip() for s in self.SENTENCE_ENDINGS.split(text) if s.strip()]

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        return [p.strip() for p in text.split("\n\n") if p.strip()]

    def _calc_pronoun_ratio(self, text: str) -> float:
        """Calculate pronoun usage ratio."""
        total_chars = len(text)
        if total_chars == 0:
            return 0.0

        pronoun_count = 0
        for pronoun in self.FIRST_PERSON_PRONOUNS | self.SECOND_PERSON_PRONOUNS | self.THIRD_PERSON_PRONOUNS:
            pronoun_count += text.count(pronoun)

        # Normalize by text length (per 100 chars)
        return min(1.0, pronoun_count / (total_chars / 100) * 0.5)

    def _calc_colloquialism(self, text: str) -> float:
        """Calculate colloquialism score."""
        total_chars = len(text)
        if total_chars == 0:
            return 0.0

        colloquial_count = 0
        for marker in self.COLLOQUIAL_MARKERS:
            colloquial_count += text.count(marker)

        # Normalize
        return min(1.0, colloquial_count / (total_chars / 100) * 0.3)

    def _calc_term_density(self, text: str) -> float:
        """Calculate technical term density."""
        total_chars = len(text)
        if total_chars == 0:
            return 0.0

        term_count = 0
        for pattern in self.TECHNICAL_PATTERNS:
            matches = re.findall(pattern, text)
            term_count += len(matches)

        # Normalize
        return min(1.0, term_count / (total_chars / 100) * 0.5)

    def _calc_sentence_complexity(self, sentences: List[str]) -> float:
        """Calculate sentence complexity based on structure."""
        if not sentences:
            return 0.5

        complexity_scores = []
        for sentence in sentences:
            if not sentence.strip():
                continue

            score = 0.0

            # Length factor
            if len(sentence) > 50:
                score += 0.3
            elif len(sentence) > 30:
                score += 0.2

            # Clause markers
            clause_markers = ["，", "、", "；", ",", ";"]
            for marker in clause_markers:
                score += sentence.count(marker) * 0.1

            # Nested structure
            if "（" in sentence or "(" in sentence:
                score += 0.2
            if "【" in sentence or "[" in sentence:
                score += 0.1

            complexity_scores.append(min(1.0, score))

        return sum(complexity_scores) / len(complexity_scores) if complexity_scores else 0.5

    def _calc_formality(self, text: str, colloquialism: float) -> float:
        """Calculate formality score."""
        total_chars = len(text)
        if total_chars == 0:
            return 0.5

        formal_count = 0
        for marker in self.FORMAL_MARKERS:
            formal_count += text.count(marker)

        formal_ratio = formal_count / (total_chars / 100) * 0.3

        # Balance with colloquialism
        formality = 0.5 + formal_ratio - colloquialism * 0.5
        return max(0.0, min(1.0, formality))

    def _detect_emotional_tone(self, text: str) -> str:
        """Detect primary emotional tone."""
        # Positive markers
        positive = ["好", "优", "强", "涨", "增", "利", "喜", "乐", "期待", "看好"]
        # Negative markers
        negative = ["差", "弱", "跌", "减", "弊", "忧", "虑", "担心", "风险", "谨慎"]
        # Neutral markers
        neutral = ["认为", "觉得", "分析", "观察", "来看", "而言", "来说"]

        pos_count = sum(text.count(p) for p in positive)
        neg_count = sum(text.count(n) for n in negative)
        neu_count = sum(text.count(n) for n in neutral)

        total = pos_count + neg_count + neu_count
        if total == 0:
            return "neutral"

        if pos_count > neg_count and pos_count > neu_count:
            return "positive"
        elif neg_count > pos_count and neg_count > neu_count:
            return "negative"
        else:
            return "neutral"

    def _classify_writing_style(
        self,
        formality: float,
        complexity: float,
        colloquialism: float,
    ) -> str:
        """Classify writing style."""
        if formality > 0.7 and complexity > 0.6:
            return "academic"
        elif formality > 0.6:
            return "professional"
        elif colloquialism > 0.5:
            return "casual"
        elif formality < 0.4:
            return "conversational"
        else:
            return "balanced"

    def _classify_vocabulary(self, term_density: float, avg_length: float) -> str:
        """Classify vocabulary complexity."""
        if term_density > 0.5 or avg_length > 40:
            return "complex"
        elif term_density > 0.3 or avg_length > 25:
            return "moderate"
        else:
            return "simple"

    def _calc_expertise(self, term_density: float, complexity: float) -> float:
        """Calculate expertise projection level."""
        return (term_density * 0.6 + complexity * 0.4)

    def _extract_brand_keywords(self, text: str) -> List[str]:
        """Extract potential personal brand keywords."""
        # Look for repeated distinctive phrases
        # This is a simplified version
        brand_keywords = []

        # Check for common KOL signature patterns
        patterns = [
            r"我是(.{2,10})",
            r"作为(.{2,10})",
            r"(.{2,10})认为",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            brand_keywords.extend(matches[:2])

        return brand_keywords[:5]

    def _extract_signature_phrases(self, text: str) -> List[str]:
        """Extract signature phrases."""
        # Look for repeated phrases
        phrases = []

        # Common signature patterns
        patterns = [
            r"(.{4,10})吧",
            r"(.{4,10})呢",
            r"总的来说[，,]?(.{4,20})",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            phrases.extend(matches[:2])

        return phrases[:5]

    def _calc_tone_consistency(self, paragraphs: List[str]) -> float:
        """Calculate tone consistency across paragraphs."""
        if len(paragraphs) < 2:
            return 1.0

        # Analyze tone of each paragraph
        tones = [self._detect_emotional_tone(p) for p in paragraphs if p.strip()]

        if not tones:
            return 1.0

        # Calculate consistency
        tone_counts = {}
        for tone in tones:
            tone_counts[tone] = tone_counts.get(tone, 0) + 1

        dominant_count = max(tone_counts.values())
        return dominant_count / len(tones)
