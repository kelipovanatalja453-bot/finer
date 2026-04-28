"""Text Analysis Schemas — zhiziX 14-dimension modeling.

This module defines schemas for the 14-dimension text analysis system
inspired by zhiziX's Writer Lab modeling dimensions.

Dimensions:
1. Surface Style (表层风格) - HIGH priority - KOL voice fingerprint
2. Rhetoric (修辞手法) - MEDIUM priority
3. Emotion Arc (情感曲线) - EXISTS in emotion_arc.py
4. Content Structure (内容结构) - HIGH priority - Argument quality
5. Cognitive Pattern (认知模式) - MEDIUM priority
6. Rhythm (节奏韵律) - MEDIUM priority
7. Narrative (叙事技巧) - LOW priority
8. Argumentation (论证策略) - HIGH priority - Reasoning quality
9. Cultural Context (文化语境) - LOW priority
10. Audience Target (受众定位) - MEDIUM priority
11. Special Requirements (特殊要求) - LOW priority
12. Reader Engagement (读者互动) - MEDIUM priority
13. Multimodal (多模态特征) - LOW priority
14. Language Variation (语言变异) - LOW priority
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AnalysisDimension(str, Enum):
    """14 analysis dimensions from zhiziX."""

    SURFACE_STYLE = "surface_style"  # 1: 表层风格
    RHETORIC = "rhetoric"  # 2: 修辞手法
    EMOTION_ARC = "emotion_arc"  # 3: 情感曲线
    CONTENT_STRUCTURE = "content_structure"  # 4: 内容结构
    COGNITIVE_PATTERN = "cognitive_pattern"  # 5: 认知模式
    RHYTHM = "rhythm"  # 6: 节奏韵律
    NARRATIVE = "narrative"  # 7: 叙事技巧
    ARGUMENTATION = "argumentation"  # 8: 论证策略
    CULTURAL_CONTEXT = "cultural_context"  # 9: 文化语境
    AUDIENCE_TARGET = "audience_target"  # 10: 受众定位
    SPECIAL_REQUIREMENTS = "special_requirements"  # 11: 特殊要求
    READER_ENGAGEMENT = "reader_engagement"  # 12: 读者互动
    MULTIMODAL = "multimodal"  # 13: 多模态特征
    LANGUAGE_VARIATION = "language_variation"  # 14: 语言变异


class DimensionPriority(str, Enum):
    """Priority level for analysis dimensions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Dimension 1: Surface Style (表层风格) - KOL voice fingerprint
class SurfaceStyleResult(BaseModel):
    """Surface style analysis - KOL voice fingerprint.

    Measures quantifiable text surface features across 5 layers:
    - Lexical: pronoun ratios, colloquialism, term density
    - Syntactic: sentence length, complexity, special patterns
    - Paragraph: length, transitions, opening patterns
    - Discourse: opening/closing patterns, memorable phrases
    - Pragmatic: argumentation style, reader relation
    """

    model_config = ConfigDict(strict=True)

    # Tone characteristics
    formality_score: float = Field(ge=0.0, le=1.0, description="正式程度 (0=口语, 1=正式)")
    emotional_tone: str = Field(description="主要情感基调")
    expertise_level: float = Field(ge=0.0, le=1.0, description="专业度投射")

    # Voice fingerprint
    writing_style: str = Field(description="主要写作风格")
    vocabulary_level: str = Field(description="词汇复杂度 (simple/moderate/complex)")
    sentence_complexity: float = Field(ge=0.0, le=1.0, description="句子复杂度")

    # Lexical features
    pronoun_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="代词使用比例")
    colloquialism_score: float = Field(default=0.0, ge=0.0, le=1.0, description="口语化程度")
    term_density: float = Field(default=0.0, ge=0.0, le=1.0, description="专业术语密度")

    # KOL-specific
    personal_brand_keywords: List[str] = Field(default_factory=list, description="个人品牌关键词")
    signature_phrases: List[str] = Field(default_factory=list, description="标志性表达")
    tone_consistency: float = Field(default=0.0, ge=0.0, le=1.0, description="语气一致性")


