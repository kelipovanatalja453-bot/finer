"""KOL Rating Engine — Multi-dimensional KOL evaluation system.

Inspired by Morningstar fund manager ratings, this engine evaluates
financial influencers (KOLs) across five dimensions:
- Accuracy (35%): View prediction accuracy
- Stop Loss Quality (25%): Risk management quality
- Consistency (20%): Logical coherence
- Market Sensitivity (10%): Market timing ability
- Risk Awareness (10%): Risk warning frequency
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


# ==============================================================================
# Data Models
# ==============================================================================

class DirectionType(str, Enum):
    """View direction types."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    WATCHLIST = "watchlist"
    RISK_WARNING = "risk_warning"


class StarRating(int, Enum):
    """Star rating levels (Morningstar style)."""
    ONE_STAR = 1
    TWO_STAR = 2
    THREE_STAR = 3
    FOUR_STAR = 4
    FIVE_STAR = 5


class MedalType(str, Enum):
    """Medal types for top performers."""
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    NONE = "none"


@dataclass
class ViewValidation:
    """Validation result for a single view/prediction."""
    view_id: str
    ticker: str
    direction: DirectionType
    view_date: datetime

    # Price at view time
    price_at_view: float

    # Validation results
    price_7d: Optional[float] = None
    price_30d: Optional[float] = None
    return_7d: Optional[float] = None  # Percentage return
    return_30d: Optional[float] = None

    # Accuracy judgment
    is_correct_7d: Optional[bool] = None
    is_correct_30d: Optional[bool] = None

    # Market context
    market_return_7d: Optional[float] = None  # SPY return
    market_return_30d: Optional[float] = None

    # Relative performance
    excess_return_7d: Optional[float] = None
    excess_return_30d: Optional[float] = None


@dataclass
class StopLossAnalysis:
    """Analysis of stop loss recommendations."""
    total_stop_loss_suggestions: int = 0
    stop_loss_triggered_count: int = 0
    timely_triggers: int = 0  # Triggers before major drop
    avg_stop_loss_pct: float = 0.0  # Average stop loss percentage

    # Quality metrics
    protected_positions: int = 0  # Positions protected by stop loss
    missed_protections: int = 0  # Positions that dropped without stop loss

    # Calculated score (0-100)
    quality_score: float = 0.0


@dataclass
class ConsistencyAnalysis:
    """Analysis of view consistency."""
    total_views: int = 0
    direction_changes: int = 0  # Same ticker, different direction
    contradicting_views: int = 0  # Logically contradicting views

    # Per-ticker consistency
    ticker_consistency: Dict[str, float] = field(default_factory=dict)

    # Calculated score (0-100)
    consistency_score: float = 0.0


@dataclass
class MarketSensitivityAnalysis:
    """Analysis of market timing ability."""
    total_views: int = 0

    # Lead time before market turns (in days)
    avg_lead_time: float = 0.0
    early_signals: int = 0  # Views before major market moves

    # Major market events captured
    captured_tops: int = 0
    captured_bottoms: int = 0

    # Calculated score (0-100)
    sensitivity_score: float = 0.0


@dataclass
class RiskAwarenessAnalysis:
    """Analysis of risk warning frequency."""
    total_views: int = 0
    views_with_risk_warning: int = 0

    # Risk warning types
    stop_loss_mentions: int = 0
    position_size_warnings: int = 0
    volatility_warnings: int = 0

    # Calculated score (0-100)
    awareness_score: float = 0.0


class DimensionScores(BaseModel):
    """Scores for each evaluation dimension."""
    model_config = ConfigDict(strict=True)

    accuracy: float = Field(0.0, ge=0.0, le=100.0, description="View accuracy score")
    stop_loss_quality: float = Field(0.0, ge=0.0, le=100.0, description="Stop loss quality score")
    consistency: float = Field(0.0, ge=0.0, le=100.0, description="Consistency score")
    market_sensitivity: float = Field(0.0, ge=0.0, le=100.0, description="Market sensitivity score")
    risk_awareness: float = Field(0.0, ge=0.0, le=100.0, description="Risk awareness score")


