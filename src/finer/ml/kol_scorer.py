"""KOL Scorer — Multi-dimensional KOL performance scoring.

This module provides:
1. Multi-dimensional KOL scoring (accuracy, timeliness, return, consistency)
2. Explainable scoring with contribution breakdown
3. Temporal decay for recent performance emphasis
4. Peer ranking and comparison

Key Design Decisions:
- Scores are on 1-5 scale (matching frontend)
- Each dimension has clear metrics and formulas
- Weights are configurable via YAML
- Explainability is built-in (not post-hoc)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yaml
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


# =============================================================================
# Task-Specified Schemas (for API compatibility)
# =============================================================================

class DimensionWeights(BaseModel):
    """评分维度权重."""
    model_config = ConfigDict(strict=True)

    accuracy: float = 0.30
    timeliness: float = 0.20
    return_score: float = 0.30
    consistency: float = 0.20


class ScoringExplanation(BaseModel):
    """评分解释."""
    model_config = ConfigDict(strict=True)

    dimension: str
    score: float
    factors: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)


class KOLScoreResult(BaseModel):
    """KOL 评分结果."""
    model_config = ConfigDict(strict=True)

    kol_id: str
    overall_score: float = Field(ge=1, le=5)
    dimension_scores: "DimensionScoresV2"
    explanations: List[ScoringExplanation]
    confidence: float = Field(ge=0, le=1, description="评分置信度")
    sample_size: int = Field(description="评估样本量")
    last_updated: str


class DimensionScoresV2(BaseModel):
    """各维度评分 (1-5)."""
    model_config = ConfigDict(strict=True)

    accuracy: float = Field(ge=1, le=5, description="准确率评分")
    timeliness: float = Field(ge=1, le=5, description="时效性评分")
    return_score: float = Field(ge=1, le=5, description="收益率评分")
    consistency: float = Field(ge=1, le=5, description="一致性评分")


# =============================================================================
# Score Dimensions (Legacy - for backward compatibility)
# =============================================================================

class DimensionScore(BaseModel):
    """Score for a single dimension."""
    model_config = ConfigDict(strict=True)

    dimension: str = Field(..., description="Dimension name")
    raw_score: float = Field(..., ge=0.0, le=5.0, description="Raw score (0-5)")
    weighted_score: float = Field(..., ge=0.0, le=5.0, description="Weighted score")
    weight: float = Field(..., ge=0.0, le=1.0, description="Dimension weight")
    contribution: float = Field(..., description="Contribution to overall score")

    # Metrics used for this dimension
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Metrics that contributed to this score"
    )

    # Explainability
    explanation: str = Field("", description="Human-readable explanation")


class DimensionScores(BaseModel):
    """All dimension scores for a KOL."""
    model_config = ConfigDict(strict=True)

    accuracy: DimensionScore = Field(..., description="Prediction accuracy score")
    timeliness: DimensionScore = Field(..., description="Timeliness score")
    return_score: DimensionScore = Field(..., description="Return performance score")
    consistency: DimensionScore = Field(..., description="Consistency score")
    depth: DimensionScore = Field(..., description="Analysis depth score")

    overall: float = Field(..., ge=0.0, le=5.0, description="Weighted overall score")

    # Metadata
    kol_id: str = Field(..., description="KOL ID")
    computed_at: datetime = Field(default_factory=datetime.now)
    sample_size: int = Field(0, description="Number of data points used")


# =============================================================================
# Scoring Configuration
# =============================================================================

@dataclass
class ScorerConfig:
    """Configuration for KOL scoring."""
    # Dimension weights (must sum to 1.0)
    accuracy_weight: float = 0.30
    timeliness_weight: float = 0.15
    return_weight: float = 0.30
    consistency_weight: float = 0.15
    depth_weight: float = 0.10

    # Decay parameters
    recent_performance_decay_days: int = 90  # Half-life for decay
    min_sample_size: int = 5  # Minimum trades for reliable score

    # Accuracy parameters
    accuracy_threshold_pct: float = 0.05  # 5% threshold for "correct" prediction
    accuracy_direction_only: bool = False  # If True, only direction matters

    # Timeliness parameters
    timeliness_ideal_days: int = 5  # Ideal days before event
    timeliness_max_days: int = 30  # Max days before event

    # Return parameters
    return_benchmark: float = 0.0  # Benchmark return (e.g., S&P 500)
    return_risk_adjusted: bool = True  # Use risk-adjusted returns

    # Consistency parameters
    consistency_window_trades: int = 10  # Rolling window for consistency

    def validate(self) -> bool:
        """Validate configuration."""
        total_weight = (
            self.accuracy_weight +
            self.timeliness_weight +
            self.return_weight +
            self.consistency_weight +
            self.depth_weight
        )
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Dimension weights sum to {total_weight}, normalizing")
            return False
        return True

    @classmethod
    def from_yaml(cls, path: Path) -> ScorerConfig:
        """Load configuration from YAML file."""
        if not path.exists():
            return cls()

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        scorer_config = data.get("kol_scorer", {})

        return cls(
            accuracy_weight=scorer_config.get("weights", {}).get("accuracy", 0.30),
            timeliness_weight=scorer_config.get("weights", {}).get("timeliness", 0.15),
            return_weight=scorer_config.get("weights", {}).get("return", 0.30),
            consistency_weight=scorer_config.get("weights", {}).get("consistency", 0.15),
            depth_weight=scorer_config.get("weights", {}).get("depth", 0.10),
            recent_performance_decay_days=scorer_config.get("decay_days", 90),
            min_sample_size=scorer_config.get("min_sample_size", 5),
        )


# =============================================================================
# KOL Scorer
# =============================================================================

class KOLScorer:
    """Multi-dimensional KOL performance scorer.

    Usage:
        scorer = KOLScorer()

        # Compute scores from backtest results
        scores = scorer.compute_scores(
            kol_id="kol_001",
            trades=trades,
            opinions=opinions,
        )

        # Get explanation
        explanation = scorer.explain(scores)
    """

    def __init__(self, config: Optional[ScorerConfig] = None):
        self.config = config or ScorerConfig()
        self.config.validate()

    def compute_scores(
        self,
        kol_id: str,
        trades: List[Dict[str, Any]],
        opinions: Optional[List[Dict[str, Any]]] = None,
        now: Optional[datetime] = None,
    ) -> DimensionScores:
        """Compute multi-dimensional scores for a KOL.

        Args:
            kol_id: KOL identifier
            trades: List of completed trades with:
                - return_pct: Trade return percentage
                - direction: 'long' or 'short'
                - entry_date, exit_date: Datetime
                - pnl: Profit/loss
                - holding_days: Days held
            opinions: Optional list of opinions with:
                - timestamp: When opinion was expressed
                - ticker: Ticker
                - direction: Predicted direction
                - confidence: Confidence level
            now: Current timestamp (for testing)

        Returns:
            DimensionScores with all dimensions and overall score
        """
        now = now or datetime.now()

        # Compute each dimension
        accuracy = self._compute_accuracy(trades, opinions)
        timeliness = self._compute_timeliness(trades, opinions, now)
        return_score = self._compute_return(trades)
        consistency = self._compute_consistency(trades)
        depth = self._compute_depth(trades, opinions)

        # Compute overall
        overall = (
            accuracy.weighted_score +
            timeliness.weighted_score +
            return_score.weighted_score +
            consistency.weighted_score +
            depth.weighted_score
        )

        return DimensionScores(
            accuracy=accuracy,
            timeliness=timeliness,
            return_score=return_score,
            consistency=consistency,
            depth=depth,
            overall=overall,
            kol_id=kol_id,
            sample_size=len(trades),
        )

    def _compute_accuracy(
        self,
        trades: List[Dict[str, Any]],
        opinions: Optional[List[Dict[str, Any]]],
    ) -> DimensionScore:
        """Compute accuracy dimension.

        Accuracy measures: How often predictions were correct.

        Metrics:
        - Direction accuracy: % of trades in correct direction
        - Magnitude accuracy: % of trades within target range
        """
        if not trades:
            return DimensionScore(
                dimension="accuracy",
                raw_score=2.5,
                weighted_score=2.5 * self.config.accuracy_weight,
                weight=self.config.accuracy_weight,
                contribution=2.5 * self.config.accuracy_weight,
                explanation="No trades available, using neutral score",
            )

        # Direction accuracy: trades with positive return are "correct"
        correct_trades = [t for t in trades if t.get('return_pct', 0) > 0]
        direction_accuracy = len(correct_trades) / len(trades)

        # Convert to 0-5 scale
        # 100% accuracy = 5.0
        # 50% accuracy = 2.5
        # 0% accuracy = 0.0
        raw_score = direction_accuracy * 5.0

        weighted_score = raw_score * self.config.accuracy_weight

        return DimensionScore(
            dimension="accuracy",
            raw_score=raw_score,
            weighted_score=weighted_score,
            weight=self.config.accuracy_weight,
            contribution=weighted_score,
            metrics={
                'direction_accuracy': direction_accuracy,
                'correct_trades': len(correct_trades),
                'total_trades': len(trades),
            },
            explanation=f"Direction accuracy: {direction_accuracy*100:.1f}% ({len(correct_trades)}/{len(trades)} correct)",
        )

    def _compute_timeliness(
        self,
        trades: List[Dict[str, Any]],
        opinions: Optional[List[Dict[str, Any]]],
        now: datetime,
    ) -> DimensionScore:
        """Compute timeliness dimension.

        Timeliness measures: How early before significant price moves.

        Metrics:
        - Average days before move
        - Decay-weighted recency
        """
        if not trades:
            return DimensionScore(
                dimension="timeliness",
                raw_score=2.5,
                weighted_score=2.5 * self.config.timeliness_weight,
                weight=self.config.timeliness_weight,
                contribution=2.5 * self.config.timeliness_weight,
                explanation="No trades available, using neutral score",
            )

        # Average holding days as inverse measure of timeliness
        # Shorter holding = more timely (caught the move early)
        avg_holding = np.mean([t.get('holding_days', 10) for t in trades])

        # Score mapping:
        # 0-5 days = 5.0 (very timely)
        # 5-15 days = 3.0
        # 15+ days = 1.0
        if avg_holding <= 5:
            raw_score = 5.0
        elif avg_holding <= 15:
            raw_score = 5.0 - (avg_holding - 5) * 0.2
        else:
            raw_score = max(1.0, 3.0 - (avg_holding - 15) * 0.1)

        # Apply recency decay
        if opinions:
            recent_opinions = [
                o for o in opinions
                if (now - datetime.fromisoformat(o['timestamp'])).days < self.config.recent_performance_decay_days
            ]
            recency_factor = len(recent_opinions) / len(opinions) if opinions else 1.0
            raw_score *= (0.7 + 0.3 * recency_factor)  # 70-100% of score

        weighted_score = raw_score * self.config.timeliness_weight

        return DimensionScore(
            dimension="timeliness",
            raw_score=raw_score,
            weighted_score=weighted_score,
            weight=self.config.timeliness_weight,
            contribution=weighted_score,
            metrics={
                'avg_holding_days': avg_holding,
                'recency_factor': recency_factor if opinions else 1.0,
            },
            explanation=f"Average holding: {avg_holding:.1f} days",
        )

    def _compute_return(self, trades: List[Dict[str, Any]]) -> DimensionScore:
        """Compute return dimension.

        Return measures: Risk-adjusted performance.

        Metrics:
        - Average return per trade
        - Sharpe ratio (if enough trades)
        - Win rate
        """
        if not trades:
            return DimensionScore(
                dimension="return",
                raw_score=2.5,
                weighted_score=2.5 * self.config.return_weight,
                weight=self.config.return_weight,
                contribution=2.5 * self.config.return_weight,
                explanation="No trades available, using neutral score",
            )

        returns = [t.get('return_pct', 0) for t in trades]
        avg_return = np.mean(returns)

        # Sharpe-like metric
        if len(returns) > 1:
            std_return = np.std(returns)
            sharpe = avg_return / std_return if std_return > 0 else 0
        else:
            sharpe = 0

        # Win rate
        win_rate = len([r for r in returns if r > 0]) / len(returns)

        # Score mapping:
        # avg_return > 10% = 5.0
        # avg_return > 5% = 4.0
        # avg_return > 0% = 3.0
        # avg_return > -5% = 2.0
        # avg_return > -10% = 1.0
        avg_return_pct = avg_return * 100
        if avg_return_pct > 10:
            raw_score = 5.0
        elif avg_return_pct > 5:
            raw_score = 4.0
        elif avg_return_pct > 0:
            raw_score = 3.0
        elif avg_return_pct > -5:
            raw_score = 2.0
        else:
            raw_score = 1.0

        # Adjust for risk (Sharpe)
        if sharpe > 2:
            raw_score = min(5.0, raw_score + 0.5)
        elif sharpe < 0:
            raw_score = max(1.0, raw_score - 0.5)

        weighted_score = raw_score * self.config.return_weight

        return DimensionScore(
            dimension="return",
            raw_score=raw_score,
            weighted_score=weighted_score,
            weight=self.config.return_weight,
            contribution=weighted_score,
            metrics={
                'avg_return_pct': avg_return_pct,
                'sharpe_ratio': sharpe,
                'win_rate': win_rate,
            },
            explanation=f"Avg return: {avg_return_pct:.1f}%, Win rate: {win_rate*100:.0f}%",
        )

    def _compute_consistency(self, trades: List[Dict[str, Any]]) -> DimensionScore:
        """Compute consistency dimension.

        Consistency measures: Stability of performance over time.

        Metrics:
        - Return volatility
        - Streak patterns
        - Gini coefficient of returns
        """
        if not trades or len(trades) < 3:
            return DimensionScore(
                dimension="consistency",
                raw_score=2.5,
                weighted_score=2.5 * self.config.consistency_weight,
                weight=self.config.consistency_weight,
                contribution=2.5 * self.config.consistency_weight,
                explanation="Insufficient data for consistency score",
            )

        returns = [t.get('return_pct', 0) for t in trades]

        # Coefficient of variation (lower = more consistent)
        mean_return = abs(np.mean(returns))
        std_return = np.std(returns)
        cv = std_return / mean_return if mean_return > 0.01 else 10  # High CV if mean near 0

        # Score mapping:
        # CV < 1.0 = 5.0 (very consistent)
        # CV < 2.0 = 4.0
        # CV < 3.0 = 3.0
        # CV < 5.0 = 2.0
        # CV >= 5.0 = 1.0
        if cv < 1.0:
            raw_score = 5.0
        elif cv < 2.0:
            raw_score = 4.0
        elif cv < 3.0:
            raw_score = 3.0
        elif cv < 5.0:
            raw_score = 2.0
        else:
            raw_score = 1.0

        # Check for alternating wins/losses (bad pattern)
        signs = [1 if r > 0 else -1 for r in returns]
        alternations = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i-1])
        alternation_rate = alternations / (len(signs) - 1) if len(signs) > 1 else 0

        if alternation_rate > 0.8:
            raw_score = max(1.0, raw_score - 1.0)  # Penalty for high alternation

        weighted_score = raw_score * self.config.consistency_weight

        return DimensionScore(
            dimension="consistency",
            raw_score=raw_score,
            weighted_score=weighted_score,
            weight=self.config.consistency_weight,
            contribution=weighted_score,
            metrics={
                'coefficient_of_variation': cv,
                'alternation_rate': alternation_rate,
            },
            explanation=f"Return variability (CV): {cv:.2f}",
        )

    def _compute_depth(
        self,
        trades: List[Dict[str, Any]],
        opinions: Optional[List[Dict[str, Any]]],
    ) -> DimensionScore:
        """Compute depth dimension.

        Depth measures: Quality of analysis and rationale.

        Metrics:
        - Average confidence level
        - Evidence text length (if available)
        - Rationale presence
        """
        if not opinions:
            # Use trades as proxy
            if not trades:
                return DimensionScore(
                    dimension="depth",
                    raw_score=2.5,
                    weighted_score=2.5 * self.config.depth_weight,
                    weight=self.config.depth_weight,
                    contribution=2.5 * self.config.depth_weight,
                    explanation="No data available, using neutral score",
                )

            # Score based on trade count (more trades = more coverage = more depth)
            n_trades = len(trades)
            if n_trades >= 50:
                raw_score = 5.0
            elif n_trades >= 20:
                raw_score = 4.0
            elif n_trades >= 10:
                raw_score = 3.0
            else:
                raw_score = 2.0

        else:
            # Use opinion data
            avg_confidence = np.mean([o.get('confidence', 0.5) for o in opinions])

            # Score based on confidence
            raw_score = avg_confidence * 5.0

            # Bonus for evidence/rationale
            with_rationale = len([o for o in opinions if o.get('rationale')])
            rationale_rate = with_rationale / len(opinions) if opinions else 0
            raw_score = min(5.0, raw_score + rationale_rate * 0.5)

        weighted_score = raw_score * self.config.depth_weight

        return DimensionScore(
            dimension="depth",
            raw_score=raw_score,
            weighted_score=weighted_score,
            weight=self.config.depth_weight,
            contribution=weighted_score,
            metrics={
                'avg_confidence': avg_confidence if opinions else 0.5,
                'rationale_rate': rationale_rate if opinions else 0,
                'sample_size': len(opinions) if opinions else len(trades),
            },
            explanation=f"Analysis depth based on {len(opinions) if opinions else len(trades)} data points",
        )

    def explain(self, scores: DimensionScores) -> Dict[str, Any]:
        """Generate detailed explanation of scores.

        Args:
            scores: Computed dimension scores

        Returns:
            Dict with explanation for each dimension
        """
        return {
            'kol_id': scores.kol_id,
            'overall_score': scores.overall,
            'overall_rating': self._score_to_rating(scores.overall),
            'dimensions': {
                'accuracy': {
                    'score': scores.accuracy.raw_score,
                    'weight': scores.accuracy.weight,
                    'contribution': scores.accuracy.contribution,
                    'explanation': scores.accuracy.explanation,
                    'metrics': scores.accuracy.metrics,
                },
                'timeliness': {
                    'score': scores.timeliness.raw_score,
                    'weight': scores.timeliness.weight,
                    'contribution': scores.timeliness.contribution,
                    'explanation': scores.timeliness.explanation,
                    'metrics': scores.timeliness.metrics,
                },
                'return': {
                    'score': scores.return_score.raw_score,
                    'weight': scores.return_score.weight,
                    'contribution': scores.return_score.contribution,
                    'explanation': scores.return_score.explanation,
                    'metrics': scores.return_score.metrics,
                },
                'consistency': {
                    'score': scores.consistency.raw_score,
                    'weight': scores.consistency.weight,
                    'contribution': scores.consistency.contribution,
                    'explanation': scores.consistency.explanation,
                    'metrics': scores.consistency.metrics,
                },
                'depth': {
                    'score': scores.depth.raw_score,
                    'weight': scores.depth.weight,
                    'contribution': scores.depth.contribution,
                    'explanation': scores.depth.explanation,
                    'metrics': scores.depth.metrics,
                },
            },
            'methodology': {
                'scoring_scale': '0-5 (0=worst, 5=best)',
                'weight_sum': sum([
                    scores.accuracy.weight,
                    scores.timeliness.weight,
                    scores.return_score.weight,
                    scores.consistency.weight,
                    scores.depth.weight,
                ]),
                'sample_size': scores.sample_size,
                'computed_at': scores.computed_at.isoformat(),
            },
        }

    def _score_to_rating(self, score: float) -> str:
        """Convert numeric score to rating category."""
        if score >= 4.5:
            return "优秀 (Excellent)"
        elif score >= 3.5:
            return "良好 (Good)"
        elif score >= 2.5:
            return "一般 (Average)"
        elif score >= 1.5:
            return "较差 (Below Average)"
        else:
            return "差 (Poor)"

    def rank_kols(
        self,
        kol_data: Dict[str, Dict[str, Any]],
        dimension: Optional[str] = None,
    ) -> List[Tuple[str, float, DimensionScores]]:
        """Rank KOLs by score.

        Args:
            kol_data: Dict mapping kol_id to {trades, opinions}
            dimension: Optional dimension to rank by (None = overall)

        Returns:
            List of (kol_id, score, scores) sorted by score
        """
        results = []

        for kol_id, data in kol_data.items():
            trades = data.get('trades', [])
            opinions = data.get('opinions', [])
            scores = self.compute_scores(kol_id, trades, opinions)

            if dimension == 'accuracy':
                score = scores.accuracy.raw_score
            elif dimension == 'timeliness':
                score = scores.timeliness.raw_score
            elif dimension == 'return':
                score = scores.return_score.raw_score
            elif dimension == 'consistency':
                score = scores.consistency.raw_score
            elif dimension == 'depth':
                score = scores.depth.raw_score
            else:
                score = scores.overall

            results.append((kol_id, score, scores))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results


# =============================================================================
# Convenience Functions
# =============================================================================

def compute_kol_score(
    kol_id: str,
    trades: List[Dict[str, Any]],
    opinions: Optional[List[Dict[str, Any]]] = None,
) -> DimensionScores:
    """Compute KOL score with default configuration.

    Args:
        kol_id: KOL identifier
        trades: List of completed trades
        opinions: Optional list of opinions

    Returns:
        DimensionScores
    """
    scorer = KOLScorer()
    return scorer.compute_scores(kol_id, trades, opinions)


# =============================================================================
# Task-Specified KOLScorerV2 (Rule-based with full explainability)
# =============================================================================

class KOLScorerV2:
    """KOL 评分器（任务规格版本）。

    使用可解释的评分函数评估 KOL 质量。
    支持两种模式：
    1. 规则模式：基于统计指标的确定性评分
    2. ML 模式：基于训练模型的评分（未来扩展）

    Thread-safe: 是。所有状态通过参数传入，无共享状态。
    """

    def __init__(self, weights: Optional[DimensionWeights] = None):
        self.weights = weights or DimensionWeights()

    def compute_scores(
        self,
        kol_id: str,
        actions: List[Any],
        backtest_results: Optional[List[Any]] = None,
    ) -> KOLScoreResult:
        """计算 KOL 评分。

        基于 TradeAction 列表和回测结果计算各维度评分。

        Args:
            kol_id: KOL 标识符
            actions: TradeAction 列表
            backtest_results: 回测结果列表

        Returns:
            KOLScoreResult with scores and explanations
        """
        now = datetime.now()

        # Compute each dimension
        accuracy = self.compute_accuracy_score(actions)
        timeliness = self.compute_timeliness_score(actions)
        return_score = self.compute_return_score(backtest_results or actions)
        consistency = self.compute_consistency_score(actions)

        dimension_scores = DimensionScoresV2(
            accuracy=accuracy,
            timeliness=timeliness,
            return_score=return_score,
            consistency=consistency,
        )

        overall = self.compute_overall(dimension_scores)

        # Generate explanations
        explanations = self._build_explanations(
            actions, backtest_results,
            accuracy, timeliness, return_score, consistency
        )

        # Compute confidence based on sample size
        sample_size = len(actions)
        confidence = min(1.0, sample_size / 30.0) if sample_size > 0 else 0.0

        return KOLScoreResult(
            kol_id=kol_id,
            overall_score=overall,
            dimension_scores=dimension_scores,
            explanations=explanations,
            confidence=confidence,
            sample_size=sample_size,
            last_updated=now.isoformat(),
        )

    def compute_accuracy_score(self, actions: List[Any]) -> float:
        """计算准确率评分 (1-5)。

        逻辑：
        - 统计每个 TradeAction 的方向与后续价格走势是否一致
        - 准确率 > 70% → 5分
        - 准确率 60-70% → 4分
        - 准确率 50-60% → 3分
        - 准确率 40-50% → 2分
        - 准确率 < 40% → 1分

        Args:
            actions: TradeAction 列表，每个应包含 is_correct 或 return_pct 字段

        Returns:
            评分 1-5
        """
        if not actions:
            return 3.0  # Neutral score for no data

        # Calculate accuracy from actions
        correct_count = 0
        total_count = 0

        for action in actions:
            # Handle both dict and object forms
            if isinstance(action, dict):
                is_correct = action.get('is_correct')
                return_pct = action.get('return_pct', 0)
            else:
                is_correct = getattr(action, 'is_correct', None)
                return_pct = getattr(action, 'return_pct', 0)

            if is_correct is not None:
                correct_count += 1 if is_correct else 0
                total_count += 1
            else:
                # Infer from return_pct: positive return = correct direction
                correct_count += 1 if return_pct > 0 else 0
                total_count += 1

        if total_count == 0:
            return 3.0

        accuracy = correct_count / total_count

        # Map accuracy to 1-5 score
        if accuracy > 0.70:
            return 5.0
        elif accuracy > 0.60:
            return 4.0
        elif accuracy > 0.50:
            return 3.0
        elif accuracy > 0.40:
            return 2.0
        else:
            return 1.0

    def compute_timeliness_score(self, actions: List[Any]) -> float:
        """计算时效性评分 (1-5)。

        逻辑：
        - 信号提前于价格变动的时间
        - 提前 > 5天 → 5分
        - 提前 3-5天 → 4分
        - 提前 1-3天 → 3分
        - 提前 0-1天 → 2分
        - 滞后 → 1分

        Args:
            actions: TradeAction 列表，每个应包含 lead_days 字段

        Returns:
            评分 1-5
        """
        if not actions:
            return 3.0

        lead_days_list = []
        for action in actions:
            if isinstance(action, dict):
                lead_days = action.get('lead_days')
                holding_days = action.get('holding_days', 10)
            else:
                lead_days = getattr(action, 'lead_days', None)
                holding_days = getattr(action, 'holding_days', 10)

            if lead_days is not None:
                lead_days_list.append(lead_days)
            else:
                # Infer from holding_days: shorter holding = better timeliness
                lead_days_list.append(max(0, 10 - holding_days))

        if not lead_days_list:
            return 3.0

        avg_lead_days = np.mean(lead_days_list)

        # Map lead days to 1-5 score
        if avg_lead_days > 5:
            return 5.0
        elif avg_lead_days > 3:
            return 4.0
        elif avg_lead_days > 1:
            return 3.0
        elif avg_lead_days > 0:
            return 2.0
        else:
            return 1.0

    def compute_return_score(self, backtest_results: List[Any]) -> float:
        """计算收益率评分 (1-5)。

        逻辑：
        - 年化收益 > 30% → 5分
        - 年化收益 15-30% → 4分
        - 年化收益 5-15% → 3分
        - 年化收益 0-5% → 2分
        - 年化收益 < 0% → 1分

        Args:
            backtest_results: 回测结果列表，每个应包含 annualized_return 或 return_pct

        Returns:
            评分 1-5
        """
        if not backtest_results:
            return 3.0

        returns = []
        for result in backtest_results:
            if isinstance(result, dict):
                annualized = result.get('annualized_return')
                return_pct = result.get('return_pct', 0)
            else:
                annualized = getattr(result, 'annualized_return', None)
                return_pct = getattr(result, 'return_pct', 0)

            if annualized is not None:
                returns.append(annualized)
            else:
                returns.append(return_pct)

        if not returns:
            return 3.0

        avg_return = np.mean(returns) * 100  # Convert to percentage

        # Map return to 1-5 score
        if avg_return > 30:
            return 5.0
        elif avg_return > 15:
            return 4.0
        elif avg_return > 5:
            return 3.0
        elif avg_return > 0:
            return 2.0
        else:
            return 1.0

    def compute_consistency_score(self, actions: List[Any]) -> float:
        """计算一致性评分 (1-5)。

        逻辑：
        - 同一标的方向是否一致
        - 逻辑链条是否自洽
        - 观点是否有矛盾

        通过检查方向一致性和收益稳定性来衡量。

        Args:
            actions: TradeAction 列表

        Returns:
            评分 1-5
        """
        if not actions or len(actions) < 3:
            return 3.0

        # Check direction consistency for same tickers
        ticker_directions: Dict[str, List[str]] = {}
        for action in actions:
            if isinstance(action, dict):
                ticker = action.get('ticker', 'UNKNOWN')
                direction = action.get('direction', 'hold')
            else:
                ticker = getattr(action, 'ticker', 'UNKNOWN')
                direction = getattr(action, 'direction', 'hold')

            if ticker not in ticker_directions:
                ticker_directions[ticker] = []
            ticker_directions[ticker].append(direction)

        # Calculate consistency per ticker
        consistencies = []
        for ticker, directions in ticker_directions.items():
            if len(directions) > 1:
                # Count direction changes
                changes = sum(1 for i in range(1, len(directions))
                              if directions[i] != directions[i-1])
                consistency = 1.0 - (changes / (len(directions) - 1))
                consistencies.append(consistency)

        if not consistencies:
            return 3.0

        avg_consistency = np.mean(consistencies)

        # Also check return volatility
        returns = []
        for action in actions:
            if isinstance(action, dict):
                returns.append(action.get('return_pct', 0))
            else:
                returns.append(getattr(action, 'return_pct', 0))

        if len(returns) > 1:
            mean_return = abs(np.mean(returns))
            std_return = np.std(returns)
            cv = std_return / mean_return if mean_return > 0.01 else 10

            # Low CV = high consistency
            if cv < 1.0:
                consistency_bonus = 0.2
            elif cv < 2.0:
                consistency_bonus = 0.1
            else:
                consistency_bonus = 0
        else:
            consistency_bonus = 0

        # Map consistency to 1-5 score
        final_consistency = min(1.0, avg_consistency + consistency_bonus)

        if final_consistency > 0.85:
            return 5.0
        elif final_consistency > 0.70:
            return 4.0
        elif final_consistency > 0.55:
            return 3.0
        elif final_consistency > 0.40:
            return 2.0
        else:
            return 1.0

    def compute_overall(self, dimension_scores: DimensionScoresV2) -> float:
        """计算综合评分。

        weighted average of dimension scores

        Args:
            dimension_scores: 各维度评分

        Returns:
            综合评分 1-5
        """
        overall = (
            dimension_scores.accuracy * self.weights.accuracy +
            dimension_scores.timeliness * self.weights.timeliness +
            dimension_scores.return_score * self.weights.return_score +
            dimension_scores.consistency * self.weights.consistency
        )
        return round(overall, 2)

    def _build_explanations(
        self,
        actions: List[Any],
        backtest_results: Optional[List[Any]],
        accuracy: float,
        timeliness: float,
        return_score: float,
        consistency: float,
    ) -> List[ScoringExplanation]:
        """构建评分解释."""
        explanations = []

        # Accuracy explanation
        correct_count = sum(
            1 for a in actions
            if (a.get('is_correct') if isinstance(a, dict) else getattr(a, 'is_correct', None))
            or ((a.get('return_pct', 0) if isinstance(a, dict) else getattr(a, 'return_pct', 0)) > 0)
        )
        explanations.append(ScoringExplanation(
            dimension="accuracy",
            score=accuracy,
            factors=["方向准确率", "预测与实际对比"],
            evidence=[f"正确预测: {correct_count}/{len(actions)}" if actions else "无数据"],
        ))

        # Timeliness explanation
        explanations.append(ScoringExplanation(
            dimension="timeliness",
            score=timeliness,
            factors=["信号提前量", "持仓周期"],
            evidence=[f"平均提前天数: {self._avg_lead_days(actions):.1f}天"],
        ))

        # Return explanation
        avg_return = self._avg_return(backtest_results or actions)
        explanations.append(ScoringExplanation(
            dimension="return_score",
            score=return_score,
            factors=["年化收益率", "风险调整收益"],
            evidence=[f"平均收益: {avg_return:.1f}%"],
        ))

        # Consistency explanation
        explanations.append(ScoringExplanation(
            dimension="consistency",
            score=consistency,
            factors=["方向一致性", "收益稳定性"],
            evidence=[f"涉及标的数: {len(set(self._get_tickers(actions)))}"],
        ))

        return explanations

    def _avg_lead_days(self, actions: List[Any]) -> float:
        """计算平均提前天数."""
        if not actions:
            return 0.0
        lead_days_list = []
        for action in actions:
            if isinstance(action, dict):
                lead_days = action.get('lead_days', max(0, 10 - action.get('holding_days', 10)))
            else:
                lead_days = getattr(action, 'lead_days', max(0, 10 - getattr(action, 'holding_days', 10)))
            lead_days_list.append(lead_days)
        return np.mean(lead_days_list) if lead_days_list else 0.0

    def _avg_return(self, results: List[Any]) -> float:
        """计算平均收益率."""
        if not results:
            return 0.0
        returns = []
        for r in results:
            if isinstance(r, dict):
                returns.append(r.get('annualized_return', r.get('return_pct', 0)) * 100)
            else:
                returns.append(getattr(r, 'annualized_return', getattr(r, 'return_pct', 0)) * 100)
        return np.mean(returns) if returns else 0.0

    def _get_tickers(self, actions: List[Any]) -> List[str]:
        """获取所有标的."""
        tickers = []
        for action in actions:
            if isinstance(action, dict):
                tickers.append(action.get('ticker', 'UNKNOWN'))
            else:
                tickers.append(getattr(action, 'ticker', 'UNKNOWN'))
        return tickers

    def explain(self, kol_id: str, result: KOLScoreResult) -> Dict[str, Any]:
        """生成评分解释报告。

        Args:
            kol_id: KOL 标识符
            result: 评分结果

        Returns:
            解释报告字典
        """
        return {
            "kol_id": kol_id,
            "overall_score": result.overall_score,
            "confidence": result.confidence,
            "sample_size": result.sample_size,
            "dimensions": {
                exp.dimension: {
                    "score": exp.score,
                    "factors": exp.factors,
                    "evidence": exp.evidence,
                }
                for exp in result.explanations
            },
            "weights": {
                "accuracy": self.weights.accuracy,
                "timeliness": self.weights.timeliness,
                "return_score": self.weights.return_score,
                "consistency": self.weights.consistency,
            },
            "methodology": {
                "scoring_scale": "1-5 (1=worst, 5=best)",
                "mode": "rule-based",
                "last_updated": result.last_updated,
            },
        }
