"""Backfill Vision — transcribe historical images and sync to NotebookLM.

Scans data/raw/maodaren and data/raw/9you for missing transcripts.
"""

import logging
import sys
from pathlib import Path
import yaml
import os
from dotenv import load_dotenv

# Ensure src is in path
sys.path.append(str(Path(__file__).parent.parent / "src"))

load_dotenv()

from finer.ingestion.vision_utils import VisionDescriptor, get_vision_transcript_path
from finer.ingestion.nlm_sync import NLMSync

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("backfill")

def load_config():
    config_path = Path(__file__).parent.parent / "configs" / "feishu.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_backfill(dry_run: bool = False):
    root = Path(__file__).parent.parent
    config = load_config()
    
    vision_cfg = config.get("vision", {})
    if not vision_cfg.get("enabled"):
        logger.error("Vision is disabled in config")
        return

    vision_desc = VisionDescriptor(model=vision_cfg.get("model", "qwen-vl-plus"))
    nlm_sync = NLMSync(config)
    
    # Target groups from config
    watched_chats = config.get("feishu", {}).get("watched_chats", [])
    
    total_processed = 0
    total_synced = 0
    
    for chat in watched_chats:
        creator_id = chat.get("default_creator")
        notebook_id = chat.get("notebook_id")
        chat_name = chat.get("name")
        
        if not creator_id or not notebook_id:
            continue
            
        logger.info(f"Processing group: {chat_name} (creator: {creator_id})")
        
        raw_dir = root / "data" / "raw" / creator_id
        if not raw_dir.exists():
            logger.warning(f"Raw directory not found: {raw_dir}")
            continue
            
        # Scan for images
        images = []
        for ext in (".png", ".jpg", ".jpeg"):
            images.extend(list(raw_dir.rglob(f"*{ext}")))
        
        logger.info(f"Found {len(images)} images for {creator_id}")
        
        for img_path in images:
            # Determine transcript path
            transcript_path = get_vision_transcript_path(root, img_path, creator_id)
            
            if transcript_path.exists():
                logger.debug(f"Skipping {img_path.name} (transcript already exists)")
                continue
            
            total_processed += 1
            if dry_run:
                logger.info(f"[DRY-RUN] Would process: {img_path.name}")
                continue
            
            # 1. Vision Analysis
            logger.info(f"Analyzing: {img_path.name}")
            try:
                description = vision_desc.describe_image(img_path)
                transcript_path.write_text(
                    f"# Vision Analysis: {img_path.name}\n\n"
                    f"**Source**: Historical Archive ({chat_name})\n"
                    f"**Creator**: {creator_id}\n\n"
                    f"## Description\n\n{description}\n",
                    encoding="utf-8"
                )
                
                # 2. Upload to NLM
                logger.info(f"Syncing to NotebookLM ({notebook_id})...")
                sync_result = nlm_sync.sync_file(transcript_path, notebook_id)
                if sync_result.success:
                    total_synced += 1
                else:
                    logger.error(f"NLM sync failed for {img_path.name}: {sync_result.error}")
                    
            except Exception as e:
                logger.error(f"Failed to process {img_path.name}: {e}")

    logger.info(f"Backfill completed. Processed: {total_processed}, Synced: {total_synced}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Count files without processing")
    args = parser.parse_args()
    
    run_backfill(dry_run=args.dry_run)