class KOLRatingResult(BaseModel):
    """Complete KOL rating result."""
    model_config = ConfigDict(strict=True)

    kol_id: str = Field(..., description="KOL identifier")
    kol_name: Optional[str] = Field(None, description="KOL display name")

    # Overall score
    total_score: float = Field(0.0, ge=0.0, le=100.0, description="Weighted total score")

    # Dimension scores
    dimensions: DimensionScores = Field(
        default_factory=DimensionScores,
        description="Individual dimension scores"
    )

    # Star rating
    star_rating: int = Field(1, ge=1, le=5, description="1-5 star rating")
    medal: str = Field("none", description="Medal type (gold/silver/bronze/none)")

    # Statistics
    total_views: int = Field(0, description="Total number of views analyzed")
    validated_views: int = Field(0, description="Views with validation results")

    # Accuracy breakdown
    bullish_accuracy: float = Field(0.0, description="Accuracy for bullish views")
    bearish_accuracy: float = Field(0.0, description="Accuracy for bearish views")
    neutral_accuracy: float = Field(0.0, description="Accuracy for neutral views")

    # Time range
    first_view_date: Optional[datetime] = Field(None, description="First view date")
    last_view_date: Optional[datetime] = Field(None, description="Most recent view date")

    # Metadata
    calculated_at: datetime = Field(
        default_factory=datetime.now,
        description="When this rating was calculated"
    )
    data_version: str = Field("1.0", description="Rating algorithm version")

    # Detailed analysis (optional)
    detailed_analysis: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed breakdown of analysis"
    )


# ==============================================================================
# Rating Engine
# ==============================================================================

