"""DEPRECATED: This module outputs legacy SegmentRecord.

New code should use the canonical F1 adapters in:
- PDFStandardizer (parsing/pdf_standardizer.py)
- ImageOCRLayoutStandardizer (parsing/image_ocr_standardizer.py)
- FeishuChatMarkdownStandardizer (parsing/feishu_chat_standardizer.py)
- ManualTextStandardizer (parsing/manual_text_standardizer.py)

This module is preserved for backward compatibility only.
"""

import json
import logging
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from finer.schemas.segment import SegmentRecord

@dataclass
class NormalizedEntity:
    original_term: str
    normalized_name: str
    ticker: Optional[str] = None
    confidence: float = 1.0

class SlangMapper:
    """
    Handles domain-specific slang and entity normalization for financial research.
    Supports static mapping and provides hooks for ML-based disambiguation.
    """
    
    DEFAULT_MAPPING = {
        "海公公": ("海力士", "000660.KS"),
        "大A": ("上证指数", "000001.SH"),
        "小作文": ("非官方市场传闻", None),
        "茅王": ("贵州茅台", "600519.SH"),
        "宁王": ("宁德时代", "300750.SZ"),
    }

    DEFAULT_CONFIG_PATH = os.path.join(os.getcwd(), "data/config/slang.json")

    def __init__(self, custom_mapping_path: Optional[str] = None):
        self.mapping = self.DEFAULT_MAPPING.copy()
        
        # Priority: custom_mapping_path > DEFAULT_CONFIG_PATH
        config_to_load = custom_mapping_path or self.DEFAULT_CONFIG_PATH
        if os.path.exists(config_to_load):
            self._load_custom_mapping(config_to_load)
            
    def _load_custom_mapping(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                custom = json.load(f)
                self.mapping.update(custom)
        except Exception as e:
            logging.error(f"Failed to load slang mapping from {path}: {e}")

    def tag_segment(self, segment: SegmentRecord) -> SegmentRecord:
        """
        Processes a segment, adds slang_tags to metadata.
        """
        tags = self.get_canonical_json_fragment(segment.text)
        if tags:
            if "slang_tags" not in segment.metadata:
                segment.metadata["slang_tags"] = []
            segment.metadata["slang_tags"].extend(tags)
        return segment

    def normalize(self, term: str) -> Optional[NormalizedEntity]:
        """
        Static lookup for slang terms.
        """
        if term in self.mapping:
            name, ticker = self.mapping[term]
            return NormalizedEntity(
                original_term=term,
                normalized_name=name,
                ticker=ticker,
                confidence=1.0  # Static match is high confidence
            )
        return None

    def find_entities_in_text(self, text: str) -> List[NormalizedEntity]:
        """
        Scan text for known slang terms and return normalized entities.
        In a future phase, this will be replaced by a VLM/LLM-based 
        contextual disambiguation tool (RLHF-refined).
        """
        results = []
        for slang, (name, ticker) in self.mapping.items():
            if slang in text:
                results.append(NormalizedEntity(
                    original_term=slang,
                    normalized_name=name,
                    ticker=ticker,
                    confidence=1.0
                ))
        return results

    def get_canonical_json_fragment(self, text: str) -> List[Dict]:
        """
        Returns a list of dicts suitable for the 'entities' field in research_object.schema.json.
        """
        entities = self.find_entities_in_text(text)
        return [
            {
                "original_term": e.original_term,
                "normalized_name": e.normalized_name,
                "ticker": e.ticker,
                "confidence": e.confidence
            }
            for e in entities
        ]
