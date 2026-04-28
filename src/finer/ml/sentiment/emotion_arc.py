"""Emotion Arc Analysis — 情感曲线分析模块.

参考 zhiziX 写作实验室的情感曲线建模体系，实现：
1. 段落级情感强度追踪（-1到1）
2. 情感高潮点/低谷点检测
3. 情感转折点识别
4. 情感变化频率和节奏分析
5. 多维度情感类型（喜/怒/哀/乐/恐惧/惊讶等）

学术基础：
- 系统功能语言学
- 情感分析研究
- 叙事学理论
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


# =============================================================================
# 情感类型定义
# =============================================================================

class EmotionType(str, Enum):
    """多维度情感类型.

    参考 Plutchik 情感轮理论，定义8种基本情感。
    """

    JOY = "joy"           # 喜悦
    TRUST = "trust"       # 信任
    FEAR = "fear"         # 恐惧
    SURPRISE = "surprise" # 惊讶
    SADNESS = "sadness"   # 悲伤
    DISGUST = "disgust"   # 厌恶
    ANGER = "anger"       # 愤怒
    ANTICIPATION = "anticipation"  # 期待

    # 投资领域特有情感
    BULLISH = "bullish"   # 看多/乐观
    BEARISH = "bearish"   # 看空/悲观
    NEUTRAL = "neutral"   # 中性
    UNCERTAIN = "uncertain"  # 不确定


class EmotionIntensity(str, Enum):
    """情感强度等级."""

    LOW = "low"           # 0-0.3
    MEDIUM = "medium"     # 0.3-0.6
    HIGH = "high"         # 0.6-1.0


class TransitionType(str, Enum):
    """情感转折类型."""

    SUDDEN = "sudden"     # 突变
    GRADUAL = "gradual"   # 渐变


# =============================================================================
# 情感词典
# =============================================================================

# 基本情感词典（中文）
EMOTION_LEXICON_CN: Dict[EmotionType, List[str]] = {
    EmotionType.JOY: [
        "开心", "高兴", "快乐", "幸福", "喜悦", "欣喜", "愉快", "欢乐",
        "满意", "欣慰", "兴奋", "激动", "振奋", "陶醉", "享受",
        "哈哈", "嘻嘻", "太好了", "棒极了", "太棒了",
    ],
    EmotionType.TRUST: [
        "信任", "相信", "信赖", "可靠", "放心", "安心", "踏实",
        "支持", "认同", "认可", "肯定", "确信", "坚信",
    ],
    EmotionType.FEAR: [
        "害怕", "恐惧", "担心", "担忧", "忧虑", "焦虑", "紧张",
        "恐慌", "惊恐", "惶恐", "不安", "忐忑", "提心吊胆",
        "风险", "危险", "危机", "威胁",
    ],
    EmotionType.SURPRISE: [
        "惊讶", "吃惊", "意外", "惊喜", "震惊", "惊奇", "诧异",
        "没想到", "出乎意料", "意想不到", "竟然", "居然",
    ],
    EmotionType.SADNESS: [
        "悲伤", "难过", "伤心", "痛苦", "忧伤", "哀愁", "悲痛",
        "失落", "沮丧", "绝望", "心碎", "凄凉", "悲凉",
        "遗憾", "惋惜", "可惜", "后悔",
    ],
    EmotionType.DISGUST: [
        "厌恶", "讨厌", "反感", "恶心", "憎恨", "厌烦", "嫌弃",
        "鄙视", "不屑", "看不惯", "受不了",
    ],
    EmotionType.ANGER: [
        "愤怒", "生气", "恼火", "气愤", "恼怒", "暴怒", "震怒",
        "不满", "抱怨", "责怪", "指责", "批评", "抨击",
    ],
    EmotionType.ANTICIPATION: [
        "期待", "盼望", "期望", "希望", "憧憬", "向往", "渴望",
        "目标", "计划", "准备", "即将", "未来",
    ],
    # 投资领域情感
    EmotionType.BULLISH: [
        "看多", "看好", "买入", "加仓", "做多", "持有", "增持",
        "上涨", "涨", "牛市", "利好", "机会", "突破", "新高",
        "推荐", "建议买入", "目标价", "低估", "价值",
    ],
    EmotionType.BEARISH: [
        "看空", "看淡", "卖出", "减仓", "做空", "清仓", "止损",
        "下跌", "跌", "熊市", "利空", "风险", "破位", "新低",
        "回避", "不建议", "高估", "泡沫",
    ],
}

# 英文情感词典
EMOTION_LEXICON_EN: Dict[EmotionType, List[str]] = {
    EmotionType.JOY: [
        "happy", "joy", "glad", "pleased", "delighted", "excited",
        "wonderful", "great", "amazing", "fantastic", "awesome",
    ],
    EmotionType.TRUST: [
        "trust", "believe", "confident", "reliable", "safe", "secure",
        "support", "agree", "approve", "certain",
    ],
    EmotionType.FEAR: [
        "fear", "afraid", "worried", "anxious", "nervous", "scared",
        "panic", "risk", "danger", "threat", "crisis",
    ],
    EmotionType.SURPRISE: [
        "surprise", "shocked", "amazed", "unexpected", "sudden",
        "unbelievable", "incredible", "surprisingly",
    ],
    EmotionType.SADNESS: [
        "sad", "sorry", "unhappy", "depressed", "disappointed",
        "regret", "loss", "miss", "grief", "sorrow",
    ],
    EmotionType.DISGUST: [
        "disgust", "hate", "dislike", "nasty", "terrible", "awful",
        "disapprove", "reject",
    ],
    EmotionType.ANGER: [
        "angry", "mad", "furious", "annoyed", "irritated", "upset",
        "blame", "criticize", "complain",
    ],
    EmotionType.ANTICIPATION: [
        "expect", "hope", "look forward", "anticipate", "await",
        "plan", "prepare", "future", "goal", "target",
    ],
    EmotionType.BULLISH: [
        "bullish", "buy", "long", "hold", "accumulate", "upgrade",
        "rally", "surge", "gain", "opportunity", "undervalued",
    ],
    EmotionType.BEARISH: [
        "bearish", "sell", "short", "reduce", "downgrade",
        "drop", "decline", "risk", "overvalued", "bubble",
    ],
}

# 情感强度修饰词
INTENSIFIERS: Dict[str, float] = {
    # 加强
    "非常": 1.5, "极其": 1.8, "特别": 1.5, "相当": 1.3,
    "很": 1.2, "真的": 1.3, "绝对": 1.8, "肯定": 1.5,
    "强烈": 1.6, "大幅": 1.5, "超级": 1.7,
    "very": 1.5, "extremely": 1.8, "highly": 1.6,
    "strongly": 1.6, "absolutely": 1.8,
    # 减弱
    "稍微": 0.7, "有点": 0.7, "可能": 0.8,
    "或许": 0.6, "大概": 0.7, "似乎": 0.6,
    "slightly": 0.7, "somewhat": 0.7, "maybe": 0.7,
}

# 否定词
NEGATION_WORDS: List[str] = [
    "不", "没", "无", "非", "别", "莫", "未", "勿",
    "not", "no", "never", "neither", "nor",
]


# =============================================================================
# 数据模型
# =============================================================================

class ParagraphEmotion(BaseModel):
    """段落情感分析结果."""

    model_config = ConfigDict(strict=True)

    paragraph_index: int = Field(description="段落索引")
    text: str = Field(description="段落文本")
    emotion_type: EmotionType = Field(description="主要情感类型")
    emotion_score: float = Field(ge=-1.0, le=1.0, description="情感分数 (-1到1)")
    intensity: float = Field(ge=0.0, le=1.0, description="情感强度 (0到1)")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")

    # 次要情感
    secondary_emotions: Dict[EmotionType, float] = Field(
        default_factory=dict,
        description="次要情感类型及其强度"
    )

    # 关键词
    keywords: List[str] = Field(default_factory=list, description="情感关键词")


class EmotionTransition(BaseModel):
    """情感转折点."""

    model_config = ConfigDict(strict=True)

    position: int = Field(description="转折点位置（段落索引）")
    from_emotion: EmotionType = Field(description="转折前情感")
    to_emotion: EmotionType = Field(description="转折后情感")
    transition_type: TransitionType = Field(description="转折类型（突变/渐变）")
    magnitude: float = Field(ge=0.0, le=1.0, description="转折幅度")


class EmotionPeak(BaseModel):
    """情感极值点."""

    model_config = ConfigDict(strict=True)

    position: int = Field(description="位置（段落索引）")
    emotion_type: EmotionType = Field(description="情感类型")
    score: float = Field(description="情感分数")
    is_high: bool = Field(description="是否为高潮点（True）或低谷点（False）")


class EmotionArc(BaseModel):
    """情感曲线 - 整篇文章的情感分析结果."""

    model_config = ConfigDict(strict=True)

    # 基本信息
    text_length: int = Field(description="文本长度")
    paragraph_count: int = Field(description="段落数量")

    # 段落级情感
    paragraph_emotions: List[ParagraphEmotion] = Field(
        default_factory=list,
        description="每个段落的情感分析结果"
    )

    # 整体情感
    overall_emotion: EmotionType = Field(description="整体主要情感")
    overall_score: float = Field(ge=-1.0, le=1.0, description="整体情感分数")
    emotion_distribution: Dict[EmotionType, float] = Field(
        default_factory=dict,
        description="各情感类型的分布比例"
    )

    # 情感曲线特征
    peaks: List[EmotionPeak] = Field(default_factory=list, description="情感极值点")
    transitions: List[EmotionTransition] = Field(default_factory=list, description="情感转折点")

    # 曲线统计
    variance: float = Field(ge=0.0, description="情感方差（波动程度）")
    change_frequency: int = Field(description="情感变化次数")
    dominant_pattern: str = Field(description="主导模式（平稳型/波动型/递增型/递减型）")

    # 情感节奏
    rhythm_score: float = Field(ge=0.0, le=1.0, description="情感节奏评分")


class EmotionArcAnalyzer:
    """情感曲线分析器.

    分析文本的情感变化轨迹，包括：
    1. 段落级情感追踪
    2. 情感高潮/低谷检测
    3. 情感转折点识别
    4. 情感变化频率分析
    5. 多维度情感类型识别

    Example:
        >>> analyzer = EmotionArcAnalyzer()
        >>> arc = analyzer.analyze("今天很开心。但是后来发生了意外...")
        >>> print(arc.overall_emotion)
        EmotionType.SADNESS
        >>> print(arc.peaks[0].is_high)
        True
    """

    def __init__(self) -> None:
        """初始化分析器."""
        self._build_lexicon_index()

    def _build_lexicon_index(self) -> None:
        """构建情感词典索引."""
        self._emotion_index_cn: Dict[str, EmotionType] = {}
        for emotion, words in EMOTION_LEXICON_CN.items():
            for word in words:
                self._emotion_index_cn[word] = emotion

        self._emotion_index_en: Dict[str, EmotionType] = {}
        for emotion, words in EMOTION_LEXICON_EN.items():
            for word in words:
                self._emotion_index_en[word.lower()] = emotion

    def analyze(self, text: str) -> EmotionArc:
        """分析文本的情感曲线.

        Args:
            text: 待分析文本

        Returns:
            EmotionArc: 情感曲线分析结果
        """
        # 分段
        paragraphs = self._split_paragraphs(text)

        # 分析每个段落的情感
        paragraph_emotions = []
        for i, para in enumerate(paragraphs):
            emotion = self._analyze_paragraph(para, i)
            paragraph_emotions.append(emotion)

        # 计算整体情感
        overall_emotion, overall_score, distribution = self._compute_overall(paragraph_emotions)

        # 检测极值点
        peaks = self._detect_peaks(paragraph_emotions)

        # 检测转折点
        transitions = self._detect_transitions(paragraph_emotions)

        # 计算曲线统计
        variance, change_freq, pattern = self._compute_statistics(paragraph_emotions)

        # 计算情感节奏
        rhythm_score = self._compute_rhythm(paragraph_emotions, transitions)

        return EmotionArc(
            text_length=len(text),
            paragraph_count=len(paragraphs),
            paragraph_emotions=paragraph_emotions,
            overall_emotion=overall_emotion,
            overall_score=overall_score,
            emotion_distribution=distribution,
            peaks=peaks,
            transitions=transitions,
            variance=variance,
            change_frequency=change_freq,
            dominant_pattern=pattern,
            rhythm_score=rhythm_score,
        )

    def _split_paragraphs(self, text: str) -> List[str]:
        """分割段落.

        按换行符分割，过滤空段落。
        """
        # 按换行符分割
        raw_paragraphs = re.split(r'\n+', text)
        # 过滤空段落并清理
        paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]
        # 如果没有分段，整个文本作为一个段落
        if not paragraphs:
            paragraphs = [text] if text.strip() else []
        return paragraphs

    def _analyze_paragraph(self, text: str, index: int) -> ParagraphEmotion:
        """分析单个段落的情感.

        Args:
            text: 段落文本
            index: 段落索引

        Returns:
            ParagraphEmotion: 段落情感分析结果
        """
        if not text.strip():
            return ParagraphEmotion(
                paragraph_index=index,
                text=text,
                emotion_type=EmotionType.NEUTRAL,
                emotion_score=0.0,
                intensity=0.0,
                confidence=0.5,
            )

        # 检测情感
        emotion_scores: Dict[EmotionType, float] = {}
        keywords: List[str] = []

        # 中文情感检测
        text_lower = text.lower()
        for word, emotion in self._emotion_index_cn.items():
            if word in text:
                # 检查否定
                if self._has_negation_before(text, word):
                    # 否定反转情感
                    opposite = self._get_opposite_emotion(emotion)
                    emotion_scores[opposite] = emotion_scores.get(opposite, 0) + 1
                else:
                    # 检查强度修饰
                    intensity = self._get_intensity_before(text, word)
                    emotion_scores[emotion] = emotion_scores.get(emotion, 0) + intensity
                keywords.append(word)

        # 英文情感检测
        for word, emotion in self._emotion_index_en.items():
            if word in text_lower:
                if self._has_negation_before(text_lower, word):
                    opposite = self._get_opposite_emotion(emotion)
                    emotion_scores[opposite] = emotion_scores.get(opposite, 0) + 1
                else:
                    intensity = self._get_intensity_before(text_lower, word)
                    emotion_scores[emotion] = emotion_scores.get(emotion, 0) + intensity
                keywords.append(word)

        # 确定主要情感
        if not emotion_scores:
            primary_emotion = EmotionType.NEUTRAL
            score = 0.0
            intensity = 0.0
            confidence = 0.3
        else:
            # 按分数排序
            sorted_emotions = sorted(emotion_scores.items(), key=lambda x: x[1], reverse=True)
            primary_emotion = sorted_emotions[0][0]

            # 计算分数 (-1到1)
            total_score = sum(emotion_scores.values())
            positive_emotions = {EmotionType.JOY, EmotionType.TRUST, EmotionType.BULLISH,
                               EmotionType.ANTICIPATION, EmotionType.SURPRISE}
            negative_emotions = {EmotionType.FEAR, EmotionType.SADNESS, EmotionType.DISGUST,
                               EmotionType.ANGER, EmotionType.BEARISH}

            pos_score = sum(v for k, v in emotion_scores.items() if k in positive_emotions)
            neg_score = sum(v for k, v in emotion_scores.items() if k in negative_emotions)

            if total_score > 0:
                score = (pos_score - neg_score) / total_score
            else:
                score = 0.0

            # 强度
            intensity = min(1.0, total_score / 5.0)

            # 置信度
            confidence = min(1.0, total_score / 3.0)

        # 构建次要情感字典
        secondary = {k: v for k, v in emotion_scores.items() if k != primary_emotion}

        return ParagraphEmotion(
            paragraph_index=index,
            text=text,
            emotion_type=primary_emotion,
            emotion_score=score,
            intensity=intensity,
            confidence=confidence,
            secondary_emotions=secondary,
            keywords=keywords[:10],
        )

    def _has_negation_before(self, text: str, word: str) -> bool:
        """检查关键词前是否有否定词."""
        idx = text.find(word)
        if idx <= 0:
            return False

        # 检查关键词前10个字符
        prefix = text[max(0, idx - 10):idx]

        for neg in NEGATION_WORDS:
            if neg in prefix:
                # 排除常见误报
                if neg == "非" and "非常" in prefix:
                    continue
                if neg == "未" and "未来" in prefix:
                    continue
                if neg == "无" and any(w in prefix for w in ["无数", "无论", "无所谓"]):
                    continue
                return True

        return False

    def _get_intensity_before(self, text: str, word: str) -> float:
        """获取关键词前的强度修饰."""
        idx = text.find(word)
        if idx <= 0:
            return 1.0

        prefix = text[max(0, idx - 15):idx]

        for modifier, multiplier in INTENSIFIERS.items():
            if modifier in prefix:
                return multiplier

        return 1.0

    def _get_opposite_emotion(self, emotion: EmotionType) -> EmotionType:
        """获取相反情感."""
        opposites = {
            EmotionType.JOY: EmotionType.SADNESS,
            EmotionType.SADNESS: EmotionType.JOY,
            EmotionType.TRUST: EmotionType.DISGUST,
            EmotionType.DISGUST: EmotionType.TRUST,
            EmotionType.FEAR: EmotionType.ANTICIPATION,
            EmotionType.ANTICIPATION: EmotionType.FEAR,
            EmotionType.SURPRISE: EmotionType.NEUTRAL,
            EmotionType.ANGER: EmotionType.TRUST,
            EmotionType.BULLISH: EmotionType.BEARISH,
            EmotionType.BEARISH: EmotionType.BULLISH,
        }
        return opposites.get(emotion, EmotionType.NEUTRAL)

    def _compute_overall(
        self,
        paragraph_emotions: List[ParagraphEmotion]
    ) -> Tuple[EmotionType, float, Dict[EmotionType, float]]:
        """计算整体情感."""
        if not paragraph_emotions:
            return EmotionType.NEUTRAL, 0.0, {}

        # 汇总所有情感分数
        emotion_totals: Dict[EmotionType, float] = {}
        for pe in paragraph_emotions:
            emotion_totals[pe.emotion_type] = emotion_totals.get(pe.emotion_type, 0) + pe.intensity
            for emo, score in pe.secondary_emotions.items():
                emotion_totals[emo] = emotion_totals.get(emo, 0) + score * 0.5

        # 计算分布
        total = sum(emotion_totals.values())
        distribution = {k: v / total for k, v in emotion_totals.items()} if total > 0 else {}

        # 确定主要情感
        if emotion_totals:
            primary = max(emotion_totals.items(), key=lambda x: x[1])
            overall_emotion = primary[0]
        else:
            overall_emotion = EmotionType.NEUTRAL

        # 计算整体分数
        scores = [pe.emotion_score for pe in paragraph_emotions]
        overall_score = sum(scores) / len(scores) if scores else 0.0

        return overall_emotion, overall_score, distribution

    def _detect_peaks(self, paragraph_emotions: List[ParagraphEmotion]) -> List[EmotionPeak]:
        """检测情感极值点."""
        if len(paragraph_emotions) < 2:
            return []

        peaks = []
        scores = [pe.emotion_score for pe in paragraph_emotions]

        for i, score in enumerate(scores):
            # 检查是否为局部极值
            is_peak = False
            is_high = False

            if i == 0:
                # 第一个段落
                if len(scores) > 1 and score > scores[1]:
                    is_peak = True
                    is_high = True
                elif len(scores) > 1 and score < scores[1]:
                    is_peak = True
                    is_high = False
            elif i == len(scores) - 1:
                # 最后一个段落
                if score > scores[i - 1]:
                    is_peak = True
                    is_high = True
                elif score < scores[i - 1]:
                    is_peak = True
                    is_high = False
            else:
                # 中间段落
                if score > scores[i - 1] and score > scores[i + 1]:
                    is_peak = True
                    is_high = True
                elif score < scores[i - 1] and score < scores[i + 1]:
                    is_peak = True
                    is_high = False

            if is_peak:
                peaks.append(EmotionPeak(
                    position=i,
                    emotion_type=paragraph_emotions[i].emotion_type,
                    score=score,
                    is_high=is_high,
                ))

        return peaks

    def _detect_transitions(self, paragraph_emotions: List[ParagraphEmotion]) -> List[EmotionTransition]:
        """检测情感转折点."""
        if len(paragraph_emotions) < 2:
            return []

        transitions = []

        for i in range(1, len(paragraph_emotions)):
            prev = paragraph_emotions[i - 1]
            curr = paragraph_emotions[i]

            # 检测情感类型变化
            if prev.emotion_type != curr.emotion_type:
                # 计算转折幅度
                magnitude = abs(curr.emotion_score - prev.emotion_score)

                # 判断转折类型
                # 如果分数变化大，认为是突变
                transition_type = TransitionType.SUDDEN if magnitude > 0.5 else TransitionType.GRADUAL

                transitions.append(EmotionTransition(
                    position=i,
                    from_emotion=prev.emotion_type,
                    to_emotion=curr.emotion_type,
                    transition_type=transition_type,
                    magnitude=min(1.0, magnitude),  # Clamp to [0, 1]
                ))

        return transitions

    def _compute_statistics(
        self,
        paragraph_emotions: List[ParagraphEmotion]
    ) -> Tuple[float, int, str]:
        """计算曲线统计."""
        if not paragraph_emotions:
            return 0.0, 0, "平稳型"

        scores = [pe.emotion_score for pe in paragraph_emotions]

        # 计算方差
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores) if len(scores) > 1 else 0.0

        # 计算变化次数
        change_count = 0
        for i in range(1, len(scores)):
            if scores[i] * scores[i - 1] < 0:  # 符号变化
                change_count += 1

        # 判断主导模式
        if variance < 0.1:
            pattern = "平稳型"
        elif change_count >= len(scores) / 2:
            pattern = "波动型"
        elif len(scores) > 1 and scores[-1] > scores[0] + 0.3:
            pattern = "递增型"
        elif len(scores) > 1 and scores[-1] < scores[0] - 0.3:
            pattern = "递减型"
        else:
            pattern = "混合型"

        return variance, change_count, pattern

    def _compute_rhythm(
        self,
        paragraph_emotions: List[ParagraphEmotion],
        transitions: List[EmotionTransition]
    ) -> float:
        """计算情感节奏评分.

        节奏评分基于：
        1. 情感变化的规律性
        2. 高潮低谷的分布
        3. 转折的自然程度
        """
        if len(paragraph_emotions) < 3:
            return 0.5

        # 计算变化间隔的方差（越小越规律）
        scores = [pe.emotion_score for pe in paragraph_emotions]
        changes = []
        for i in range(1, len(scores)):
            changes.append(abs(scores[i] - scores[i - 1]))

        if not changes:
            return 0.5

        # 变化越均匀，节奏越好
        mean_change = sum(changes) / len(changes)
        variance = sum((c - mean_change) ** 2 for c in changes) / len(changes)

        # 方差越小，节奏评分越高
        rhythm = max(0.0, min(1.0, 1.0 - variance))

        return rhythm


# =============================================================================
# 便捷函数
# =============================================================================

def analyze_emotion_arc(text: str) -> EmotionArc:
    """分析文本的情感曲线.

    Args:
        text: 待分析文本

    Returns:
        EmotionArc: 情感曲线分析结果

    Example:
        >>> arc = analyze_emotion_arc("今天很开心。但是后来发生了意外...")
        >>> print(arc.overall_emotion)
        >>> print(arc.dominant_pattern)
    """
    analyzer = EmotionArcAnalyzer()
    return analyzer.analyze(text)


def get_paragraph_emotions(text: str) -> List[ParagraphEmotion]:
    """获取段落级情感分析结果.

    Args:
        text: 待分析文本

    Returns:
        每个段落的情感分析结果列表
    """
    arc = analyze_emotion_arc(text)
    return arc.paragraph_emotions


def detect_emotion_transitions(text: str) -> List[EmotionTransition]:
    """检测情感转折点.

    Args:
        text: 待分析文本

    Returns:
        情感转折点列表
    """
    arc = analyze_emotion_arc(text)
    return arc.transitions
