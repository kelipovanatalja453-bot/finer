"""Extraction module for Finer pipeline.

This module provides intent extraction and event extraction functionality.
"""

from finer.extraction.intent_extractor import (
    IntentExtractionResult,
    extract_intents_from_envelope,
)

__all__ = [
    "IntentExtractionResult",
    "extract_intents_from_envelope",
]