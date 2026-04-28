#!/usr/bin/env python3
"""Export DPO dataset from RLHF feedback data.

Usage:
    # Export full dataset
    python -m finer.ml.export_dpo --output_dir ./data/dpo

    # Export incremental (since date)
    python -m finer.ml.export_dpo --output_dir ./data/dpo_incremental --since 2026-04-01

    # Export with custom config
    python -m finer.ml.export_dpo --output_dir ./data/dpo --min_rating 4 --include_schema
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from finer.ml.dpo_trainer import DPOExporter, DPOConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Export DPO dataset from RLHF feedback",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Required
    parser.add_argument(
        "--output_dir",
        type=str,
        required=True,
        help="Output directory for dataset",
    )

    # Filtering
    parser.add_argument(
        "--min_rating",
        type=int,
        default=3,
        choices=[1, 2, 3, 4, 5],
        help="Minimum rating to include",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        nargs="+",
        help="Filter to specific tickers (space-separated)",
    )

    # Incremental
    parser.add_argument(
        "--since",
        type=str,
        help="Export only feedbacks after this date (ISO format: 2026-04-01)",
    )

    # Format options
    parser.add_argument(
        "--include_schema",
        action="store_true",
        help="Include JSON schema in prompts",
    )
    parser.add_argument(
        "--include_metadata",
        action="store_true",
        help="Include metadata in output (for debugging)",
    )

    # Validation
    parser.add_argument(
        "--skip_validation",
        action="store_true",
        help="Skip data validation (faster but may include invalid items)",
    )

    # Stats
    parser.add_argument(
        "--stats_only",
        action="store_true",
        help="Only print statistics, don't export",
    )

    args = parser.parse_args()

    # Setup
    output_dir = Path(args.output_dir)
    config = DPOConfig(min_rating=args.min_rating)
    exporter = DPOExporter(config=config)

    # Export
    if args.since:
        logger.info(f"Exporting incremental data since {args.since}")
        items = exporter.export_incremental(
            since=args.since,
            include_schema=args.include_schema,
            validate=not args.skip_validation,
        )
    else:
        logger.info(f"Exporting full dataset (min_rating={args.min_rating})")
        items = exporter.export_dataset(
            min_rating=args.min_rating,
            tickers=args.tickers,
            include_schema=args.include_schema,
            validate=not args.skip_validation,
        )

    # Compute stats
    stats = exporter.compute_stats(items)

    print(f"\n{'='*50}")
    print("DPO Dataset Statistics")
    print(f"{'='*50}")
    print(f"Total items:     {stats.total_items}")
    print(f"Unique tickers:  {stats.unique_tickers}")
    print(f"Average rating:  {stats.avg_rating:.2f}")
    print(f"\nRating distribution:")
    for rating, count in sorted(stats.rating_distribution.items()):
        print(f"  {rating} stars: {count}")

    if stats.tag_distribution:
        print(f"\nTop issue tags:")
        for tag, count in list(stats.tag_distribution.items())[:5]:
            print(f"  {tag}: {count}")

    if stats.date_range:
        print(f"\nDate range: {stats.date_range[0][:10]} to {stats.date_range[1][:10]}")

    # Stats only mode
    if args.stats_only:
        return

    # Save
    if not items:
        logger.warning("No items to export. Check your filters or collect more feedback.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Save in HuggingFace format
    paths = exporter.save_huggingface_format(items, output_dir)
    print(f"\n{'='*50}")
    print("Exported Files")
    print(f"{'='*50}")
    for name, path in paths.items():
        print(f"  {name}: {path}")

    # Also save with metadata if requested
    if args.include_metadata:
        metadata_path = output_dir / "train_with_metadata.jsonl"
        exporter.save_jsonl(items, metadata_path, include_metadata=True)
        print(f"  train_with_metadata: {metadata_path}")

    print(f"\nDataset ready for training:")
    print(f"  python scripts/train_dpo.py --data_dir {output_dir} --output_dir ./models/dpo_finetuned")


if __name__ == "__main__":
    main()
