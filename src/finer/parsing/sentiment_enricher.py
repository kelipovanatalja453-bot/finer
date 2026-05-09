"""DEPRECATED: This module outputs legacy SegmentRecord.

New code should use the canonical F1 adapters in:
- PDFStandardizer (parsing/pdf_standardizer.py)
- ImageOCRLayoutStandardizer (parsing/image_ocr_standardizer.py)
- FeishuChatMarkdownStandardizer (parsing/feishu_chat_standardizer.py)
- ManualTextStandardizer (parsing/manual_text_standardizer.py)

This module is preserved for backward compatibility only.
"""

from snownlp import SnowNLP
import logging
import re
from finer.schemas.segment import SegmentRecord
from finer.schemas.segment import SegmentRecord

class SentimentEnricher:
    """
    Local NLP processing to determine sentiment intensity using static lightweight models.
    """
    
    @staticmethod
    def enrich_segment(segment: SegmentRecord) -> SegmentRecord:
        """
        Calculates sentiment for the segment.text and updates the sentiment_intensity field.
        Returns the updated SegmentRecord.
        """
        text = segment.text.strip()
        if not text:
            return segment
            
        try:
            # Calculate overall sentiment
            s = SnowNLP(text)
            sent_score = s.sentiments
            
            # Sentence-by-Sentence Sentiment (逐句情感打分)
            # Custom sentence splitter: clean \n layout wraps first
            clean_text = text.replace('\n', '')
            parts = re.split(r'([。！？!?]+)', clean_text)
            sentences = []
            current_sentence = ""
            for part in parts:
                current_sentence += part
                if re.match(r'^[。！？!?]+$', part) or part == parts[-1]:
                    s = current_sentence.strip()
                    if s:
                        sentences.append(s)
                    current_sentence = ""
            
            sentence_sentiments = []
            if len(sentences) > 0:
                for sentence in sentences:
                    try:
                        # 独立评估每一个完整语义句子的情感
                        sentence_score = SnowNLP(sentence).sentiments
                        sentence_sentiments.append({
                            "sentence": sentence,
                            "positivity": round(sentence_score, 3)
                        })
                    except Exception:
                        pass
            
            # Convert overall probability into an "intensity" measure.
            intensity = abs(sent_score - 0.5) * 2.0
            
            # Keep precision manageable
            segment.sentiment_intensity = round(intensity, 3)
            segment.metadata['raw_positivity_score'] = round(sent_score, 3)
            segment.metadata['sentence_sentiments'] = sentence_sentiments
            
        except Exception as e:
            logging.debug(f"Failed to calculate sentiment for segment {segment.segment_id}: {e}")
            
        return segment
        
    @staticmethod
    def enrich_segments(segments: list[SegmentRecord]) -> list[SegmentRecord]:
        return [SentimentEnricher.enrich_segment(s) for s in segments]
