"""Tests for Emotion Arc Analysis."""

import pytest

from finer.ml.sentiment.emotion_arc import (
    EmotionType,
    EmotionIntensity,
    TransitionType,
    ParagraphEmotion,
    EmotionTransition,
    EmotionPeak,
    EmotionArc,
    EmotionArcAnalyzer,
    analyze_emotion_arc,
    get_paragraph_emotions,
    detect_emotion_transitions,
)


class TestEmotionType:
    """Test EmotionType enum."""

    def test_emotion_types_exist(self):
        """Test all emotion types are defined."""
        assert EmotionType.JOY.value == "joy"
        assert EmotionType.TRUST.value == "trust"
        assert EmotionType.FEAR.value == "fear"
        assert EmotionType.SURPRISE.value == "surprise"
        assert EmotionType.SADNESS.value == "sadness"
        assert EmotionType.DISGUST.value == "disgust"
        assert EmotionType.ANGER.value == "anger"
        assert EmotionType.ANTICIPATION.value == "anticipation"
        assert EmotionType.BULLISH.value == "bullish"
        assert EmotionType.BEARISH.value == "bearish"
        assert EmotionType.NEUTRAL.value == "neutral"


class TestEmotionArcAnalyzer:
    """Test EmotionArcAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        return EmotionArcAnalyzer()

    def test_analyze_empty_text(self, analyzer):
        """Test analyzing empty text."""
        arc = analyzer.analyze("")
        assert arc.paragraph_count == 0
        assert arc.overall_emotion == EmotionType.NEUTRAL
        assert arc.overall_score == 0.0

    def test_analyze_single_paragraph(self, analyzer):
        """Test analyzing single paragraph."""
        text = "今天很开心，非常高兴"
        arc = analyzer.analyze(text)

        assert arc.paragraph_count == 1
        assert arc.overall_emotion == EmotionType.JOY
        assert arc.overall_score > 0

    def test_analyze_multiple_paragraphs(self, analyzer):
        """Test analyzing multiple paragraphs."""
        text = """
今天很开心。

但是后来发生了意外，很担心。

最后还是解决了，非常满意。
"""
        arc = analyzer.analyze(text)

        assert arc.paragraph_count == 3
        assert len(arc.paragraph_emotions) == 3

    def test_emotion_detection_joy(self, analyzer):
        """Test joy emotion detection."""
        text = "今天非常开心，太高兴了"
        arc = analyzer.analyze(text)

        assert arc.overall_emotion == EmotionType.JOY
        assert arc.overall_score > 0

    def test_emotion_detection_fear(self, analyzer):
        """Test fear emotion detection."""
        text = "我很担心，非常害怕"
        arc = analyzer.analyze(text)

        assert arc.overall_emotion == EmotionType.FEAR
        assert arc.overall_score < 0

    def test_emotion_detection_bullish(self, analyzer):
        """Test bullish emotion detection."""
        text = "NVDA看多，强烈推荐买入，目标价150"
        arc = analyzer.analyze(text)

        assert arc.overall_emotion == EmotionType.BULLISH
        assert arc.overall_score > 0

    def test_emotion_detection_bearish(self, analyzer):
        """Test bearish emotion detection."""
        text = "看空这只股票，建议卖出止损"
        arc = analyzer.analyze(text)

        assert arc.overall_emotion == EmotionType.BEARISH
        assert arc.overall_score < 0

    def test_peak_detection(self, analyzer):
        """Test emotion peak detection."""
        text = """
今天很开心。

但是突然发生了意外，非常担心。

最后解决了，又很开心。
"""
        arc = analyzer.analyze(text)

        # Should have at least one peak (high or low)
        assert len(arc.peaks) >= 1

    def test_transition_detection(self, analyzer):
        """Test emotion transition detection."""
        text = """
今天很开心。