# Dimension 2: Rhetoric (修辞手法)
class RhetoricResult(BaseModel):
    """Rhetoric analysis - Literary devices detection."""

    model_config = ConfigDict(strict=True)

    # Metaphor types
    metaphor_count: int = Field(default=0, ge=0, description="隐喻数量")
    simile_count: int = Field(default=0, ge=0, description="明喻数量")
    personification_count: int = Field(default=0, ge=0, description="拟人数量")

    # Structural patterns
    parallelism_count: int = Field(default=0, ge=0, description="排比数量")
    antithesis_count: int = Field(default=0, ge=0, description="对比数量")
    repetition_count: int = Field(default=0, ge=0, description="重复数量")

    # Tone patterns
    rhetorical_question_count: int = Field(default=0, ge=0, description="反问数量")
    hyperbole_count: int = Field(default=0, ge=0, description="夸张数量")
    irony_count: int = Field(default=0, ge=0, description="反语数量")

    # Citations
    classical_citation_count: int = Field(default=0, ge=0, description="古文引用")
    famous_quote_count: int = Field(default=0, ge=0, description="名言引用")

    # Summary
    total_rhetoric_devices: int = Field(default=0, ge=0, description="修辞手法总数")
    rhetoric_density: float = Field(default=0.0, ge=0.0, le=1.0, description="修辞密度")


# Dimension 4: Content Structure (内容结构) - Argument quality
class ContentStructureResult(BaseModel):
    """Content structure analysis - Argument quality.

    Measures:
    - Overall structure pattern
    - Information density
    - Logic chains
    - Suspense and foreshadowing
    """

    model_config = ConfigDict(strict=True)

    # Overall structure
    structure_type: str = Field(description="结构类型 (pyramid/inverted/parallel/progressive/mixed)")
    section_count: int = Field(ge=0, description="段落数量")
    paragraph_count: int = Field(ge=0, description="段落数")

    # Argument quality
    has_clear_thesis: bool = Field(description="是否有明确论点")
    thesis_position: str = Field(default="", description="论点位置 (opening/middle/closing/scattered)")
    supporting_points: int = Field(default=0, ge=0, description="支撑论点数量")

    # Evidence quality
    evidence_types: List[str] = Field(default_factory=list, description="证据类型 (data/case/authority)")
    evidence_quality_score: float = Field(default=0.0, ge=0.0, le=1.0, description="证据质量分数")
    citation_count: int = Field(default=0, ge=0, description="引用数量")

    # Logical flow
    logical_flow_score: float = Field(default=0.0, ge=0.0, le=1.0, description="逻辑流畅度")
    coherence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="连贯性分数")
    transition_quality: float = Field(default=0.0, ge=0.0, le=1.0, description="过渡质量")

    # Information density
    information_density: float = Field(default=0.0, ge=0.0, le=1.0, description="信息密度")
    redundancy_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="冗余比例")

    # Sections breakdown
    sections: List[Dict[str, Any]] = Field(default_factory=list, description="段落结构详情")


# Dimension 5: Cognitive Pattern (认知模式)
class CognitivePatternResult(BaseModel):
    """Cognitive pattern analysis - Thinking mode detection."""

    model_config = ConfigDict(strict=True)

    # Thinking mode
    primary_thinking_mode: str = Field(description="主要思维模式 (inductive/deductive/analogical)")
    thinking_mode_distribution: Dict[str, float] = Field(
        default_factory=dict,
        description="思维模式分布",
    )

    # Abstraction level
    abstraction_level: str = Field(description="抽象程度 (concrete/mixed/abstract)")
    abstraction_shift_count: int = Field(default=0, ge=0, description="抽象层次转换次数")

    # Conceptual metaphors
    conceptual_metaphors: List[str] = Field(default_factory=list, description="概念隐喻")
    metaphor_consistency: float = Field(default=0.0, ge=0.0, le=1.0, description="隐喻一致性")


