from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal

class SegmentRecord(BaseModel):
    """
    Atomic chunk of text/information extracted from multi-modal sources.
    """
    model_config = ConfigDict(strict=False)

    segment_id: str = Field(..., description="Unique ID for this extracted segment")
    content_id: str = Field(..., description="ID referencing the parent ContentRecord")
    
    speaker: Optional[str] = Field(None, description="Speaker name (for audio extraction with diarization)")
    start_sec: Optional[float] = Field(None, description="Start time in seconds for audio segments")
    end_sec: Optional[float] = Field(None, description="End time in seconds for audio segments")
    
    page_index: Optional[int] = Field(None, description="Page number for PDF segments")
    block_index: Optional[int] = Field(None, description="Sequential layout block index for images/PDFs")
    
    text: str = Field(..., description="The raw transcribed or OCR'd text")
    
    source_modality: Literal["image_ocr", "audio_asr", "text_native"] = Field(
        ..., description="The method/modality used to extract this text"
    )
    
    sentiment_intensity: float = Field(
        0.0, 
        ge=0.0, le=1.0, 
        description="Sentiment intensity score inferred locally (0 = calm, 1 = extremly strong)"
    )
    
    estimated_tokens: Optional[int] = Field(None, description="Estimated token count for budget tracking")

    metadata: dict = Field(
        default_factory=dict, 
        description="Metadata including structural_context (prev/next summary) and slang_tags"
    )
