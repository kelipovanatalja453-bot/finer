"""Text Analysis Engine — Orchestrator for zhiziX 14-dimension analysis.

This module provides a unified interface for analyzing text using
all 14 dimensions from zhiziX's Writer Lab modeling system.

Usage:
    engine = TextAnalysisEngine()
    result = engine.analyze("这是一段文本...", dimensions=["surface_style", "argumentation"])
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from finer.schemas.text_analysis import (
    AnalysisDimension,
    TextAnalysisRequest,
    TextAnalysisResult,
    get_high_priority_dimensions,
    get_medium_priority_dimensions,
)
from finer.ml.sentiment.emotion_arc import EmotionArcAnalyzer

logger = logging.getLogger(__name__)


class TextAnalysisEngine:
    """Orchestrator for 14-dimension text analysis.

    Usage:
        engine = TextAnalysisEngine()
        result = engine.analyze(text, dimensions=[...])
    """

    def __init__(self):
        # Initialize analyzers (lazy)
        self._emotion_arc = EmotionArcAnalyzer()
        self._surface_style = None
        self._content_structure = None
        self._argumentation = None
        self._rhetoric = None
        self._cognitive_pattern = None
        self._rhythm = None
        self._reader_engagement = None
        self._audience_target = None

    def _get_surface_style(self):
        if self._surface_style is None:
            from finer.ml.sentiment.text_dimensions.surface_style import SurfaceStyleAnalyzer
            self._surface_style = SurfaceStyleAnalyzer()
        return self._surface_style

    def _get_content_structure(self):
        if self._content_structure is None:
            from finer.ml.sentiment.text_dimensions.content_structure import ContentStructureAnalyzer
            self._content_structure = ContentStructureAnalyzer()
        return self._content_structure

    def _get_argumentation(self):
        if self._argumentation is None:
            from finer.ml.sentiment.text_dimensions.argumentation import ArgumentationAnalyzer
            self._argumentation = ArgumentationAnalyzer()
        return self._argumentation

    def _get_rhetoric(self):
        if self._rhetoric is None:
            from finer.ml.sentiment.text_dimensions.rhetoric import RhetoricAnalyzer
            self._rhetoric = RhetoricAnalyzer()
        return self._rhetoric

    def _get_cognitive_pattern(self):
        if self._cognitive_pattern is None:
            from finer.ml.sentiment.text_dimensions.cognitive_pattern import CognitivePatternAnalyzer
            self._cognitive_pattern = CognitivePatternAnalyzer()
        return self._cognitive_pattern

    def _get_rhythm(self):
        if self._rhythm is None:
            from finer.ml.sentiment.text_dimensions.rhythm import RhythmAnalyzer
            self._rhythm = RhythmAnalyzer()
        return self._rhythm

    def _get_reader_engagement(self):
        if self._reader_engagement is None:
            from finer.ml.sentiment.text_dimensions.reader_engagement import ReaderEngagementAnalyzer
            self._reader_engagement = ReaderEngagementAnalyzer()
        return self._reader_engagement

    def _get_audience_target(self):
        if self._audience_target is None:
            from finer.ml.sentiment.text_dimensions.audience_target import AudienceTargetAnalyzer
            self._audience_target = AudienceTargetAnalyzer()
        return self._audience_target

    def analyze(
        self,
        text: str,
        dimensions: Optional[List[AnalysisDimension]] = None,
        language: str = "zh",
        context: Optional[Dict[str, Any]] = None,
    ) -> TextAnalysisResult:
        """Analyze text using specified dimensions.

        Args:
            text: Text to analyze
            dimensions: Dimensions to analyze (None = all)
            language: Text language
            context: Additional context

        Returns:
            TextAnalysisResult with all dimension results
        """
        if not text.strip():
            return TextAnalysisResult(
                text_length=0,
                overall_quality_score=0.0,
            )

        # Default to all dimensions
        if dimensions is None:
            dimensions = list(AnalysisDimension)

        # Analyze each dimension
        results: Dict[str, Any] = {}
        analyzed: List[AnalysisDimension] = []

        for dim in dimensions:
            try:
                result = self._analyze_dimension(dim, text, context)
                if result is not None:
                    results[dim.value] = result
                    analyzed.append(dim)
            except Exception as e:
                logger.warning(f"Failed to analyze dimension {dim}: {e}")

        # Calculate overall quality score
        overall_score = self._calc_overall_score(results)

        # Build KOL fingerprint
        kol_fingerprint = self._build_kol_fingerprint(results)

        return TextAnalysisResult(
            text_length=len(text),
            analysis_time=datetime.now(),
            dimensions_analyzed=analyzed,
            surface_style=results.get("surface_style"),
            rhetoric=results.get("rhetoric"),
            emotion_arc=results.get("emotion_arc"),
            content_structure=results.get("content_structure"),
            cognitive_pattern=results.get("cognitive_pattern"),
            rhythm=results.get("rhythm"),
            narrative=results.get("narrative"),
            argumentation=results.get("argumentation"),
            cultural_context=results.get("cultural_context"),
            audience_target=results.get("audience_target"),
            special_requirements=results.get("special_requirements"),
            reader_engagement=results.get("reader_engagement"),
            multimodal=results.get("multimodal"),
            language_variation=results.get("language_variation"),
            overall_quality_score=overall_score,
            kol_fingerprint=kol_fingerprint,
        )

    def analyze_dimension(
        self,
        dimension: AnalysisDimension,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Analyze a single dimension.

        Args:
            dimension: Dimension to analyze
            text: Text to analyze
            context: Additional context

        Returns:
            Dimension-specific result
        """
        return self._analyze_dimension(dimension, text, context)

    def _analyze_dimension(
        self,
        dimension: AnalysisDimension,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Internal dimension analysis."""
        if dimension == AnalysisDimension.SURFACE_STYLE:
            return self._get_surface_style().analyze(text, context)

        elif dimension == AnalysisDimension.RHETORIC:
            return self._get_rhetoric().analyze(text, context)

        elif dimension == AnalysisDimension.EMOTION_ARC:
            arc = self._emotion_arc.analyze(text)
            return arc.model_dump()

        elif dimension == AnalysisDimension.CONTENT_STRUCTURE:
            return self._get_content_structure().analyze(text, context)

        elif dimension == AnalysisDimension.COGNITIVE_PATTERN:
            return self._get_cognitive_pattern().analyze(text, context)

        elif dimension == AnalysisDimension.RHYTHM:
            return self._get_rhythm().analyze(text, context)

        elif dimension == AnalysisDimension.ARGUMENTATION:
            return self._get_argumentation().analyze(text, context)

        elif dimension == AnalysisDimension.READER_ENGAGEMENT:
            return self._get_reader_engagement().analyze(text, context)

        elif dimension == AnalysisDimension.AUDIENCE_TARGET:
            return self._get_audience_target().analyze(text, context)

        # LOW priority dimensions - simplified implementations
        elif dimension == AnalysisDimension.NARRATIVE:
            return {"perspective": "unknown", "time_structure": "chronological"}

        elif dimension == AnalysisDimension.CULTURAL_CONTEXT:
            return {"cultural_references": [], "era_references": []}

        elif dimension == AnalysisDimension.SPECIAL_REQUIREMENTS:
            return {"detected_constraints": [], "emphasis_priorities": []}

        elif dimension == AnalysisDimension.MULTIMODAL:
            return {"punctuation_style": "standard", "emoji_count": 0}

        elif dimension == AnalysisDimension.LANGUAGE_VARIATION:
            return {"formality_shifts": 0, "register_switches": []}

        return None

    def _calc_overall_score(self, results: Dict[str, Any]) -> float:
        """Calculate overall quality score."""
        if not results:
            return 0.0

        scores = []

        # Surface style contributes to quality
        if "surface_style" in results:
            ss = results["surface_style"]
            scores.append(ss.tone_consistency)

        # Content structure contributes
        if "content_structure" in results:
            cs = results["content_structure"]
            scores.append(cs.logical_flow_score)
            scores.append(cs.coherence_score)

        # Argumentation contributes
        if "argumentation" in results:
            arg = results["argumentation"]
            scores.append(arg.argument_strength)
            scores.append(arg.logical_validity)

        # Emotion arc contributes
        if "emotion_arc" in results:
            arc = results["emotion_arc"]
            # Use variance as a quality indicator
            scores.append(1 - arc.get("variance", 0.5) * 0.5)

        return sum(scores) / len(scores) if scores else 0.5

    def _build_kol_fingerprint(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Build aggregated KOL voice fingerprint."""
        fingerprint = {}

        # From surface style
        if "surface_style" in results:
            ss = results["surface_style"]
            fingerprint["writing_style"] = ss.writing_style
            fingerprint["formality"] = ss.formality_score
            fingerprint["expertise"] = ss.expertise_level
            fingerprint["signature_phrases"] = ss.signature_phrases[:3]

        # From content structure
        if "content_structure" in results:
            cs = results["content_structure"]
            fingerprint["structure_type"] = cs.structure_type
            fingerprint["argument_quality"] = cs.logical_flow_score

        # From argumentation
        if "argumentation" in results:
            arg = results["argumentation"]
            fingerprint["reasoning_type"] = arg.primary_argument_type
            fingerprint["reasoning_strength"] = arg.argument_strength

        return fingerprint


# Convenience function
def analyze_text(
    text: str,
    dimensions: Optional[List[AnalysisDimension]] = None,
    language: str = "zh",
) -> TextAnalysisResult:
    """Analyze text using zhiziX dimensions.

    Args:
        text: Text to analyze
        dimensions: Dimensions to analyze (None = all)
        language: Text language

    Returns:
        TextAnalysisResult
    """
    engine = TextAnalysisEngine()
    return engine.analyze(text, dimensions, language)