class KOLRatingEngine:
    """Multi-dimensional KOL rating engine.

    Usage:
        engine = KOLRatingEngine(data_dir="data/kol_ratings")
        rating = await engine.calculate_kol_rating("kol_123")
        scores = await engine.calculate_dimension_scores("kol_123")
    """

    # Dimension weights
    WEIGHTS = {
        "accuracy": 0.35,
        "stop_loss_quality": 0.25,
        "consistency": 0.20,
        "market_sensitivity": 0.10,
        "risk_awareness": 0.10,
    }

    # Star rating thresholds
    STAR_THRESHOLDS = {
        5: 90,   # Gold medal
        4: 75,   # Silver medal
        3: 60,   # Bronze medal
        2: 40,   # No medal
        1: 0,    # No medal
    }

    def __init__(self, data_dir: str = "data/kol_ratings"):
        """Initialize the rating engine.

        Args:
            data_dir: Directory to store rating data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Sub-directories
        self.views_dir = self.data_dir / "views"
        self.validations_dir = self.data_dir / "validations"
        self.ratings_dir = self.data_dir / "ratings"

        for subdir in [self.views_dir, self.validations_dir, self.ratings_dir]:
            subdir.mkdir(parents=True, exist_ok=True)

        # Finance skills client for market data (lazy init)
        self._finance_client = None

    async def _get_finance_client(self):
        """Get finance skills client (lazy initialization)."""
        if self._finance_client is None:
            from finer.services import get_finance_skills_client
            self._finance_client = get_finance_skills_client()
        return self._finance_client

    # --------------------------------------------------------------------------
    # Core API Methods
    # --------------------------------------------------------------------------

    async def calculate_kol_rating(self, kol_id: str) -> KOLRatingResult:
        """Calculate comprehensive rating for a single KOL.

        Args:
            kol_id: KOL identifier

        Returns:
            Complete rating result with all dimensions
        """
        # Get dimension scores
        dimensions = await self.calculate_dimension_scores(kol_id)

        # Calculate weighted total score
        total_score = (
            dimensions.accuracy * self.WEIGHTS["accuracy"] +
            dimensions.stop_loss_quality * self.WEIGHTS["stop_loss_quality"] +
            dimensions.consistency * self.WEIGHTS["consistency"] +
            dimensions.market_sensitivity * self.WEIGHTS["market_sensitivity"] +
            dimensions.risk_awareness * self.WEIGHTS["risk_awareness"]
        )

        # Determine star rating and medal
        star_rating = self._calculate_star_rating(total_score)
        medal = self._get_medal_type(star_rating)

        # Get KOL stats
        stats = await self.get_kol_stats(kol_id)

        # Build result
        result = KOLRatingResult(
            kol_id=kol_id,
            kol_name=stats.get("name"),
            total_score=round(total_score, 2),
            dimensions=dimensions,
            star_rating=star_rating,
            medal=medal,
            total_views=stats.get("total_views", 0),
            validated_views=stats.get("validated_views", 0),
            bullish_accuracy=stats.get("bullish_accuracy", 0.0),
            bearish_accuracy=stats.get("bearish_accuracy", 0.0),
            neutral_accuracy=stats.get("neutral_accuracy", 0.0),
            first_view_date=stats.get("first_view_date"),
            last_view_date=stats.get("last_view_date"),
        )

        # Save rating
        await self._save_rating(result)

        return result

    async def calculate_dimension_scores(self, kol_id: str) -> DimensionScores:
        """Calculate scores for each evaluation dimension.

        Args:
            kol_id: KOL identifier

        Returns:
            DimensionScores with individual scores
        """
        # Get view data
        views = await self._load_kol_views(kol_id)
        validations = await self._load_kol_validations(kol_id)

        # Calculate each dimension
        accuracy = await self._calculate_accuracy(validations)
        stop_loss = await self._calculate_stop_loss_quality(views, validations)
        consistency = await self._calculate_consistency(views)
        sensitivity = await self._calculate_market_sensitivity(views, validations)
        risk = await self._calculate_risk_awareness(views)

        return DimensionScores(
            accuracy=accuracy,
            stop_loss_quality=stop_loss,
            consistency=consistency,
            market_sensitivity=sensitivity,
            risk_awareness=risk,
        )

    async def get_kol_stats(self, kol_id: str) -> Dict[str, Any]:
        """Get statistics for a KOL.

        Args:
            kol_id: KOL identifier

        Returns:
            Dictionary with KOL statistics
        """
        views = await self._load_kol_views(kol_id)
        validations = await self._load_kol_validations(kol_id)

        if not views:
            return {
                "total_views": 0,
                "validated_views": 0,
                "bullish_accuracy": 0.0,
                "bearish_accuracy": 0.0,
                "neutral_accuracy": 0.0,
            }

        # Count views by direction
        direction_counts = {"bullish": 0, "bearish": 0, "neutral": 0}
        for view in views:
            direction = view.get("direction", "neutral")
            if direction in direction_counts:
                direction_counts[direction] += 1

        # Calculate accuracy by direction
        accuracy_by_direction = {"bullish": [], "bearish": [], "neutral": []}
        for val in validations:
            direction = val.get("direction", "neutral")
            if direction in accuracy_by_direction and val.get("is_correct_7d") is not None:
                accuracy_by_direction[direction].append(1 if val["is_correct_7d"] else 0)

        # Calculate average accuracies
        bullish_acc = sum(accuracy_by_direction["bullish"]) / len(accuracy_by_direction["bullish"]) * 100 if accuracy_by_direction["bullish"] else 0.0
        bearish_acc = sum(accuracy_by_direction["bearish"]) / len(accuracy_by_direction["bearish"]) * 100 if accuracy_by_direction["bearish"] else 0.0
        neutral_acc = sum(accuracy_by_direction["neutral"]) / len(accuracy_by_direction["neutral"]) * 100 if accuracy_by_direction["neutral"] else 0.0

        # Date range
        dates = [datetime.fromisoformat(v["view_date"]) for v in views if v.get("view_date")]
        first_date = min(dates) if dates else None
        last_date = max(dates) if dates else None

        return {
            "name": views[0].get("kol_name") if views else None,
            "total_views": len(views),
            "validated_views": len([v for v in validations if v.get("is_correct_7d") is not None]),
            "bullish_accuracy": round(bullish_acc, 2),
            "bearish_accuracy": round(bearish_acc, 2),
            "neutral_accuracy": round(neutral_acc, 2),
            "first_view_date": first_date,
            "last_view_date": last_date,
            "direction_distribution": direction_counts,
        }

    async def compare_kols(self, kol_ids: List[str]) -> Dict[str, KOLRatingResult]:
        """Compare multiple KOLs.

        Args:
            kol_ids: List of KOL identifiers

        Returns:
            Dictionary mapping KOL ID to rating result
        """
        results = {}
        for kol_id in kol_ids:
            try:
                results[kol_id] = await self.calculate_kol_rating(kol_id)
            except Exception as e:
                logger.error(f"Error calculating rating for {kol_id}: {e}")
                results[kol_id] = KOLRatingResult(kol_id=kol_id)

        return results

    async def get_top_kols(
        self,
        limit: int = 10,
        min_views: int = 10,
        sort_by: str = "total_score",
    ) -> List[KOLRatingResult]:
        """Get top KOLs by rating.

        Args:
            limit: Maximum number of KOLs to return
            min_views: Minimum views required for ranking
            sort_by: Sort field (total_score, accuracy, etc.)

        Returns:
            List of KOL rating results sorted by score
        """
        # Find all KOL rating files
        ratings = []
        for rating_file in self.ratings_dir.glob("*.json"):
            try:
                with open(rating_file, "r") as f:
                    data = json.load(f)
                    result = KOLRatingResult(**data)

                    # Filter by minimum views
                    if result.total_views >= min_views:
                        ratings.append(result)
            except Exception as e:
                logger.warning(f"Error loading rating file {rating_file}: {e}")

        # Sort by specified field
        if sort_by == "total_score":
            ratings.sort(key=lambda r: r.total_score, reverse=True)
        elif sort_by in ["accuracy", "stop_loss_quality", "consistency", "market_sensitivity", "risk_awareness"]:
            ratings.sort(key=lambda r: getattr(r.dimensions, sort_by), reverse=True)
        else:
            ratings.sort(key=lambda r: r.total_score, reverse=True)

        return ratings[:limit]

    # --------------------------------------------------------------------------
    # Dimension Calculations
    # --------------------------------------------------------------------------

    async def _calculate_accuracy(self, validations: List[Dict]) -> float:
        """Calculate view accuracy score.

        Accuracy is based on:
        - 7-day return validation
        - 30-day return validation (bonus)
        - Direction correctness
        - Excess return vs market
        """
        if not validations:
            return 0.0

        total_score = 0.0
        total_weight = 0.0

        for val in validations:
            # Skip unvalidated views
            if val.get("is_correct_7d") is None:
                continue

            # Base score for correct direction
            base_score = 100 if val["is_correct_7d"] else 0

            # Bonus for excess return
            excess_return = val.get("excess_return_7d", 0) or 0
            bonus = min(20, max(-20, excess_return * 2))  # Cap bonus/penalty

            # Weight by view type (bullish/bearish worth more than neutral)
            direction = val.get("direction", "neutral")
            weight = 1.5 if direction in ["bullish", "bearish"] else 1.0

            # 30-day bonus
            if val.get("is_correct_30d"):
                base_score += 10  # Extra points for 30-day validation

            view_score = base_score + bonus
            total_score += view_score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return min(100, max(0, total_score / total_weight))

    async def _calculate_stop_loss_quality(
        self,
        views: List[Dict],
        validations: List[Dict]
    ) -> float:
        """Calculate stop loss quality score.

        Evaluates:
        - Stop loss suggestion frequency
        - Stop loss trigger timeliness
        - Protection effectiveness
        """
        if not views:
            return 0.0

        # Count stop loss mentions
        stop_loss_views = []
        for view in views:
            action_chain = view.get("action_chain", [])
            for action in action_chain:
                trigger = action.get("trigger_condition", "")
                if trigger and ("stop" in trigger.lower() or "loss" in trigger.lower()):
                    stop_loss_views.append(view)
                    break

        if not stop_loss_views:
            # No stop loss suggestions, score based on overall risk management
            risk_warnings = len([v for v in views if v.get("direction") == "risk_warning"])
            return min(50, risk_warnings * 5)  # Up to 50 points for risk awareness

        # Calculate quality metrics
        suggestion_rate = len(stop_loss_views) / len(views)

        # Check if stop losses were triggered appropriately
        timely_triggers = 0
        total_stop_loss = len(stop_loss_views)

        for view in stop_loss_views:
            view_id = view.get("view_id")
            for val in validations:
                if val.get("view_id") == view_id:
                    # Check if stop loss protected from major drop
                    return_7d = val.get("return_7d", 0) or 0
                    if return_7d < -5:  # Major drop
                        # Stop loss suggestion was valuable
                        timely_triggers += 1
                    break

        # Quality score components
        frequency_score = min(40, suggestion_rate * 100)  # Up to 40 points for frequency
        effectiveness_score = (timely_triggers / total_stop_loss * 60) if total_stop_loss > 0 else 0

        return min(100, frequency_score + effectiveness_score)

    async def _calculate_consistency(self, views: List[Dict]) -> float:
        """Calculate view consistency score.

        Evaluates:
        - Direction changes on same ticker
        - Logical coherence
        - Time-weighted consistency
        """
        if not views:
            return 0.0

        # Group views by ticker
        ticker_views: Dict[str, List[Dict]] = {}
        for view in views:
            ticker = view.get("ticker", "")
            if ticker:
                if ticker not in ticker_views:
                    ticker_views[ticker] = []
                ticker_views[ticker].append(view)

        if not ticker_views:
            return 50.0  # Default score if no ticker data

        # Calculate consistency per ticker
        consistency_scores = []

        for ticker, ticker_view_list in ticker_views.items():
            if len(ticker_view_list) < 2:
                continue

            # Sort by date
            sorted_views = sorted(
                ticker_view_list,
                key=lambda v: v.get("view_date", "")
            )

            # Count direction changes
            changes = 0
            for i in range(1, len(sorted_views)):
                prev_dir = sorted_views[i-1].get("direction", "neutral")
                curr_dir = sorted_views[i].get("direction", "neutral")

                # Significant change: bullish <-> bearish
                if {prev_dir, curr_dir} == {"bullish", "bearish"}:
                    changes += 1
                # Moderate change: bullish/bearish <-> neutral
                elif prev_dir != curr_dir and "neutral" in [prev_dir, curr_dir]:
                    changes += 0.3

            # Consistency = 1 - change_rate
            change_rate = changes / (len(sorted_views) - 1)
            ticker_consistency = max(0, 1 - change_rate)
            consistency_scores.append(ticker_consistency)

        if not consistency_scores:
            return 100.0  # Perfect consistency if no changes

        # Average consistency across all tickers
        avg_consistency = sum(consistency_scores) / len(consistency_scores)

        return avg_consistency * 100

    async def _calculate_market_sensitivity(
        self,
        views: List[Dict],
        validations: List[Dict]
    ) -> float:
        """Calculate market sensitivity/timing score.

        Evaluates:
        - Views before major market moves
        - Lead time before market turns
        - Captured tops and bottoms
        """
        if not views or not validations:
            return 50.0  # Default score

        early_signals = 0
        total_validated = 0

        for val in validations:
            if val.get("is_correct_7d") is None:
                continue

            total_validated += 1

            # Check if view was early (before major move)
            return_7d = val.get("return_7d", 0) or 0
            direction = val.get("direction", "neutral")

            # Bullish view before significant rise
            if direction == "bullish" and return_7d > 5:
                early_signals += 1
            # Bearish view before significant drop
            elif direction == "bearish" and return_7d < -5:
                early_signals += 1
            # Correct neutral call during consolidation
            elif direction == "neutral" and abs(return_7d) < 3:
                early_signals += 0.5

        if total_validated == 0:
            return 50.0

        sensitivity_rate = early_signals / total_validated
        return min(100, sensitivity_rate * 150)  # Scale up for visibility

    async def _calculate_risk_awareness(self, views: List[Dict]) -> float:
        """Calculate risk awareness score.

        Evaluates:
        - Risk warning frequency
        - Risk warning coverage
        - Types of risk warnings
        """
        if not views:
            return 0.0

        # Count views with risk indicators
        risk_views = 0
        risk_warning_views = 0

        for view in views:
            direction = view.get("direction", "")
            rationale = view.get("rationale", "") or ""
            action_chain = view.get("action_chain", [])

            # Explicit risk warning direction
            if direction == "risk_warning":
                risk_warning_views += 1
                risk_views += 1
                continue

            # Check rationale for risk mentions
            risk_keywords = ["risk", "caution", "volatile", "uncertain", "stop loss", "position size"]
            rationale_lower = rationale.lower()

            has_risk = any(kw in rationale_lower for kw in risk_keywords)

            # Check action chain for stop loss
            for action in action_chain:
                trigger = action.get("trigger_condition", "") or ""
                if "stop" in trigger.lower() or "loss" in trigger.lower():
                    has_risk = True
                    break

            if has_risk:
                risk_views += 1

        # Calculate coverage
        coverage_rate = risk_views / len(views)

        # Bonus for explicit risk_warning direction
        bonus = min(20, risk_warning_views * 5)

        # Score = coverage * 80 + bonus
        score = coverage_rate * 80 + bonus

        return min(100, score)

    # --------------------------------------------------------------------------
    # Data Loading / Saving
    # --------------------------------------------------------------------------

    async def _load_kol_views(self, kol_id: str) -> List[Dict]:
        """Load KOL views from file."""
        view_file = self.views_dir / f"{kol_id}.json"
        if not view_file.exists():
            return []

        try:
            with open(view_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading views for {kol_id}: {e}")
            return []

    async def _load_kol_validations(self, kol_id: str) -> List[Dict]:
        """Load KOL view validations from file."""
        val_file = self.validations_dir / f"{kol_id}.json"
        if not val_file.exists():
            return []

        try:
            with open(val_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading validations for {kol_id}: {e}")
            return []

    async def _save_rating(self, result: KOLRatingResult):
        """Save rating result to file."""
        rating_file = self.ratings_dir / f"{result.kol_id}.json"

        try:
            # Convert to dict for JSON serialization
            data = result.model_dump()

            # Handle datetime serialization
            if data.get("first_view_date"):
                data["first_view_date"] = data["first_view_date"].isoformat()
            if data.get("last_view_date"):
                data["last_view_date"] = data["last_view_date"].isoformat()
            data["calculated_at"] = data["calculated_at"].isoformat()

            with open(rating_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved rating for {result.kol_id}")
        except Exception as e:
            logger.error(f"Error saving rating for {result.kol_id}: {e}")

    async def save_kol_view(self, kol_id: str, view: Dict):
        """Save a new view for a KOL.

        Args:
            kol_id: KOL identifier
            view: View data dictionary
        """
        views = await self._load_kol_views(kol_id)
        views.append(view)

        view_file = self.views_dir / f"{kol_id}.json"
        with open(view_file, "w") as f:
            json.dump(views, f, indent=2, ensure_ascii=False)

    async def save_kol_validation(self, kol_id: str, validation: Dict):
        """Save a view validation result.

        Args:
            kol_id: KOL identifier
            validation: Validation data dictionary
        """
        validations = await self._load_kol_validations(kol_id)
        validations.append(validation)

        val_file = self.validations_dir / f"{kol_id}.json"
        with open(val_file, "w") as f:
            json.dump(validations, f, indent=2, ensure_ascii=False)

    # --------------------------------------------------------------------------
    # Helper Methods
    # --------------------------------------------------------------------------

    def _calculate_star_rating(self, total_score: float) -> int:
        """Convert total score to star rating."""
        for stars, threshold in sorted(self.STAR_THRESHOLDS.items(), reverse=True):
            if total_score >= threshold:
                return stars
        return 1

    def _get_medal_type(self, star_rating: int) -> str:
        """Get medal type for star rating."""
        if star_rating >= 5:
            return MedalType.GOLD.value
        elif star_rating >= 4:
            return MedalType.SILVER.value
        elif star_rating >= 3:
            return MedalType.BRONZE.value
        else:
            return MedalType.NONE.value

    async def validate_view(
        self,
        ticker: str,
        direction: str,
        view_date: datetime,
        price_at_view: float,
    ) -> ViewValidation:
        """Validate a view against market data.

        Uses Finance-Skills to get historical prices and calculate returns.

        Args:
            ticker: Ticker symbol
            direction: View direction
            view_date: Date view was made
            price_at_view: Price at view time

        Returns:
            ViewValidation with calculated metrics
        """
        client = await self._get_finance_client()

        # Calculate validation dates
        date_7d = view_date + timedelta(days=7)
        date_30d = view_date + timedelta(days=30)

        # Get historical prices (this would need a historical price API)
        # For now, return placeholder
        validation = ViewValidation(
            view_id=f"{ticker}_{view_date.isoformat()}",
            ticker=ticker,
            direction=DirectionType(direction),
            view_date=view_date,
            price_at_view=price_at_view,
        )

        # TODO: Fetch actual historical prices from Finance-Skills
        # client.call(SkillName.YFINANCE_DATA, ticker=ticker, start=view_date, end=date_30d)

        return validation

    def get_leaderboard(
        self,
        dimension: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get leaderboard for a specific dimension.

        Args:
            dimension: Dimension to sort by (None for total score)
            limit: Number of entries to return

        Returns:
            List of leaderboard entries
        """
        leaderboard = []

        for rating_file in self.ratings_dir.glob("*.json"):
            try:
                with open(rating_file, "r") as f:
                    data = json.load(f)

                    score = data["total_score"]
                    if dimension and dimension in data.get("dimensions", {}):
                        score = data["dimensions"][dimension]

                    leaderboard.append({
                        "kol_id": data["kol_id"],
                        "kol_name": data.get("kol_name"),
                        "score": score,
                        "star_rating": data["star_rating"],
                        "medal": data["medal"],
                        "total_views": data["total_views"],
                    })
            except Exception as e:
                logger.warning(f"Error loading rating file: {e}")

        # Sort by score
        leaderboard.sort(key=lambda x: x["score"], reverse=True)

        return leaderboard[:limit]


# ==============================================================================
# Convenience Functions
# ==============================================================================

_engine: Optional[KOLRatingEngine] = None


def get_kol_rating_engine(data_dir: str = "data/kol_ratings") -> KOLRatingEngine:
    """Get or create the global KOL rating engine."""
    global _engine
    if _engine is None:
        _engine = KOLRatingEngine(data_dir=data_dir)
    return _engine


async def calculate_kol_rating(kol_id: str) -> KOLRatingResult:
    """Convenience function to calculate KOL rating."""
    engine = get_kol_rating_engine()
    return await engine.calculate_kol_rating(kol_id)


async def get_top_kols(limit: int = 10) -> List[KOLRatingResult]:
    """Convenience function to get top KOLs."""
    engine = get_kol_rating_engine()
    return await engine.get_top_kols(limit=limit)