# Dimension 6: Rhythm (节奏韵律)
class RhythmResult(BaseModel):
    """Rhythm analysis - Phonology and flow."""

    model_config = ConfigDict(strict=True)

    # Phonology
    rhyme_patterns: List[str] = Field(default_factory=list, description="韵律模式")

    # Rhythm
    pause_pattern_score: float = Field(default=0.0, ge=0.0, le=1.0, description="停顿模式分数")
    long_short_alternation: float = Field(default=0.0, ge=0.0, le=1.0, description="长短句交替分数")

    # Flow
    fluency_score: float = Field(default=0.0, ge=0.0, le=1.0, description="流畅度")
    reading_speed_estimate: str = Field(default="medium", description="阅读速度估计 (fast/medium/slow)")

    # Sentence patterns
    avg_sentence_length: float = Field(default=0.0, ge=0, description="平均句长")
    sentence_length_variance: float = Field(default=0.0, ge=0, description="句长方差")


# Dimension 7: Narrative (叙事技巧)
class NarrativeResult(BaseModel):
    """Narrative techniques analysis."""

    model_config = ConfigDict(strict=True)

    # Perspective
    perspective: str = Field(description="叙事视角 (first_person/third_omniscient/third_limited)")

    # Time structure
    time_structure: str = Field(description="时间结构 (chronological/reverse/interleaved/montage)")

    # Ratios
    dialogue_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="对话比例")
    scene_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="场景描写比例")


# Dimension 8: Argumentation (论证策略) - Reasoning quality
class ArgumentationResult(BaseModel):
    """Argumentation strategy analysis - Reasoning quality.

    Measures:
    - Argument type and strength
    - Logical validity
    - Fallacy detection
    - Persuasion techniques
    """

    model_config = ConfigDict(strict=True)

    # Argument type
    primary_argument_type: str = Field(description="主要论证类型 (deductive/inductive/abductive)")
    argument_strength: float = Field(ge=0.0, le=1.0, description="论证强度")

    # Reasoning quality
    logical_validity: float = Field(default=0.0, ge=0.0, le=1.0, description="逻辑有效性")
    premise_clarity: float = Field(default=0.0, ge=0.0, le=1.0, description="前提清晰度")
    conclusion_support: float = Field(default=0.0, ge=0.0, le=1.0, description="结论支撑度")

    # Fallacies detection
    detected_fallacies: List[str] = Field(default_factory=list, description="检测到的逻辑谬误")
    fallacy_risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="谬误风险分数")

    # Persuasion techniques
    persuasion_techniques: List[str] = Field(default_factory=list, description="说服技巧")
    emotional_appeal_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="情感诉求比例")
    logical_appeal_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="逻辑诉求比例")

    # Counter-argument handling
    addresses_counterarguments: bool = Field(default=False, description="是否回应反方观点")
    counterargument_quality: float = Field(default=0.0, ge=0.0, le=1.0, description="反方观点回应质量")


# Dimension 9: Cultural Context (文化语境)
class CulturalContextResult(BaseModel):
    """Cultural context analysis."""

    model_config = ConfigDict(strict=True)

    cultural_references: List[str] = Field(default_factory=list, description="文化引用")
    era_references: List[str] = Field(default_factory=list, description="时代引用")
    regional_markers: List[str] = Field(default_factory=list, description="地域标记")


# Dimension 10: Audience Target (受众定位)
class AudienceTargetResult(BaseModel):
    """Audience targeting analysis."""

    model_config = ConfigDict(strict=True)

    expertise_level: str = Field(description="专业水平 (expert/general/novice)")
    assumed_knowledge: List[str] = Field(default_factory=list, description="假设已知概念")
    explanation_depth: str = Field(description="解释深度 (detailed/moderate/minimal)")


# Dimension 11: Special Requirements (特殊要求)
class SpecialRequirementsResult(BaseModel):
    """Special requirements detection."""

    model_config = ConfigDict(strict=True)

    detected_constraints: List[str] = Field(default_factory=list, description="检测到的约束")
    emphasis_priorities: List[str] = Field(default_factory=list, description="强调优先级")


# Dimension 12: Reader Engagement (读者互动)
class ReaderEngagementResult(BaseModel):
    """Reader engagement analysis."""

    model_config = ConfigDict(strict=True)

    direct_address_count: int = Field(default=0, ge=0, description="直接称呼次数")
    question_count: int = Field(default=0, ge=0, description="提问数量")
    question_frequency: float = Field(default=0.0, ge=0.0, le=1.0, description="提问频率")
    interaction_style: str = Field(description="互动风格 (conversational/guiding/challenging)")
    resonance_triggers: List[str] = Field(default_factory=list, description="共鸣触发点")


