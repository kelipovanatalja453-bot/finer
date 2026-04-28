"""Text Dimensions — zhiziX 14-dimension text analysis.

This package provides analyzers for the 14 modeling dimensions from zhiziX:

HIGH Priority:
- surface_style: KOL voice fingerprint
- content_structure: Argument quality
- argumentation: Reasoning quality

MEDIUM Priority:
- rhetoric: Literary devices
- cognitive_pattern: Thinking mode
- rhythm: Phonology and flow
- reader_engagement: Audience interaction
- audience_target: Reader expertise

LOW Priority:
- narrative: Story architecture
- cultural_context: Cultural references
- multimodal: Emoji, punctuation
- language_variation: Formality shifts
- special_requirements: Constraints

Emotion Arc (Dimension 3) is implemented in emotion_arc.py.
"""

from __future__ import annotations

from finer.ml.sentiment.text_dimensions.surface_style import SurfaceStyleAnalyzer
from finer.ml.sentiment.text_dimensions.content_structure import ContentStructureAnalyzer
from finer.ml.sentiment.text_dimensions.argumentation import ArgumentationAnalyzer
from finer.ml.sentiment.text_dimensions.rhetoric import RhetoricAnalyzer
from finer.ml.sentiment.text_dimensions.cognitive_pattern import CognitivePatternAnalyzer
from finer.ml.sentiment.text_dimensions.rhythm import RhythmAnalyzer
from finer.ml.sentiment.text_dimensions.reader_engagement import ReaderEngagementAnalyzer
from finer.ml.sentiment.text_dimensions.audience_target import AudienceTargetAnalyzer

__all__ = [
    "SurfaceStyleAnalyzer",
    "ContentStructureAnalyzer",
    "ArgumentationAnalyzer",
    "RhetoricAnalyzer",
    "CognitivePatternAnalyzer",
    "RhythmAnalyzer",
    "ReaderEngagementAnalyzer",
    "AudienceTargetAnalyzer",
]