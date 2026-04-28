"""Tests for KOL Scorer."""

import pytest
import numpy as np
from datetime import datetime

from finer.ml.kol_scorer import (
    ScorerConfig,
    KOLScorer,
    DimensionScore,
    DimensionScores,
    compute_kol_score,
    # Task-specified exports
    DimensionWeights,
    DimensionScoresV2,
    ScoringExplanation,
    KOLScoreResult,
    KOLScorerV2,
)


class TestScorerConfig:
    """Test ScorerConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = ScorerConfig()
        assert config.accuracy_weight == 0.30
        assert config.timeliness_weight == 0.15
        assert config.return_weight == 0.30
        assert config.consistency_weight == 0.15
        assert config.depth_weight == 0.10

    def test_weights_sum_to_one(self):
        """Test weights validation."""
        config = ScorerConfig()
        total = (
            config.accuracy_weight +
            config.timeliness_weight +
            config.return_weight +
            config.consistency_weight +
            config.depth_weight
        )
        assert abs(total - 1.0) < 0.01

    def test_custom_config(self):
        """Test custom configuration."""
        config = ScorerConfig(
            accuracy_weight=0.40,
            timeliness_weight=0.10,
            return_weight=0.35,
            consistency_weight=0.10,
            depth_weight=0.05,
        )
        assert config.accuracy_weight == 0.40


class TestDimensionScore:
    """Test DimensionScore model."""

    def test_create_dimension_score(self):
        """Test creating a dimension score."""
        score = DimensionScore(
            dimension="accuracy",
            raw_score=4.0,
            weighted_score=1.2,
            weight=0.30,
            contribution=1.2,
            explanation="Test explanation",
        )
        assert score.dimension == "accuracy"
        assert score.raw_score == 4.0
        assert score.weight == 0.30


class TestKOLScorer:
    """Test KOLScorer."""

    @pytest.fixture
    def sample_trades(self):
        """Create sample trade data."""
        return [
            {"return_pct": 0.15, "holding_days": 5, "direction": "long"},
            {"return_pct": -0.05, "holding_days": 10, "direction": "long"},
            {"return_pct": 0.10, "holding_days": 3, "direction": "short"},
            {"return_pct": 0.08, "holding_days": 7, "direction": "long"},
            {"return_pct": -0.03, "holding_days": 15, "direction": "long"},
        ]

    @pytest.fixture
    def sample_opinions(self):
        """Create sample opinion data."""
        return [
            {"timestamp": "2024-01-01", "ticker": "AAPL", "confidence": 0.8, "rationale": "Strong fundamentals"},
            {"timestamp": "2024-01-15", "ticker": "TSLA", "confidence": 0.9, "rationale": "Technical breakout"},
        ]

    def test_compute_scores(self, sample_trades, sample_opinions):
        """Test computing full scores."""
        scorer = KOLScorer()
        scores = scorer.compute_scores(
            kol_id="kol_001",
            trades=sample_trades,
            opinions=sample_opinions,
        )

        assert scores.kol_id == "kol_001"
        assert isinstance(scores.accuracy, DimensionScore)
        assert isinstance(scores.timeliness, DimensionScore)
        assert isinstance(scores.return_score, DimensionScore)
        assert isinstance(scores.consistency, DimensionScore)
        assert isinstance(scores.depth, DimensionScore)
        assert 0 <= scores.overall <= 5.0

    def test_accuracy_calculation(self, sample_trades):
        """Test accuracy dimension calculation."""
        scorer = KOLScorer()
        scores = scorer.compute_scores("kol_001", sample_trades)

        # 3 out of 5 trades are positive
        expected_accuracy = 3 / 5 * 5.0
        assert abs(scores.accuracy.raw_score - expected_accuracy) < 1.0

    def test_return_calculation(self, sample_trades):
        """Test return dimension calculation."""
        scorer = KOLScorer()
        scores = scorer.compute_scores("kol_001", sample_trades)

        # Average return is positive
        avg_return = np.mean([t["return_pct"] for t in sample_trades])
        assert scores.return_score.metrics["avg_return_pct"] > 0

    def test_empty_trades(self):
        """Test scoring with no trades."""
        scorer = KOLScorer()
        scores = scorer.compute_scores("kol_001", [])

        # Should use neutral score
        assert scores.accuracy.raw_score == 2.5
        assert scores.timeliness.raw_score == 2.5
        assert scores.return_score.raw_score == 2.5
        assert scores.overall == 2.5

    def test_explain(self, sample_trades):
        """Test explainability."""
        scorer = KOLScorer()
        scores = scorer.compute_scores("kol_001", sample_trades)
        explanation = scorer.explain(scores)

        assert explanation["kol_id"] == "kol_001"
        assert "overall_score" in explanation
        assert "dimensions" in explanation
        assert "accuracy" in explanation["dimensions"]

    def test_rank_kols(self, sample_trades):
        """Test KOL ranking."""
        scorer = KOLScorer()

        kol_data = {
            "kol_001": {"trades": sample_trades[:3]},
            "kol_002": {"trades": sample_trades},
            "kol_003": {"trades": sample_trades[:1]},
        }

        ranked = scorer.rank_kols(kol_data)

        assert len(ranked) == 3
        assert ranked[0][0]  # KOL ID
        assert ranked[0][1]  # Score
        assert isinstance(ranked[0][2], DimensionScores)

        # Check sorted order
        scores_list = [r[1] for r in ranked]
        assert scores_list == sorted(scores_list, reverse=True)

    def test_dimension_ranking(self, sample_trades):
        """Test ranking by specific dimension."""
        scorer = KOLScorer()

        kol_data = {
            "kol_001": {"trades": sample_trades},
        }

        ranked = scorer.rank_kols(kol_data, dimension="accuracy")
        assert ranked[0][1] == ranked[0][2].accuracy.raw_score


class TestComputeKolScore:
    """Test convenience function."""

    def test_compute_kol_score(self):
        """Test compute_kol_score wrapper."""
        trades = [
            {"return_pct": 0.10, "holding_days": 5},
            {"return_pct": -0.05, "holding_days": 10},
        ]

        scores = compute_kol_score("kol_001", trades)
        assert scores.kol_id == "kol_001"
        assert isinstance(scores, DimensionScores)


# =============================================================================
# Task-Specified Tests (KOLScorerV2)
# =============================================================================

class TestDimensionWeights:
    """Tests for DimensionWeights schema."""

    def test_dimension_weights_defaults(self):
        """Test default weight values."""
        weights = DimensionWeights()
        assert weights.accuracy == 0.30
        assert weights.timeliness == 0.20
        assert weights.return_score == 0.30
        assert weights.consistency == 0.20

    def test_dimension_weights_custom(self):
        """Test custom weight values."""
        weights = DimensionWeights(
            accuracy=0.40,
            timeliness=0.10,
            return_score=0.35,
            consistency=0.15,
        )
        assert weights.accuracy == 0.40
        assert weights.timeliness == 0.10
        assert weights.return_score == 0.35
        assert weights.consistency == 0.15

    def test_dimension_weights_validation(self):
        """Test Pydantic validation."""
        # Valid range (weights are not constrained to 0-1)
        weights = DimensionWeights(accuracy=0.5, timeliness=0.5, return_score=0.0, consistency=0.0)
        assert weights.accuracy == 0.5

        # Invalid: score out of range (DimensionScoresV2 has ge=1, le=5)
        with pytest.raises(Exception):  # ValidationError
            DimensionScoresV2(accuracy=6.0)  # Out of range


class TestKOLScorerV2:
    """Tests for task-specified KOLScorerV2."""

    @pytest.fixture
    def scorer(self):
        """Create a scorer instance."""
        return KOLScorerV2()

    @pytest.fixture
    def sample_actions(self):
        """Sample TradeAction data."""
        return [
            {"ticker": "AAPL", "direction": "long", "return_pct": 0.15, "holding_days": 5, "is_correct": True},
            {"ticker": "GOOGL", "direction": "long", "return_pct": 0.08, "holding_days": 7, "is_correct": True},
            {"ticker": "MSFT", "direction": "short", "return_pct": -0.05, "holding_days": 3, "is_correct": False},
            {"ticker": "TSLA", "direction": "long", "return_pct": 0.22, "holding_days": 10, "is_correct": True},
            {"ticker": "NVDA", "direction": "long", "return_pct": 0.18, "holding_days": 6, "is_correct": True},
        ]

    @pytest.fixture
    def sample_backtest_results(self):
        """Sample backtest results."""
        return [
            {"annualized_return": 0.35, "return_pct": 0.15},
            {"annualized_return": 0.20, "return_pct": 0.08},
            {"annualized_return": -0.10, "return_pct": -0.05},
            {"annualized_return": 0.45, "return_pct": 0.22},
            {"annualized_return": 0.30, "return_pct": 0.18},
        ]

    def test_compute_accuracy_score_high(self, scorer, sample_actions):
        """Test accuracy score with high accuracy."""
        # All correct
        actions_all_correct = [
            {"return_pct": 0.10, "is_correct": True},
            {"return_pct": 0.15, "is_correct": True},
            {"return_pct": 0.20, "is_correct": True},
            {"return_pct": 0.05, "is_correct": True},
            {"return_pct": 0.08, "is_correct": True},
        ]
        score = scorer.compute_accuracy_score(actions_all_correct)
        assert score == 5.0  # 100% accuracy

    def test_compute_accuracy_score_low(self, scorer):
        """Test accuracy score with low accuracy."""
        # Most incorrect
        actions_low_accuracy = [
            {"return_pct": -0.10, "is_correct": False},
            {"return_pct": -0.15, "is_correct": False},
            {"return_pct": -0.20, "is_correct": False},
            {"return_pct": 0.05, "is_correct": True},
            {"return_pct": -0.08, "is_correct": False},
        ]
        score = scorer.compute_accuracy_score(actions_low_accuracy)
        assert score == 1.0  # 20% accuracy

    def test_compute_accuracy_score_medium(self, scorer):
        """Test accuracy score with medium accuracy."""
        # 70% accuracy (boundary for 5.0)
        actions_medium = [
            {"return_pct": 0.10, "is_correct": True},
            {"return_pct": 0.15, "is_correct": True},
            {"return_pct": -0.20, "is_correct": False},
            {"return_pct": 0.05, "is_correct": True},
            {"return_pct": 0.08, "is_correct": True},  # 4/5 = 80% > 70% -> 5.0
        ]
        score = scorer.compute_accuracy_score(actions_medium)
        assert score == 5.0  # 80% accuracy > 70% threshold

    def test_compute_accuracy_score_empty(self, scorer):
        """Test accuracy score with no data."""
        score = scorer.compute_accuracy_score([])
        assert score == 3.0  # Neutral score

    def test_compute_timeliness_score(self, scorer):
        """Test timeliness score calculation."""
        # Very timely: lead > 5 days
        actions_timely = [
            {"lead_days": 7, "holding_days": 3},
            {"lead_days": 10, "holding_days": 2},
            {"lead_days": 8, "holding_days": 4},
        ]
        score = scorer.compute_timeliness_score(actions_timely)
        assert score == 5.0

        # Somewhat timely: lead 3-5 days
        actions_moderate = [
            {"lead_days": 4, "holding_days": 6},
            {"lead_days": 3, "holding_days": 7},
        ]
        score = scorer.compute_timeliness_score(actions_moderate)
        assert score == 4.0

        # Not timely: lead < 1 day
        actions_late = [
            {"lead_days": 0, "holding_days": 10},
            {"lead_days": -1, "holding_days": 12},
        ]
        score = scorer.compute_timeliness_score(actions_late)
        assert score == 1.0

    def test_compute_return_score(self, scorer, sample_backtest_results):
        """Test return score calculation."""
        # High return: > 30%
        score = scorer.compute_return_score(sample_backtest_results)
        # Average annualized return is 24%, so should be 4.0
        assert 3.0 <= score <= 5.0

    def test_compute_return_score_high(self, scorer):
        """Test return score with high returns."""
        results = [
            {"annualized_return": 0.50},
            {"annualized_return": 0.45},
            {"annualized_return": 0.55},
        ]
        score = scorer.compute_return_score(results)
        assert score == 5.0  # > 30%

    def test_compute_return_score_negative(self, scorer):
        """Test return score with negative returns."""
        results = [
            {"annualized_return": -0.10},
            {"annualized_return": -0.15},
            {"annualized_return": -0.05},
        ]
        score = scorer.compute_return_score(results)
        assert score == 1.0  # < 0%

    def test_compute_consistency_score(self, scorer):
        """Test consistency score calculation."""
        # Consistent actions: same direction for same ticker
        actions_consistent = [
            {"ticker": "AAPL", "direction": "long", "return_pct": 0.10},
            {"ticker": "AAPL", "direction": "long", "return_pct": 0.12},
            {"ticker": "AAPL", "direction": "long", "return_pct": 0.08},
            {"ticker": "GOOGL", "direction": "short", "return_pct": -0.05},
        ]
        score = scorer.compute_consistency_score(actions_consistent)
        assert score >= 4.0  # High consistency

    def test_compute_consistency_score_inconsistent(self, scorer):
        """Test consistency score with inconsistent actions."""
        # Inconsistent: flipping directions
        actions_inconsistent = [
            {"ticker": "AAPL", "direction": "long", "return_pct": 0.10},
            {"ticker": "AAPL", "direction": "short", "return_pct": -0.05},
            {"ticker": "AAPL", "direction": "long", "return_pct": 0.08},
            {"ticker": "AAPL", "direction": "short", "return_pct": -0.10},
        ]
        score = scorer.compute_consistency_score(actions_inconsistent)
        assert score <= 3.0  # Low consistency

    def test_compute_overall(self, scorer):
        """Test overall score calculation."""
        dimension_scores = DimensionScoresV2(
            accuracy=4.0,
            timeliness=3.0,
            return_score=5.0,
            consistency=4.0,
        )
        overall = scorer.compute_overall(dimension_scores)
        # Weighted average: 4*0.3 + 3*0.2 + 5*0.3 + 4*0.2 = 4.1
        assert 4.0 <= overall <= 4.3

    def test_compute_scores_full(self, scorer, sample_actions, sample_backtest_results):
        """Test full score computation."""
        result = scorer.compute_scores(
            kol_id="kol_001",
            actions=sample_actions,
            backtest_results=sample_backtest_results,
        )

        assert result.kol_id == "kol_001"
        assert 1.0 <= result.overall_score <= 5.0
        assert 1.0 <= result.dimension_scores.accuracy <= 5.0
        assert 1.0 <= result.dimension_scores.timeliness <= 5.0
        assert 1.0 <= result.dimension_scores.return_score <= 5.0
        assert 1.0 <= result.dimension_scores.consistency <= 5.0
        assert len(result.explanations) == 4
        assert result.sample_size == 5
        assert 0 <= result.confidence <= 1.0

    def test_explain(self, scorer, sample_actions, sample_backtest_results):
        """Test explanation generation."""
        result = scorer.compute_scores(
            kol_id="kol_001",
            actions=sample_actions,
            backtest_results=sample_backtest_results,
        )
        explanation = scorer.explain("kol_001", result)

        assert explanation["kol_id"] == "kol_001"
        assert "overall_score" in explanation
        assert "dimensions" in explanation
        assert "weights" in explanation
        assert "methodology" in explanation

    def test_custom_weights(self):
        """Test scorer with custom weights."""
        weights = DimensionWeights(
            accuracy=0.40,
            timeliness=0.10,
            return_score=0.35,
            consistency=0.15,
        )
        scorer = KOLScorerV2(weights=weights)

        dimension_scores = DimensionScoresV2(
            accuracy=5.0,
            timeliness=3.0,
            return_score=4.0,
            consistency=2.0,
        )
        overall = scorer.compute_overall(dimension_scores)
        # 5*0.4 + 3*0.1 + 4*0.35 + 2*0.15 = 4.0
        assert 3.9 <= overall <= 4.1

    def test_empty_actions(self, scorer):
        """Test scorer with no actions."""
        result = scorer.compute_scores("kol_empty", [])

        assert result.kol_id == "kol_empty"
        assert result.sample_size == 0
        assert result.confidence == 0.0
        # Neutral scores
        assert result.dimension_scores.accuracy == 3.0


class TestSchemas:
    """Tests for Pydantic schemas."""

    def test_dimension_scores_v2_validation(self):
        """Test DimensionScoresV2 validation."""
        # Valid
        scores = DimensionScoresV2(
            accuracy=4.5,
            timeliness=3.0,
            return_score=5.0,
            consistency=2.5,
        )
        assert scores.accuracy == 4.5

        # Invalid: out of range
        with pytest.raises(Exception):  # ValidationError
            DimensionScoresV2(accuracy=6.0)

    def test_kol_score_result_validation(self):
        """Test KOLScoreResult validation."""
        # Valid
        result = KOLScoreResult(
            kol_id="test_kol",
            overall_score=4.2,
            dimension_scores=DimensionScoresV2(
                accuracy=4.0,
                timeliness=3.5,
                return_score=5.0,
                consistency=4.0,
            ),
            explanations=[],
            confidence=0.85,
            sample_size=10,
            last_updated="2024-01-01T00:00:00",
        )
        assert result.kol_id == "test_kol"

        # Invalid: confidence out of range
        with pytest.raises(Exception):  # ValidationError
            KOLScoreResult(
                kol_id="test_kol",
                overall_score=4.2,
                dimension_scores=DimensionScoresV2(
                    accuracy=4.0,
                    timeliness=3.5,
                    return_score=5.0,
                    consistency=4.0,
                ),
                explanations=[],
                confidence=1.5,  # Invalid
                sample_size=10,
                last_updated="2024-01-01T00:00:00",
            )

    def test_scoring_explanation(self):
        """Test ScoringExplanation schema."""
        explanation = ScoringExplanation(
            dimension="accuracy",
            score=4.5,
            factors=["方向准确率", "预测与实际对比"],
            evidence=["正确预测: 8/10"],
        )
        assert explanation.dimension == "accuracy"
        assert len(explanation.factors) == 2
        assert len(explanation.evidence) == 1


class TestIntegration:
    """Integration tests."""

    def test_full_scoring_workflow(self):
        """Test complete scoring workflow."""
        # Create scorer
        weights = DimensionWeights(
            accuracy=0.30,
            timeliness=0.20,
            return_score=0.30,
            consistency=0.20,
        )
        scorer = KOLScorerV2(weights=weights)

        # Prepare data
        actions = [
            {"ticker": "AAPL", "direction": "long", "return_pct": 0.15, "holding_days": 5, "is_correct": True, "lead_days": 6},
            {"ticker": "GOOGL", "direction": "long", "return_pct": 0.08, "holding_days": 7, "is_correct": True, "lead_days": 4},
            {"ticker": "MSFT", "direction": "short", "return_pct": -0.05, "holding_days": 3, "is_correct": False, "lead_days": 1},
            {"ticker": "TSLA", "direction": "long", "return_pct": 0.22, "holding_days": 10, "is_correct": True, "lead_days": 8},
            {"ticker": "NVDA", "direction": "long", "return_pct": 0.18, "holding_days": 6, "is_correct": True, "lead_days": 5},
        ]

        backtest_results = [
            {"annualized_return": 0.35, "return_pct": 0.15},
            {"annualized_return": 0.20, "return_pct": 0.08},
            {"annualized_return": -0.10, "return_pct": -0.05},
            {"annualized_return": 0.45, "return_pct": 0.22},
            {"annualized_return": 0.30, "return_pct": 0.18},
        ]

        # Compute scores
        result = scorer.compute_scores(
            kol_id="kol_test",
            actions=actions,
            backtest_results=backtest_results,
        )

        # Verify
        assert result.kol_id == "kol_test"
        assert 1.0 <= result.overall_score <= 5.0
        assert len(result.explanations) == 4

        # Get explanation
        explanation = scorer.explain("kol_test", result)
        assert "dimensions" in explanation
        assert "weights" in explanation

    def test_import_from_ml_module(self):
        """Test importing from finer.ml module."""
        from finer.ml import (
            KOLScorer,
            KOLScorerV2,
            DimensionWeights,
            KOLScoreResult,
            DimensionScoresV2,
            ScorerConfig,
        )

        # Should not raise
        scorer_v1 = KOLScorer()
        scorer_v2 = KOLScorerV2()
        weights = DimensionWeights()

        assert scorer_v1 is not None
        assert scorer_v2 is not None
        assert weights.accuracy == 0.30