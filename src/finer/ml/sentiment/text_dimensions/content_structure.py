"""Content Structure Analyzer — Dimension 4: 内容结构 (HIGH priority).

Measures:
- Overall structure pattern (pyramid, inverted, parallel, progressive)
- Information density per paragraph
- Argument-evidence chain structure
- Logical flow and coherence
- Thesis detection and position

For KOL analysis, this provides argument quality metrics.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from finer.schemas.text_analysis import ContentStructureResult


class ContentStructureAnalyzer:
    """Analyze content structure - Argument quality.

    Usage:
        analyzer = ContentStructureAnalyzer()
        result = analyzer.analyze("这是一段文本...")
        print(result.structure_type, result.has_clear_thesis)
    """

    # Thesis indicators
    THESIS_INDICATORS = [
        r"我认为",
        r"我的观点是",
        r"总的来说",
        r"综上所述",
        r"核心观点",
        r"主要观点",
        r"关键在于",
        r"重点是",
        r"结论是",
        r"因此[，,]?(.{5,30})",
    ]

    # Evidence markers
    EVIDENCE_MARKERS = {
        "data": ["数据", "统计", "显示", "报告", "调查", "%", "亿", "万"],
        "case": ["案例", "例子", "比如", "例如", "如", "实例"],
        "authority": ["专家", "学者", "研究", "论文", "报告", "机构"],
    }

    # Structure patterns
    STRUCTURE_PATTERNS = {
        "pyramid": ["首先", "其次", "最后", "总之"],  # 总-分-总
        "inverted": ["结论", "因此", "具体来说", "首先"],  # 分-总
        "parallel": ["一方面", "另一方面", "同时", "同样"],  # 并列
        "progressive": ["进一步", "更深", "不仅", "而且", "进而"],  # 递进
    }

    # Transition markers
    TRANSITION_MARKERS = [
        "但是", "然而", "不过", "相反", "另一方面",
        "因此", "所以", "故", "于是",
        "首先", "其次", "再次", "最后",
        "具体来说", "换句话说", "换言之",
    ]

    def __init__(self):
        pass

    def analyze(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ContentStructureResult:
        """Analyze content structure.

        Args:
            text: Text to analyze
            context: Optional context

        Returns:
            ContentStructureResult with structure analysis
        """
        if not text.strip():
            return self._empty_result()

        paragraphs = self._split_paragraphs(text)
        sentences = self._split_sentences(text)

        # Structure type
        structure_type = self._detect_structure_type(text, paragraphs)

        # Thesis detection
        thesis_result = self._detect_thesis(text, paragraphs)
        has_clear_thesis = thesis_result["has_thesis"]
        thesis_position = thesis_result["position"]

        # Supporting points
        supporting_points = self._count_supporting_points(text)

        # Evidence analysis
        evidence_types = self._detect_evidence_types(text)
        evidence_quality_score = self._calc_evidence_quality(evidence_types, supporting_points)
        citation_count = self._count_citations(text)

        # Logical flow
        logical_flow_score = self._calc_logical_flow(text, paragraphs)
        coherence_score = self._calc_coherence(text, paragraphs)
        transition_quality = self._calc_transition_quality(text)

        # Information density
        information_density = self._calc_information_density(text, paragraphs)
        redundancy_ratio = self._calc_redundancy(text)

        # Section breakdown
        sections = self._analyze_sections(paragraphs)

        return ContentStructureResult(
            structure_type=structure_type,
            section_count=len(paragraphs),
            paragraph_count=len(sentences),
            has_clear_thesis=has_clear_thesis,
            thesis_position=thesis_position,
            supporting_points=supporting_points,
            evidence_types=evidence_types,
            evidence_quality_score=evidence_quality_score,
            citation_count=citation_count,
            logical_flow_score=logical_flow_score,
            coherence_score=coherence_score,
            transition_quality=transition_quality,
            information_density=information_density,
            redundancy_ratio=redundancy_ratio,
            sections=sections,
        )

    def _empty_result(self) -> ContentStructureResult:
        """Return empty result."""
        return ContentStructureResult(
            structure_type="mixed",
            section_count=0,
            paragraph_count=0,
            has_clear_thesis=False,
            thesis_position="",
            supporting_points=0,
            evidence_quality_score=0.0,
            logical_flow_score=0.0,
            coherence_score=0.0,
            transition_quality=0.0,
            information_density=0.0,
            redundancy_ratio=0.0,
        )

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        return [p.strip() for p in text.split("\n\n") if p.strip()]

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        return [s.strip() for s in re.split(r"[。！？\.\!\?]", text) if s.strip()]

    def _detect_structure_type(self, text: str, paragraphs: List[str]) -> str:
        """Detect overall structure pattern."""
        if len(paragraphs) < 3:
            return "simple"

        # Check for structure markers
        scores = {}
        for pattern_type, markers in self.STRUCTURE_PATTERNS.items():
            score = sum(text.count(marker) for marker in markers)
            scores[pattern_type] = score

        # Find dominant pattern
        if scores:
            max_pattern = max(scores, key=scores.get)
            if scores[max_pattern] >= 2:
                return max_pattern

        # Check paragraph positions
        first_para = paragraphs[0] if paragraphs else ""
        last_para = paragraphs[-1] if paragraphs else ""

        # Check if thesis is at beginning or end
        thesis_at_start = any(
            re.search(pattern, first_para)
            for pattern in self.THESIS_INDICATORS[:3]
        )
        thesis_at_end = any(
            re.search(pattern, last_para)
            for pattern in self.THESIS_INDICATORS[3:]
        )

        if thesis_at_start and thesis_at_end:
            return "pyramid"
        elif thesis_at_start:
            return "inverted"
        elif thesis_at_end:
            return "progressive"

        return "mixed"

    def _detect_thesis(self, text: str, paragraphs: List[str]) -> Dict[str, Any]:
        """Detect thesis statement."""
        result = {"has_thesis": False, "position": "", "thesis_text": ""}

        for pattern in self.THESIS_INDICATORS:
            matches = re.findall(pattern, text)
            if matches:
                result["has_thesis"] = True
                # Find position
                match_pos = text.find(str(matches[0]) if matches else "")
                if match_pos < len(text) * 0.3:
                    result["position"] = "opening"
                elif match_pos > len(text) * 0.7:
                    result["position"] = "closing"
                else:
                    result["position"] = "middle"
                break

        return result

    def _count_supporting_points(self, text: str) -> int:
        """Count supporting points."""
        count = 0

        # Numbered points
        numbered = re.findall(r"[第]?[一二三四五六七八九十\d]+[，,.：:点]", text)
        count += len(numbered)

        # Bullet-like markers
        bullets = re.findall(r"[•●○]", text)
        count += len(bullets)

        # "首先/其次/最后" pattern
        sequence_markers = ["首先", "其次", "再次", "最后"]
        count += sum(1 for m in sequence_markers if m in text)

        return count

    def _detect_evidence_types(self, text: str) -> List[str]:
        """Detect evidence types used."""
        types = []

        for evidence_type, markers in self.EVIDENCE_MARKERS.items():
            if any(marker in text for marker in markers):
                types.append(evidence_type)

        return types

    def _calc_evidence_quality(self, evidence_types: List[str], points: int) -> float:
        """Calculate evidence quality score."""
        if not evidence_types:
            return 0.0

        # More evidence types = better
        type_score = len(evidence_types) / 3

        # More supporting points with evidence = better
        point_score = min(1.0, points / 5)

        return (type_score * 0.4 + point_score * 0.6)

    def _count_citations(self, text: str) -> int:
        """Count citations/references."""
        count = 0

        # Quote markers
        quotes = re.findall(r"[""「」『』]", text)
        count += len(quotes) // 2

        # Citation patterns
        citations = re.findall(r"据.{2,10}报道", text)
        count += len(citations)

        citations = re.findall(r"(.{2,10})表示", text)
        count += len(citations)

        return count

    def _calc_logical_flow(self, text: str, paragraphs: List[str]) -> float:
        """Calculate logical flow score."""
        if len(paragraphs) < 2:
            return 1.0

        # Check for logical connectors
        connectors = ["因为", "所以", "由于", "因此", "故", "导致", "使得", "造成"]
        connector_count = sum(text.count(c) for c in connectors)

        # Normalize
        return min(1.0, connector_count / len(paragraphs) * 0.3)

    def _calc_coherence(self, text: str, paragraphs: List[str]) -> float:
        """Calculate coherence score."""
        if len(paragraphs) < 2:
            return 1.0

        # Check for paragraph transitions
        transition_count = sum(
            1 for marker in self.TRANSITION_MARKERS
            if marker in text
        )

        # Normalize
        return min(1.0, transition_count / len(paragraphs) * 0.5)

    def _calc_transition_quality(self, text: str) -> float:
        """Calculate transition quality."""
        # Check for explicit transitions
        explicit_transitions = [
            "具体来说", "换句话说", "换言之", "进一步",
            "另一方面", "与此同时", "不仅如此",
        ]

        count = sum(1 for t in explicit_transitions if t in text)

        return min(1.0, count / 3)

    def _calc_information_density(self, text: str, paragraphs: List[str]) -> float:
        """Calculate information density."""
        if not paragraphs:
            return 0.0

        # Count meaningful content (excluding whitespace and punctuation)
        total_chars = len(text)
        meaningful_chars = len(re.sub(r"[^\w]", "", text))

        # Normalize
        return meaningful_chars / total_chars if total_chars > 0 else 0.0

    def _calc_redundancy(self, text: str) -> float:
        """Calculate redundancy ratio."""
        # Check for repeated phrases
        words = re.findall(r"\w{2,}", text)
        if len(words) < 10:
            return 0.0

        # Count unique vs total
        unique_words = set(words)
        redundancy = 1 - (len(unique_words) / len(words))

        return redundancy

    def _analyze_sections(self, paragraphs: List[str]) -> List[Dict[str, Any]]:
        """Analyze individual sections."""
        sections = []

        for i, para in enumerate(paragraphs):
            section = {
                "index": i,
                "length": len(para),
                "type": self._classify_section_type(para),
                "has_thesis": any(
                    re.search(p, para)
                    for p in self.THESIS_INDICATORS
                ),
            }
            sections.append(section)

        return sections

    def _classify_section_type(self, paragraph: str) -> str:
        """Classify paragraph type."""
        # Check for thesis
        if any(re.search(p, paragraph) for p in self.THESIS_INDICATORS):
            return "thesis"

        # Check for evidence
        for markers in self.EVIDENCE_MARKERS.values():
            if any(m in paragraph for m in markers):
                return "evidence"

        # Check for conclusion
        conclusion_markers = ["总之", "综上所述", "结论", "因此"]
        if any(m in paragraph for m in conclusion_markers):
            return "conclusion"

        return "content"