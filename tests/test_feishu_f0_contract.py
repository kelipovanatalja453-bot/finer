"""Focused tests for the F0-only Feishu transcript importer."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from finer.ingestion.feishu_f0_importer import (
    BEIJING_TZ,
    FeishuMessageSelection,
    _build_content_record,
    import_feishu_transcript,
    parse_feishu_export,
)
from finer.schemas.content import ContentRecord


def _write_transcript(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Chat History: test",
                "",
                "- **Chat ID**: oc_test",
                "",
                "---",
                "### [2026-03-12 15:36:00] ou_sender (text)",
                "Q:猫大 算电协同 今天会讲么",
                "A: 核心是绿电成本优势，涨多了该卖就卖就好。",
                "",
                "### [2026-03-12 16:43:00] ou_sender (text)",
                "Q:猫大，阿特斯是否还值得关注",
                "A:值得，15元以下都是还不错的入场机会。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_parse_export_preserves_real_feishu_create_time(tmp_path: Path) -> None:
    transcript = tmp_path / "chat.md"
    _write_transcript(transcript)

    messages = parse_feishu_export(transcript)

    assert len(messages) == 2
    assert messages[0].timestamp == datetime(2026, 3, 12, 15, 36, 0, tzinfo=BEIJING_TZ)
    assert messages[0].timestamp.hour != 9
    assert messages[0].sender_id == "ou_sender"
    assert messages[0].message_type == "text"
    assert messages[0].raw_slice.startswith("### [2026-03-12 15:36:00]")
    assert "绿电成本优势" in messages[0].body_text


def test_importer_writes_valid_content_record_with_timestamp_source(tmp_path: Path) -> None:
    transcript = tmp_path / "chat.md"
    _write_transcript(transcript)
    data_root = tmp_path / "data"
    collected_at = datetime(2026, 6, 2, 8, 0, 0, tzinfo=timezone.utc)

    result = import_feishu_transcript(
        source_path=transcript,
        selections=[
            FeishuMessageSelection(
                timestamp="2026-03-12 15:36:00",
                sender_id="ou_sender",
                message_type="text",
            )
        ],
        chat_id="oc_test",
        chat_name="Test Chat",
        data_root=data_root,
        collected_at=collected_at,
    )

    assert len(result.items) == 1
    item = result.items[0]
    record = ContentRecord.model_validate_json(item.record_path.read_text(encoding="utf-8"))

    assert record.source_platform == "feishu"
    assert record.source_type == "feishu_chat"
    assert record.file_type == "chat_log"
    assert record.creator_id == "maodaren"
    assert record.published_at == datetime(2026, 3, 12, 15, 36, 0, tzinfo=BEIJING_TZ)
    assert record.collected_at == collected_at
    assert record.metadata["timestamp_source"] == "feishu_create_time"
    assert record.metadata["external_source_id_kind"] == "derived_from_export"
    assert record.metadata["creator_mapping"]["canonical_creator_id"] == "kol_cat_lord_fire"
    assert record.metadata["source_export_sha256"] == result.source_export_sha256
    assert item.raw_slice_path.read_text(encoding="utf-8").startswith(
        "### [2026-03-12 15:36:00]"
    )

    slice_hash = hashlib.sha256(item.raw_slice_path.read_bytes()).hexdigest()
    assert slice_hash == record.metadata["raw_slice_sha256"]
    expected_dedupe = hashlib.sha256(
        record.external_source_id.encode("utf-8") + b"\0" + item.raw_slice_path.read_bytes()
    ).hexdigest()
    assert record.dedupe_fingerprint == expected_dedupe


def test_importer_requires_explicit_message_selections(tmp_path: Path) -> None:
    transcript = tmp_path / "chat.md"
    _write_transcript(transcript)

    with pytest.raises(ValueError, match="FeishuMessageSelection"):
        import_feishu_transcript(
            source_path=transcript,
            selections=[],
            chat_id="oc_test",
            chat_name="Test Chat",
            data_root=tmp_path / "data",
        )


def test_invalid_source_type_is_rejected_by_builder() -> None:
    with pytest.raises(ValueError, match="only emits feishu_chat"):
        _build_content_record(
            content_id="bad",
            source_type="chat_export",
            source_platform="feishu",
            creator_id="maodaren",
            creator_name="猫大人FIRE",
            published_at=datetime(2026, 3, 12, 15, 36, 0, tzinfo=BEIJING_TZ),
            collected_at=datetime(2026, 6, 2, 8, 0, 0, tzinfo=timezone.utc),
            title="bad",
            raw_path="data/raw/feishu/oc_test/messages/bad.md",
            external_source_id="msg_bad",
            dedupe_fingerprint="hash",
            metadata={},
        )


def test_importer_source_has_no_cross_stage_or_legacy_calls() -> None:
    source = Path("src/finer/ingestion/feishu_f0_importer.py").read_text(encoding="utf-8")
    forbidden = [
        "VisionDescriptor",
        "SummaryGenerator",
        "NLMSync",
        "finer.parsing",
        "finer.pipeline",
        "finer.extraction",
        "finer.policy",
        "finer.backtest",
        "subprocess",
        "lark-cli",
    ]

    for token in forbidden:
        assert token not in source