# Dimension 13: Multimodal (多模态特征)
class MultimodalResult(BaseModel):
    """Multimodal features analysis."""

    model_config = ConfigDict(strict=True)

    punctuation_style: str = Field(description="标点风格 (standard/casual/emphatic)")
    paragraph_spacing: str = Field(description="段落间距 (tight/medium/loose)")
    emoji_count: int = Field(default=0, ge=0, description="表情符号数量")
    internet_slang_count: int = Field(default=0, ge=0, description="网络用语数量")


# Dimension 14: Language Variation (语言变异)
class LanguageVariationResult(BaseModel):
    """Language variation analysis."""

    model_config = ConfigDict(strict=True)

    formality_shifts: int = Field(default=0, ge=0, description="正式程度转换次数")
    register_switches: List[str] = Field(default_factory=list, description="语体转换")
    multilingual_mix: List[str] = Field(default_factory=list, description="多语言混合")


# Request/Response models
class TextAnalysisRequest(BaseModel):
    """Request for text analysis."""

    model_config = ConfigDict(strict=True)

    text: str = Field(..., min_length=1, description="待分析文本")
    dimensions: Optional[List[AnalysisDimension]] = Field(
        default=None,
        description="分析维度（None = 全部）",
    )
    language: str = Field(default="zh", description="文本语言")
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="额外上下文（KOL 信息、主题等）",
    )


class TextAnalysisResult(BaseModel):
    """Complete text analysis result."""

    model_config = ConfigDict(strict=True)

    # Metadata
    text_length: int = Field(ge=0, description="文本长度")
    analysis_time: datetime = Field(default_factory=datetime.now, description="分析时间")
    dimensions_analyzed: List[AnalysisDimension] = Field(
        default_factory=list,
        description="已分析维度",
    )

    # Dimension results (all optional based on request)
    surface_style: Optional[SurfaceStyleResult] = None
    rhetoric: Optional[RhetoricResult] = None
    emotion_arc: Optional[Dict[str, Any]] = None  # Use existing EmotionArc
    content_structure: Optional[ContentStructureResult] = None
    cognitive_pattern: Optional[CognitivePatternResult] = None
    rhythm: Optional[RhythmResult] = None
    narrative: Optional[NarrativeResult] = None
    argumentation: Optional[ArgumentationResult] = None
    cultural_context: Optional[CulturalContextResult] = None
    audience_target: Optional[AudienceTargetResult] = None
    special_requirements: Optional[SpecialRequirementsResult] = None
    reader_engagement: Optional[ReaderEngagementResult] = None
    multimodal: Optional[MultimodalResult] = None
    language_variation: Optional[LanguageVariationResult] = None

    # Summary scores
    overall_quality_score: float = Field(ge=0.0, le=1.0, description="整体质量分数")
    kol_fingerprint: Optional[Dict[str, Any]] = Field(
        default=None,
        description="聚合 KOL 声音指纹",
    )


class DimensionInfo(BaseModel):
    """Information about an analysis dimension."""

    model_config = ConfigDict(strict=True)

    id: str = Field(description="维度 ID")
    name: str = Field(description="维度名称（中文）")
    name_en: str = Field(description="维度名称（英文）")
    priority: DimensionPriority = Field(description="优先级")
    description: str = Field(description="维度描述")