但是突然发生了意外，非常担心。
"""
        arc = analyzer.analyze(text)

        # Should detect transition from joy to fear
        assert len(arc.transitions) >= 1

    def test_variance_calculation(self, analyzer):
        """Test variance calculation."""
        # Stable text
        stable_text = "今天天气不错。明天天气也不错。后天天气也不错。"
        stable_arc = analyzer.analyze(stable_text)

        # Variable text
        variable_text = "今天非常开心。但是突然很担心。最后又很开心。"
        variable_arc = analyzer.analyze(variable_text)

        # Variable text should have higher variance
        assert variable_arc.variance >= stable_arc.variance

    def test_pattern_detection(self, analyzer):
        """Test dominant pattern detection."""
        # Stable pattern
        stable_text = "今天天气不错。明天天气也不错。后天天气也不错。"
        stable_arc = analyzer.analyze(stable_text)
        assert stable_arc.dominant_pattern in ["平稳型", "混合型"]

    def test_negation_handling(self, analyzer):
        """Test negation handling."""
        # Without negation
        text1 = "我很开心"
        arc1 = analyzer.analyze(text1)

        # With negation
        text2 = "我不开心"
        arc2 = analyzer.analyze(text2)

        # Negation should change the emotion
        assert arc1.overall_emotion != arc2.overall_emotion or arc1.overall_score != arc2.overall_score

    def test_intensity_modifiers(self, analyzer):
        """Test intensity modifiers."""
        # Normal intensity
        text1 = "我开心"
        arc1 = analyzer.analyze(text1)

        # High intensity
        text2 = "我非常开心"
        arc2 = analyzer.analyze(text2)

        # Both should be joy, but intensity may differ
        assert arc1.overall_emotion == EmotionType.JOY
        assert arc2.overall_emotion == EmotionType.JOY

    def test_mixed_language(self, analyzer):
        """Test mixed Chinese-English text."""
        text = "I am very happy 今天很开心"
        arc = analyzer.analyze(text)

        assert arc.overall_emotion == EmotionType.JOY


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_analyze_emotion_arc(self):
        """Test analyze_emotion_arc function."""
        text = "今天很开心"
        arc = analyze_emotion_arc(text)

        assert isinstance(arc, EmotionArc)
        assert arc.overall_emotion == EmotionType.JOY

    def test_get_paragraph_emotions(self):
        """Test get_paragraph_emotions function."""
        text = "今天很开心。\n\n但是后来很担心。"
        emotions = get_paragraph_emotions(text)

        assert len(emotions) == 2
        assert all(isinstance(e, ParagraphEmotion) for e in emotions)

    def test_detect_emotion_transitions(self):
        """Test detect_emotion_transitions function."""
        text = "今天很开心。\n\n但是后来很担心。"
        transitions = detect_emotion_transitions(text)

        assert isinstance(transitions, list)
        assert all(isinstance(t, EmotionTransition) for t in transitions)


class TestEmotionArcModels:
    """Test Pydantic models."""

    def test_paragraph_emotion_validation(self):
        """Test ParagraphEmotion validation."""
        emotion = ParagraphEmotion(
            paragraph_index=0,
            text="test",
            emotion_type=EmotionType.JOY,
            emotion_score=0.8,
            intensity=0.7,
            confidence=0.9,
        )
        assert emotion.emotion_score == 0.8

        # Invalid score
        with pytest.raises(Exception):
            ParagraphEmotion(
                paragraph_index=0,
                text="test",
                emotion_type=EmotionType.JOY,
                emotion_score=2.0,  # Invalid
                intensity=0.7,
                confidence=0.9,
            )

    def test_emotion_transition_validation(self):
        """Test EmotionTransition validation."""
        transition = EmotionTransition(
            position=1,
            from_emotion=EmotionType.JOY,
            to_emotion=EmotionType.FEAR,
            transition_type=TransitionType.SUDDEN,
            magnitude=0.8,
        )
        assert transition.magnitude == 0.8

    def test_emotion_peak_validation(self):
        """Test EmotionPeak validation."""
        peak = EmotionPeak(
            position=0,
            emotion_type=EmotionType.JOY,
            score=0.9,
            is_high=True,
        )
        assert peak.is_high is True

    def test_emotion_arc_validation(self):
        """Test EmotionArc validation."""
        arc = EmotionArc(
            text_length=100,
            paragraph_count=2,
            overall_emotion=EmotionType.JOY,
            overall_score=0.5,
            variance=0.2,
            change_frequency=1,
            dominant_pattern="波动型",
            rhythm_score=0.7,
        )
        assert arc.overall_emotion == EmotionType.JOY


class TestIntegration:
    """Integration tests."""

    def test_full_analysis_workflow(self):
        """Test complete analysis workflow."""
        text = """
今天市场大涨，我非常开心，持有的股票都涨了。

但是下午突然传来利空消息，让我很担心。

NVDA看多，目标价150，强烈推荐买入。

不过风险也不小，大家要谨慎。

总的来说，这次机会难得，值得把握。
"""
        arc = analyze_emotion_arc(text)

        # Basic checks
        assert arc.paragraph_count == 5
        assert arc.text_length > 0

        # Emotion checks
        assert arc.overall_emotion in [EmotionType.BULLISH, EmotionType.JOY, EmotionType.ANTICIPATION]

        # Curve checks
        assert 0 <= arc.variance <= 1
        assert arc.change_frequency >= 0
        assert 0 <= arc.rhythm_score <= 1

        # Distribution check
        assert len(arc.emotion_distribution) > 0
        assert abs(sum(arc.emotion_distribution.values()) - 1.0) < 0.01  # Should sum to ~1

    def test_investment_content_analysis(self):
        """Test investment content analysis."""
        text = """
强烈看好NVDA，建议买入。

风险提示：市场波动较大，注意止损。

综合来看，长期价值投资为主。
"""
        arc = analyze_emotion_arc(text)

        # Should detect bullish sentiment
        assert EmotionType.BULLISH in arc.emotion_distribution

        # Should have some variance (mixed emotions)
        assert arc.variance > 0
