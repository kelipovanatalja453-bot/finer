"""B1 Diagnostic Run — 2 raw items through F1→quality_gate→F3→F4→F5.

Stopgap script: constructs minimal ContentRecords for the 2 cat_lord pack items,
routes them through StandardizationRouter, then runs golden_path with
quality gate rejection as a valid diagnostic outcome (not a failure).

Usage:
    cd /Users/zhouhongyuan/Desktop/finer
    source .env && python scripts/b1_diagnostic_run.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("b1_diagnostic")

PACK_DIR = Path("data/packs/cat_lord/cat_lord_raw_20260531T142911Z/items")
TRACE_DIR = Path("data/b1_diagnostic_traces")
TRACE_DIR.mkdir(parents=True, exist_ok=True)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "value"):
        return obj.value
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)


def dump(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=_json_default)
    logger.info("Wrote %s", path)


# ── Item definitions ────────────────────────────────────────────────────────
ITEMS = [
    {
        "item_id": "cat_lord_strategy_2026_03_12",
        "raw_file": "cat_lord_strategy_2026_03_12.raw",
        "source_type": "chat_transcript",
        "source_platform": "feishu",
        "file_type": "chat_log",
        "creator_name": "猫大人FIRE",
        "published_at": "2026-03-12T00:00:00+08:00",
        "title": "猫大人投资策略分析 — 2026年3月12日",
        "expected_adapter": "feishu_chat",
    },
    {
        "item_id": "cat_lord_image_strategy_2026_04_26",
        "raw_file": "cat_lord_image_strategy_2026_04_26.raw",
        "source_type": "manual_upload",
        "source_platform": "feishu",
        "file_type": "text",
        "creator_name": "猫大人FIRE",
        "published_at": None,
        "title": "猫大人图片策略分析 — 2026年4月26日",
        "expected_adapter": "manual_text",
    },
]


def build_content_record(item: dict) -> "ContentRecord":
    from finer.schemas.content import ContentRecord

    raw_path = PACK_DIR / item["raw_file"]
    pub = None
    if item["published_at"]:
        pub = datetime.fromisoformat(item["published_at"])

    return ContentRecord(
        content_id=item["item_id"],
        source_type=item["source_type"],
        source_platform=item["source_platform"],
        creator_name=item["creator_name"],
        published_at=pub,
        title=item["title"],
        raw_path=str(raw_path),
        file_type=item["file_type"],
        metadata={"pack_kol_id": "cat_lord", "pipeline_kol_id": "kol_cat_lord_fire"},
    )


def create_md_symlink(raw_path: Path) -> Path:
    md_path = raw_path.with_suffix(".md")
    if md_path.exists() or md_path.is_symlink():
        md_path.unlink()
    md_path.symlink_to(raw_path.name)
    return md_path


def run_one(item: dict) -> dict:
    from finer.parsing.standardization_router import StandardizationRouter

    trace: dict[str, Any] = {
        "item_id": item["item_id"],
        "kol_id_mapping": {"pack": "cat_lord", "pipeline": "kol_cat_lord_fire"},
        "expected_adapter": item["expected_adapter"],
        "actual_function_chain": [],
        "stages": {},
    }

    # ── Construct ContentRecord ──────────────────────────────────────────
    record = build_content_record(item)
    trace["content_record"] = record.model_dump()

    # ── Create .md symlink (router checks suffix) ────────────────────────
    raw_path = PACK_DIR / item["raw_file"]
    md_path = create_md_symlink(raw_path)
    trace["actual_function_chain"].append(
        f"symlink {raw_path.name} → {md_path.name} (router needs .md suffix)"
    )

    # ── F1: Standardization ──────────────────────────────────────────────
    router = StandardizationRouter()
    try:
        envelope, report = router.route(record, md_path)
        actual_adapter = report["adapter"]
        trace["actual_function_chain"].append(
            f"StandardizationRouter.route() → adapter={actual_adapter}"
        )
        trace["stages"]["F1_standardization"] = {
            "adapter": actual_adapter,
            "report": dict(report),
            "block_count": len(envelope.blocks),
            "blocks_summary": [
                {
                    "block_id": b.block_id,
                    "block_type": b.block_type,
                    "text_len": len(b.text),
                    "text_preview": b.text[:120] + "..." if len(b.text) > 120 else b.text,
                    "quality": b.quality.model_dump() if hasattr(b.quality, "model_dump") else str(b.quality),
                }
                for b in envelope.blocks
            ],
        }
    except Exception as exc:
        trace["stages"]["F1_standardization"] = {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        trace["outcome"] = "F1_FAILED"
        return trace

    # ── Quality Gate (pre-F3) ────────────────────────────────────────────
    # BUG: evaluate_envelope_quality() passes BlockQuality to evaluate_quality_card()
    # which expects QualityCard (has overall_score). Work around by using envelope-level
    # QualityCard only + manual block inspection.
    from finer.services.quality_gate import evaluate_quality_card
    envelope_gate = evaluate_quality_card(envelope.quality_card)

    block_quality_summary = []
    for b in envelope.blocks:
        bq = b.quality
        avg = (bq.readability + bq.extraction_confidence + bq.structural_confidence
               + bq.completeness) / 4
        block_quality_summary.append({
            "block_id": b.block_id,
            "readability": bq.readability,
            "extraction_confidence": bq.extraction_confidence,
            "structural_confidence": bq.structural_confidence,
            "completeness": bq.completeness,
            "noise_score": bq.noise_score,
            "avg_score": round(avg, 3),
            "flags": bq.quality_flags,
        })

    trace["stages"]["quality_gate"] = {
        "envelope_level": {
            "status": envelope_gate.status,
            "score": envelope_gate.score,
            "reasons": envelope_gate.reasons,
            "recommended_next_step": envelope_gate.recommended_next_step,
            "metadata": envelope_gate.metadata,
        },
        "block_quality_summary": block_quality_summary,
        "bug_note": (
            "evaluate_envelope_quality() crashes because it passes BlockQuality "
            "to evaluate_quality_card() which expects QualityCard.overall_score. "
            "Used envelope-level QualityCard as workaround."
        ),
    }
    trace["actual_function_chain"].append(
        f"evaluate_quality_card(envelope.quality_card) → status={envelope_gate.status}, score={envelope_gate.score:.2f}"
    )

    # ── F3→F4→F5 directly (bypass broken golden_path quality gate) ──────
    gate_status = envelope_gate.status
    if gate_status == "reject":
        trace["outcome"] = "QUALITY_GATE_REJECT"
        trace["stages"]["golden_path"] = {
            "skipped": True,
            "reason": f"Quality gate rejected (score={envelope_gate.score:.2f}): {envelope_gate.reasons}",
        }
        trace["actual_function_chain"].append(
            "F3→F4→F5 SKIPPED — quality gate reject"
        )
        return trace

    if gate_status == "review":
        trace["stages"]["quality_gate"]["note"] = (
            "Status is 'review' — proceeding to F3 (only 'reject' stops)."
        )

    # Run F3→F4→F5 inline (same logic as golden_path but without the broken gate call)
    try:
        from finer.extraction.intent_extractor import LLMIntentExtractor
        from finer.extraction.canonical_action_builder import CanonicalActionBuilder
        from finer.extraction.timing_builder import build_execution_timing
        from finer.llm.router import ModelRouter
        from finer.llm.client import LLMClient
        from finer.prompts.registry import PromptRegistry
        from finer.policy.policy_mapper import PolicyMapper

        # BUG workaround: ModelRouter accesses client.model but LLMClient only has _model
        if not hasattr(LLMClient, "model"):
            LLMClient.model = property(lambda self: self._model)

        item_dir = TRACE_DIR / item["item_id"]

        # F3: Intent Extraction
        extractor = LLMIntentExtractor(
            router=ModelRouter(),
            prompt_registry=PromptRegistry(),
        )
        extraction_result = extractor.extract(envelope)

        evidence_spans = getattr(extraction_result, "evidence_spans", [])
        trace["stages"]["F3_intent_extraction"] = {
            "intent_count": len(extraction_result.intents),
            "processing_notes": extraction_result.processing_notes,
            "intents": [i.model_dump() for i in extraction_result.intents],
            "evidence_spans": [s.model_dump() for s in evidence_spans] if evidence_spans else [],
            "evidence_span_count": len(evidence_spans) if evidence_spans else 0,
        }
        trace["actual_function_chain"].append(
            f"LLMIntentExtractor.extract() → {len(extraction_result.intents)} intent(s)"
        )

        # Write F3 artifacts
        f3_dir = item_dir / "F3_intents"
        f3_dir.mkdir(parents=True, exist_ok=True)
        for intent in extraction_result.intents:
            dump(intent.model_dump(), f3_dir / f"{intent.intent_id}.json")

        if not extraction_result.intents:
            trace["outcome"] = "NO_INTENTS"
            trace["stages"]["golden_path"] = {
                "error": f"No intents: {extraction_result.processing_notes}",
            }
            return trace

        intents = extraction_result.intents

        # F4: Policy Mapping
        mapper = PolicyMapper()
        batch = mapper.map_batch(intents)

        trace["stages"]["F4_policy_mapping"] = {
            "mapped_count": len(batch.mapped_intents),
            "mappings": [m.model_dump() for m in batch.mappings],
        }
        trace["actual_function_chain"].append(
            f"PolicyMapper.map_batch() → {len(batch.mapped_intents)} mapped"
        )

        f4_dir = item_dir / "F4_policy_mapped"
        f4_dir.mkdir(parents=True, exist_ok=True)
        for pmr in batch.mappings:
            dump(pmr.model_dump(), f4_dir / f"{pmr.policy_id}.json")

        # F5: Canonical TradeAction
        builder = CanonicalActionBuilder()
        temporal_anchors = getattr(envelope, "temporal_anchors", None) or []
        pmi_by_intent = {pmi.intent_id: pmi for pmi in batch.mapped_intents}
        trade_actions = []

        for intent in intents:
            pmi = pmi_by_intent.get(intent.intent_id)
            if pmi is None:
                continue

            timing = build_execution_timing(
                envelope,
                temporal_anchors=temporal_anchors,
                market=intent.market or "CN",
                intent_id=intent.intent_id,
            )

            ta = builder.build(
                intent=intent,
                policy_mapped_intent=pmi,
                evidence_span_ids=list(intent.evidence_span_ids),
                execution_timing=timing,
            )
            trade_actions.append(ta)

        trace["stages"]["F5_trade_actions"] = {
            "action_count": len(trade_actions),
            "actions": [a.model_dump() for a in trade_actions],
        }
        trace["actual_function_chain"].append(
            f"CanonicalActionBuilder.build() → {len(trade_actions)} TradeAction(s)"
        )

        f5_dir = item_dir / "F5_executed"
        f5_dir.mkdir(parents=True, exist_ok=True)
        for ta in trade_actions:
            dump(ta.model_dump(), f5_dir / f"{ta.trade_action_id}.json")

        if trade_actions:
            trace["outcome"] = "GOLDEN_PATH_OK"
        else:
            trace["outcome"] = "NO_ACTIONABLE_ACTIONS"

    except ValueError as exc:
        exc_msg = str(exc)
        trace["outcome"] = "PIPELINE_VALUE_ERROR"
        trace["stages"]["golden_path"] = {"error": exc_msg}
        trace["actual_function_chain"].append(
            f"Pipeline raised ValueError: {exc_msg[:200]}"
        )

    except Exception as exc:
        trace["outcome"] = "PIPELINE_EXCEPTION"
        trace["stages"]["golden_path"] = {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        trace["actual_function_chain"].append(
            f"Pipeline raised {type(exc).__name__}: {str(exc)[:200]}"
        )

    return trace


def main() -> None:
    logger.info("=== B1 Diagnostic Run Start ===")
    logger.info("Pack KOL ID: cat_lord | Pipeline KOL ID: kol_cat_lord_fire")

    all_traces = []
    for item in ITEMS:
        logger.info("─── Processing %s ───", item["item_id"])
        trace = run_one(item)
        all_traces.append(trace)

        out_path = TRACE_DIR / f"{item['item_id']}_trace.json"
        dump(trace, out_path)

        logger.info(
            "Result: %s (adapter=%s)",
            trace["outcome"],
            trace["stages"].get("F1_standardization", {}).get("adapter", "N/A"),
        )

    # Summary
    dump(all_traces, TRACE_DIR / "all_traces.json")
    logger.info("=== B1 Diagnostic Run Complete ===")
    for t in all_traces:
        logger.info("  %s → %s", t["item_id"], t["outcome"])


if __name__ == "__main__":
    main()
