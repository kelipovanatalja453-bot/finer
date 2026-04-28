import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Ensure src/ is in PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent / "src"))

from finer.schemas.content import ContentRecord
from finer.schemas.segment import SegmentRecord
from finer.extraction.extractor import ActionExtractor
from finer.extraction.action_interpreter import ActionInterpreter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class EventExtractionWorkflow:
    def __init__(self, model_name: str = "qwen-max"):
        self.extractor = ActionExtractor(model=model_name)
        self.interpreter = ActionInterpreter()

    def process_json(self, input_file: Path, output_dir: Path):
        """
        Reads a processed JSON and extracts events from its segments.
        """
        logging.info(f"🚀 Starting event extraction for {input_file.name}...")
        
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        content = ContentRecord.model_validate(data["content"])
        segments = [SegmentRecord.model_validate(s) for s in data["segments"]]
        
        all_events = []
        
        # We only process segments that have meaningful sentiment or length 
        # to avoid wasting API quota on 'Hello' or 'Wait' segments.
        processed_count = 0
        for seg in segments:
            # Heuristic: skip very short segments without slang tags
            if len(seg.text) < 15 and not seg.metadata.get("slang_tags"):
                continue
            
            logging.info(f"Extracting context for segment {seg.segment_id}...")
            context = self.interpreter.prepare_segment_context(content, seg)
            guideline = self.interpreter.format_extraction_guideline()
            full_context = f"{context}\n\n{guideline}"
            
            events = self.extractor.extract_events(seg.text, context=full_context)
            if events:
                for ev in events:
                    # Enrich event with content association
                    ev.content_id = content.content_id
                    all_events.append(ev)
                processed_count += 1
            
            # For sandbox testing, we might want to limit the number of segments
            if processed_count >= 10: 
                logging.info("Reached sandbox limit of 10 extraction-heavy segments.")
                break
                
        # Save results
        output_file = output_dir / f"{content.content_id}_events.json"
        export_data = [ev.model_dump(mode='json') for ev in all_events]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            
        logging.info(f"✅ Extraction complete. {len(all_events)} events found. Saved to {output_file}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Event Extraction Workflow")
    parser.add_argument("--input", type=str, required=True, help="Path to a processed JSON file")
    parser.add_argument("--output", type=str, default="data/extracted/candidate_events", help="Output dir")
    parser.add_argument("--model", type=str, default="qwen-max", help="Model name")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    workflow = EventExtractionWorkflow(model_name=args.model)
    workflow.process_json(input_path, output_path)
