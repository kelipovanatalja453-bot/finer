import sys
import os
from pathlib import Path
from datetime import datetime
import json
import logging
from dotenv import load_dotenv

load_dotenv()


# Ensure src/ is in PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent / "src"))

from finer.schemas.content import ContentRecord
from finer.schemas.segment import SegmentRecord
from finer.parsing.vision_extractor import VisionExtractor
from finer.parsing.audio_extractor import AudioExtractor
from finer.parsing.sentiment_enricher import SentimentEnricher
from finer.parsing.slang import SlangMapper
from finer.parsing.context_summarizer import ContextSummarizer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ExtractionPipeline:
    def __init__(self):
        self.vision_extractor = VisionExtractor()
        self.audio_extractor = AudioExtractor()
        self.slang_mapper = SlangMapper()
        self.context_summarizer = ContextSummarizer()

    def determine_content_type(self, filepath: Path) -> str:
        name = filepath.name.lower()
        if filepath.suffix in [".mp4", ".mp3", ".wav"]:
            return "livestream_audio"
        elif "周度策略" in name:
            return "weekly_strategy_image"
        elif "盘前" in name:
            return "daily_pre_image"
        elif "盘后" in name:
            return "daily_post_image"
        return "manual_upload"

    def process_file(self, file_path: Path, output_dir: Path):
        """
        Process a single file through the extraction and sentiment pipeline.
        """
        logging.info(f"--- Processing {file_path.name} ---")
        
        # 1. Create Base Record
        content_id = file_path.stem.replace(" ", "_")
        content_record = ContentRecord(
            content_id=content_id,
            creator_name="trader韭",
            source_platform="wechat_or_bilibili",
            content_type=self.determine_content_type(file_path),
            published_at=datetime.now(), # Temporary fallback, can be parsed from filename
            source_path=str(file_path),
        )

        segments = []
        if file_path.suffix.lower() in [".jpg", ".png", ".jpeg"]:
            segments = self.vision_extractor.extract_image(content_record)
        elif file_path.suffix.lower() in [".mp3", ".mp4", ".wav"]:
            segments = self.audio_extractor.extract_audio(content_record)
        else:
            logging.info(f"Skipping unsupported file extension: {file_path.suffix}")
            return
            
        if not segments:
            logging.warning(f"No segments extracted for {file_path.name}.")
            return
            
        # 2. Sequential Enrichment
        # A. Sentiment & Sentence-level splitting
        enriched_segments = SentimentEnricher.enrich_segments(segments)
        
        # B. Slang Tagging & Token Estimation
        for seg in enriched_segments:
            self.slang_mapper.tag_segment(seg)
            seg.estimated_tokens = ContextSummarizer.estimate_tokens(seg.text)
            
        # C. Contextual Hierarchy (Global & Local)
        # Global Summary
        content_record.overall_summary = self.context_summarizer.generate_overall_summary(enriched_segments)
        
        # Local Window Summaries
        self.context_summarizer.enrich_local_context(enriched_segments)
        
        # 3. Export to JSON
        output_file = output_dir / f"{content_id}.json"
        
        # We output a dictionary containing the parent ContentRecord + List of Segments
        export_data = {
            "content": content_record.model_dump(mode='json'),
            "segments": [seg.model_dump(mode='json') for seg in enriched_segments]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            
        logging.info(f"✅ Successfully wrote structured data to {output_file}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Extraction Pipeline")
    parser.add_argument("--input", type=str, required=True, help="Input directory or specific file")
    parser.add_argument("--output", type=str, default="data/processed/transcripts_json", help="Output JSON dir")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    pipeline = ExtractionPipeline()
    
    if input_path.is_file():
        pipeline.process_file(input_path, output_path)
    elif input_path.is_dir():
        for root, _, files in os.walk(input_path):
            for file in files:
                if file.startswith("."):
                    continue
                pipeline.process_file(Path(root) / file, output_path)
    else:
        logging.error("Input path does not exist.")
