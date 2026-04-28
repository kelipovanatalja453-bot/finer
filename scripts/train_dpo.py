#!/usr/bin/env python3
"""DPO Training Script for TradeAction Extraction.

This script trains a model using Direct Preference Optimization (DPO)
on RLHF feedback data from the Finer system.

Usage:
    # Export dataset first
    python -m finer.ml.export_dpo --output_dir ./data/dpo

    # Then train
    python scripts/train_dpo.py --data_dir ./data/dpo --output_dir ./models/dpo_finetuned

Requirements:
    pip install transformers trl peft accelerate bitsandbytes torch

Environment:
    CUDA_VISIBLE_DEVICES=0 python scripts/train_dpo.py ...
"""

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
from trl import DPOTrainer, DPOConfig as TRLDPOConfig
from peft import LoraConfig, get_peft_model, TaskType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_dpo_dataset(data_dir: Path) -> List[Dict[str, Any]]:
    """Load DPO dataset from JSONL file.

    Expected format (each line):
    {
        "prompt": "The input prompt",
        "chosen": "The preferred response (JSON)",
        "rejected": "The rejected response (JSON)"
    }

    Args:
        data_dir: Directory containing train.jsonl

    Returns:
        List of dataset items
    """
    train_path = data_dir / "train.jsonl"
    if not train_path.exists():
        raise FileNotFoundError(f"Dataset not found: {train_path}")

    items = []
    with open(train_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                # Validate required fields
                if not all(k in item for k in ["prompt", "chosen", "rejected"]):
                    logger.warning(f"Line {i} missing required fields, skipping")
                    continue
                items.append(item)
            except json.JSONDecodeError as e:
                logger.warning(f"Line {i} invalid JSON: {e}, skipping")
                continue

    logger.info(f"Loaded {len(items)} training examples from {train_path}")
    return items


def setup_model_and_tokenizer(
    model_name: str,
    use_peft: bool = True,
    lora_r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
):
    """Load model and tokenizer with optional LoRA.

    Args:
        model_name: HuggingFace model name or path
        use_peft: Whether to use PEFT/LoRA
        lora_r: LoRA rank
        lora_alpha: LoRA alpha
        lora_dropout: LoRA dropout

    Returns:
        (model, tokenizer)
    """
    logger.info(f"Loading model: {model_name}")

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )

    # Apply LoRA if requested
    if use_peft:
        logger.info(f"Applying LoRA: r={lora_r}, alpha={lora_alpha}")
        lora_config = LoraConfig(
            r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

    return model, tokenizer


def train_dpo(
    data_dir: Path,
    output_dir: Path,
    model_name: str = "Qwen/Qwen2.5-14B-Instruct",
    beta: float = 0.01,
    learning_rate: float = 5e-7,
    num_epochs: int = 1,
    batch_size: int = 4,
    gradient_accumulation_steps: int = 4,
    use_peft: bool = True,
    lora_r: int = 16,
    lora_alpha: int = 32,
    warmup_ratio: float = 0.1,
    max_grad_norm: float = 1.0,
    save_steps: int = 100,
    logging_steps: int = 10,
):
    """Run DPO training.

    Args:
        data_dir: Directory containing train.jsonl
        output_dir: Output directory for model
        model_name: Base model name
        beta: DPO beta (KL penalty)
        learning_rate: Learning rate
        num_epochs: Number of training epochs
        batch_size: Per-device batch size
        gradient_accumulation_steps: Gradient accumulation steps
        use_peft: Use LoRA for efficient training
        lora_r: LoRA rank
        lora_alpha: LoRA alpha
        warmup_ratio: Warmup ratio
        max_grad_norm: Max gradient norm for clipping
        save_steps: Save checkpoint every N steps
        logging_steps: Log every N steps
    """
    # Load dataset
    dataset = load_dpo_dataset(data_dir)

    if not dataset:
        raise ValueError("No training data found. Please check data_dir.")

    # Setup model
    model, tokenizer = setup_model_and_tokenizer(
        model_name=model_name,
        use_peft=use_peft,
        lora_r=lora_r,
        lora_alpha=lora_alpha,
    )

    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # DPO configuration
    dpo_config = TRLDPOConfig(
        output_dir=str(output_dir),
        beta=beta,
        learning_rate=learning_rate,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        warmup_ratio=warmup_ratio,
        max_grad_norm=max_grad_norm,
        bf16=True,
        logging_steps=logging_steps,
        save_steps=save_steps,
        save_total_limit=3,
        remove_unused_columns=False,
    )

    logger.info(f"DPO Config: beta={beta}, lr={learning_rate}, epochs={num_epochs}")

    # Create trainer
    trainer = DPOTrainer(
        model=model,
        ref_model=None,  # Will use the same model as reference
        args=dpo_config,
        train_dataset=dataset,
        tokenizer=tokenizer,
    )

    # Train
    logger.info("Starting DPO training...")
    trainer.train()

    # Save final model
    trainer.save_model(str(output_dir / "final"))
    tokenizer.save_pretrained(str(output_dir / "final"))

    logger.info(f"Training complete. Model saved to {output_dir / 'final'}")

    # Save training config
    config = {
        "model_name": model_name,
        "beta": beta,
        "learning_rate": learning_rate,
        "num_epochs": num_epochs,
        "batch_size": batch_size,
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "use_peft": use_peft,
        "lora_r": lora_r,
        "lora_alpha": lora_alpha,
        "dataset_size": len(dataset),
    }
    config_path = output_dir / "training_config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    logger.info(f"Training config saved to {config_path}")


def main():
    parser = argparse.ArgumentParser(
        description="DPO Training for TradeAction Extraction",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Required arguments
    parser.add_argument(
        "--data_dir",
        type=str,
        required=True,
        help="Directory containing train.jsonl",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        required=True,
        help="Output directory for trained model",
    )

    # Model arguments
    parser.add_argument(
        "--model_name",
        type=str,
        default="Qwen/Qwen2.5-14B-Instruct",
        help="Base model name or path",
    )

    # DPO hyperparameters
    parser.add_argument("--beta", type=float, default=0.01, help="DPO beta (KL penalty)")
    parser.add_argument("--lr", type=float, default=5e-7, help="Learning rate")
    parser.add_argument("--epochs", type=int, default=1, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=4, help="Per-device batch size")
    parser.add_argument(
        "--gradient_accumulation_steps",
        type=int,
        default=4,
        help="Gradient accumulation steps",
    )

    # LoRA arguments
    parser.add_argument("--use_peft", action="store_true", default=True, help="Use LoRA")
    parser.add_argument("--no_peft", action="store_false", dest="use_peft")
    parser.add_argument("--lora_r", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora_alpha", type=int, default=32, help="LoRA alpha")

    # Training arguments
    parser.add_argument("--warmup_ratio", type=float, default=0.1, help="Warmup ratio")
    parser.add_argument("--max_grad_norm", type=float, default=1.0, help="Max gradient norm")
    parser.add_argument("--save_steps", type=int, default=100, help="Save every N steps")
    parser.add_argument("--logging_steps", type=int, default=10, help="Log every N steps")

    args = parser.parse_args()

    # Run training
    train_dpo(
        data_dir=Path(args.data_dir),
        output_dir=Path(args.output_dir),
        model_name=args.model_name,
        beta=args.beta,
        learning_rate=args.lr,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        use_peft=args.use_peft,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        warmup_ratio=args.warmup_ratio,
        max_grad_norm=args.max_grad_norm,
        save_steps=args.save_steps,
        logging_steps=args.logging_steps,
    )


if __name__ == "__main__":
    main()