# Dimension metadata
DIMENSION_INFO: Dict[AnalysisDimension, DimensionInfo] = {
    AnalysisDimension.SURFACE_STYLE: DimensionInfo(
        id="surface_style",
        name="表层风格",
        name_en="Surface Style",
        priority=DimensionPriority.HIGH,
        description="KOL 声音指纹：代词比例、口语化程度、句子复杂度",
    ),
    AnalysisDimension.RHETORIC: DimensionInfo(
        id="rhetoric",
        name="修辞手法",
        name_en="Rhetoric",
        priority=DimensionPriority.MEDIUM,
        description="修辞密度：隐喻、排比、反问、夸张",
    ),
    AnalysisDimension.EMOTION_ARC: DimensionInfo(
        id="emotion_arc",
        name="情感曲线",
        name_en="Emotion Arc",
        priority=DimensionPriority.HIGH,
        description="情感分析：强度曲线、峰值检测、情感转换",
    ),
    AnalysisDimension.CONTENT_STRUCTURE: DimensionInfo(
        id="content_structure",
        name="内容结构",
        name_en="Content Structure",
        priority=DimensionPriority.HIGH,
        description="论证质量：结构模式、论点检测、证据质量",
    ),
    AnalysisDimension.COGNITIVE_PATTERN: DimensionInfo(
        id="cognitive_pattern",
        name="认知模式",
        name_en="Cognitive Pattern",
        priority=DimensionPriority.MEDIUM,
        description="思维模式：归纳/演绎/类比、抽象层次",
    ),
    AnalysisDimension.RHYTHM: DimensionInfo(
        id="rhythm",
        name="节奏韵律",
        name_en="Rhythm",
        priority=DimensionPriority.MEDIUM,
        description="节奏分析：停顿模式、长短句交替、流畅度",
    ),
    AnalysisDimension.NARRATIVE: DimensionInfo(
        id="narrative",
        name="叙事技巧",
        name_en="Narrative",
        priority=DimensionPriority.LOW,
        description="叙事分析：视角、时间结构、对话比例",
    ),
    AnalysisDimension.ARGUMENTATION: DimensionInfo(
        id="argumentation",
        name="论证策略",
        name_en="Argumentation",
        priority=DimensionPriority.HIGH,
        description="推理质量：论证类型、逻辑有效性、谬误检测",
    ),
    AnalysisDimension.CULTURAL_CONTEXT: DimensionInfo(
        id="cultural_context",
        name="文化语境",
        name_en="Cultural Context",
        priority=DimensionPriority.LOW,
        description="文化引用、时代标记、地域特征",
    ),
    AnalysisDimension.AUDIENCE_TARGET: DimensionInfo(
        id="audience_target",
        name="受众定位",
        name_en="Audience Target",
        priority=DimensionPriority.MEDIUM,
        description="受众分析：专业水平、解释深度",
    ),
    AnalysisDimension.SPECIAL_REQUIREMENTS: DimensionInfo(
        id="special_requirements",
        name="特殊要求",
        name_en="Special Requirements",
        priority=DimensionPriority.LOW,
        description="约束检测、强调优先级",
    ),
    AnalysisDimension.READER_ENGAGEMENT: DimensionInfo(
        id="reader_engagement",
        name="读者互动",
        name_en="Reader Engagement",
        priority=DimensionPriority.MEDIUM,
        description="互动分析：直接称呼、提问频率、共鸣触发",
    ),
    AnalysisDimension.MULTIMODAL: DimensionInfo(
        id="multimodal",
        name="多模态特征",
        name_en="Multimodal",
        priority=DimensionPriority.LOW,
        description="标点风格、表情符号、网络用语",
    ),
    AnalysisDimension.LANGUAGE_VARIATION: DimensionInfo(
        id="language_variation",
        name="语言变异",
        name_en="Language Variation",
        priority=DimensionPriority.LOW,
        description="正式度转换、语体切换、多语言混合",
    ),
}


def get_dimension_priority(dimension: AnalysisDimension) -> DimensionPriority:
    """Get priority for a dimension."""
    return DIMENSION_INFO[dimension].priority


def get_high_priority_dimensions() -> List[AnalysisDimension]:
    """Get all high priority dimensions."""
    return [
        dim
        for dim, info in DIMENSION_INFO.items()
        if info.priority == DimensionPriority.HIGH
    ]


def get_medium_priority_dimensions() -> List[AnalysisDimension]:
    """Get all medium priority dimensions."""
    return [
        dim
        for dim, info in DIMENSION_INFO.items()
        if info.priority == DimensionPriority.MEDIUM
    ]


def get_low_priority_dimensions() -> List[AnalysisDimension]:
    """Get all low priority dimensions."""
    return [
        dim
        for dim, info in DIMENSION_INFO.items()
        if info.priority == DimensionPriority.LOW
    ]
