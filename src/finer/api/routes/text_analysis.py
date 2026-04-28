"""Text Analysis API Routes — REST endpoints for zhiziX 14-dimension analysis.

Provides endpoints for:
- Full text analysis
- Single dimension analysis
- Dimension listing
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
import logging

from finer.schemas.text_analysis import (
    TextAnalysisRequest,
    TextAnalysisResult,
    AnalysisDimension,
    DimensionInfo,
    DIMENSION_INFO,
)
from finer.ml.sentiment.text_analysis_engine import TextAnalysisEngine

logger = logging.getLogger(__name__)
router = APIRouter()

# Singleton engine
_engine: Optional[TextAnalysisEngine] = None


def get_engine() -> TextAnalysisEngine:
    """Get or create text analysis engine."""
    global _engine
    if _engine is None:
        _engine = TextAnalysisEngine()
    return _engine


@router.post("/analyze", response_model=TextAnalysisResult)
async def analyze_text(request: TextAnalysisRequest):
    """Analyze text using zhiziX 14 dimensions.

    Args:
        request: Analysis request with text and optional dimensions

    Returns:
        TextAnalysisResult with all dimension results
    """
    engine = get_engine()
    try:
        return engine.analyze(
            text=request.text,
            dimensions=request.dimensions,
            language=request.language,
            context=request.context,
        )
    except Exception as e:
        logger.error(f"Text analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/dimension/{dimension}")
async def analyze_dimension(
    dimension: AnalysisDimension,
    text: str,
    context: Optional[dict] = None,
):
    """Analyze a single dimension.

    Args:
        dimension: Dimension to analyze
        text: Text to analyze
        context: Optional context

    Returns:
        Dimension-specific result
    """
    engine = get_engine()
    try:
        result = engine.analyze_dimension(dimension, text, context)
        if result is None:
            raise HTTPException(status_code=400, detail=f"Dimension {dimension} not implemented")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dimension analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dimensions")
async def list_dimensions():
    """List all available analysis dimensions.

    Returns:
        List of dimension info with priorities
    """
    return {
        "dimensions": [
            {
                "id": dim.value,
                "name": info.name,
                "name_en": info.name_en,
                "priority": info.priority.value,
                "description": info.description,
            }
            for dim, info in DIMENSION_INFO.items()
        ]
    }


@router.get("/dimensions/high-priority")
async def list_high_priority_dimensions():
    """List high priority dimensions.

    Returns:
        List of high priority dimension IDs
    """
    from finer.schemas.text_analysis import get_high_priority_dimensions
    return {
        "dimensions": [dim.value for dim in get_high_priority_dimensions()]
    }


@router.get("/dimensions/medium-priority")
async def list_medium_priority_dimensions():
    """List medium priority dimensions.

    Returns:
        List of medium priority dimension IDs
    """
    from finer.schemas.text_analysis import get_medium_priority_dimensions
    return {
        "dimensions": [dim.value for dim in get_medium_priority_dimensions()]
    }


@router.post("/kol-fingerprint")
async def extract_kol_fingerprint(text: str):
    """Extract KOL voice fingerprint from text.

    This analyzes the text and returns a fingerprint suitable for
    KOL identification and clustering.

    Args:
        text: Text to analyze

    Returns:
        KOL fingerprint dictionary
    """
    engine = get_engine()
    try:
        # Analyze key dimensions for fingerprint
        result = engine.analyze(
            text=text,
            dimensions=[
                AnalysisDimension.SURFACE_STYLE,
                AnalysisDimension.CONTENT_STRUCTURE,
                AnalysisDimension.ARGUMENTATION,
                AnalysisDimension.EMOTION_ARC,
            ],
        )
        return {
            "fingerprint": result.kol_fingerprint,
            "quality_score": result.overall_quality_score,
        }
    except Exception as e:
        logger.error(f"KOL fingerprint extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
