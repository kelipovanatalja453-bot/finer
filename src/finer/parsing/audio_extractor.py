"""DEPRECATED: This module outputs legacy SegmentRecord.

New code should use the canonical F1 adapters in:
- PDFStandardizer (parsing/pdf_standardizer.py)
- ImageOCRLayoutStandardizer (parsing/image_ocr_standardizer.py)
- FeishuChatMarkdownStandardizer (parsing/feishu_chat_standardizer.py)
- ManualTextStandardizer (parsing/manual_text_standardizer.py)

This module is preserved for backward compatibility only.
"""

import os
import logging
from pathlib import Path
from finer.schemas.content import ContentRecord
from finer.schemas.segment import SegmentRecord

# We import DocumentConverter to parse the existing transcript PDFs fallback
try:
    from finer.services.converter import DocumentConverter
except ImportError:
    DocumentConverter = None

class AudioExtractor:
    """
    Extracts text and timestamps from Audio using DashScope Paraformer.
    Since DashScope long-audio Transcription requires OSS Object URLs, 
    this class provides a hybrid approach:
    1. It relies on the provided .pdf transcripts if available (as an MVP fallback).
    2. Real audio API calls would chunk the audio or stream via WebSockets.
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        self.converter = DocumentConverter() if DocumentConverter else None

    def _extract_from_existing_transcript(self, transcript_path: Path, content_record: ContentRecord) -> list[SegmentRecord]:
        """
        Uses MarkItDown to parse the existing transcript PDF files provided by the user.
        """
        if not self.converter:
            logging.error("DocumentConverter unavailable. Cannot parse transcript PDF.")
            return []
            
        md_text = self.converter.convert_to_markdown(transcript_path)
        if not md_text:
            return []
            
        blocks = md_text.split("\n\n")
        segments = []
        for index, block_text in enumerate(blocks):
            block_text = block_text.strip()
            if not block_text:
                continue
                
            segments.append(SegmentRecord(
                segment_id=f"{content_record.content_id}-audiotranscript-{index}",
                content_id=content_record.content_id,
                text=block_text,
                source_modality="audio_asr",
                metadata={"fallback": "existing_transcript_pdf", "block_index": index}
            ))
            
        return segments

    def extract_audio(self, content_record: ContentRecord) -> list[SegmentRecord]:
        source_path = Path(content_record.source_path)
        
        # Check if the user provided a transcript alongside the audio 
        # (e.g. 20260125-内部直播音频.mp3.pdf)
        possible_transcript_path = source_path.with_name(source_path.name + ".pdf")
        if possible_transcript_path.exists():
            logging.info(f"Discovered existing transcript for {source_path.name}. Using it as fallback extraction...")
            return self._extract_from_existing_transcript(possible_transcript_path, content_record)
            
        # If no transcript, we issue a clear warning about OSS requirements for DashScope.
        logging.warning(
            f"Cannot strictly perform API transcription on {source_path.name} "
            f"DashScope requires an Alibaba OSS URL for long audio files (>60s). "
            f"Please chunk the audio or upload to OSS first."
        )
        return []
