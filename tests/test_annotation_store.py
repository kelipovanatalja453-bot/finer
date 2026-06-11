"""AnnotationStore tests — GUI-backed quality gates and export contracts."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from finer.schemas.annotation import ANNOTATION_SCHEMA_VERSION
from finer.services.annotation_store import (
    DEFAULT_PAIR_SAMPLE_SEED,
    DEFAULT_PAIR_SAMPLE_SIZE,
    AnnotationStore,
    _content_hash,
    evidence_from_prompt,
)


PROMPT_TMPL = "从以下文本提取 TradeAction：\n\n## 原文\n{evidence}\n\n## 提取要求\n1. 准确识别..."
REVIEWER = "analyst_test"


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def good_gold(ticker: str = "0700.HK"):
    return {
        "ticker": ticker,
        "direction": "bullish",
        "action_chain": [{"action_type": "long", "target_price_low": 400.0, "target_price_high": 500.0}],
    }


def eval_ann(item_id: str, *, verdict: str = "gold", reviewer: str = REVIEWER):
    base = {
        "id": item_id,
        "reviewer_id": reviewer,
        "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
        "sample_verdict": verdict,
        "notes": None,
    }
    if verdict == "exclude":
        return {**base, "exclude_reason": "non_investment", "expected_abstain": False, "gold": None}
    return {**base, "expected_abstain": False, "gold": good_gold()}


def pair_ann(pair_id: str, verdict: str = "accept", **extra):
    return {
        "pair_id": pair_id,
        "reviewer_id": REVIEWER,
        "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
        "verdict": verdict,
        **extra,
    }


@pytest.fixture
def store(tmp_path: Path) -> AnnotationStore:
    dpo = tmp_path / "dpo"
    eval_rows = [
        {
            "id": f"psg_e{i:02d}",
            "evidence_text": f"腾讯 0700.HK 目标价 {400 + i} 元，可逢低建仓",
            "creator": "kol_a",
            "source_file": "data/raw/a.md",
            "timestamp": "2026-05-01",
            "signals": {"signal_score": 2},
        }
        for i in range(25)
    ]
    pair_rows = [
        {
            "prompt": PROMPT_TMPL.format(evidence=f"阿特斯 CSIQ {15 + i} 元以下可入场"),
            "chosen": json.dumps({"ticker": "CSIQ", "direction": "bullish", "action_chain": [{"action_type": "long"}]}),
            "rejected": json.dumps({"ticker": "CSIQ", "direction": "bullish", "action_chain": [{"action_type": "long", "target_price_low": 999}]}),
            "meta": {"passage_id": f"psg_p{i:02d}", "creator": "kol_a"},
        }
        for i in range(40)
    ]
    write_jsonl(dpo / "eval" / "passages.jsonl", eval_rows)
    write_jsonl(dpo / "pairs.jsonl", pair_rows)
    return AnnotationStore(dpo_dir=dpo)


def test_task_summaries_ready_with_quality(store: AnnotationStore):
    summaries = {s.task_id: s for s in store.task_summaries()}
    assert summaries["eval_gold"].ready and summaries["eval_gold"].total == 25
    assert summaries["eval_gold"].quality.incomplete_items == 25
    assert summaries["pairs_review"].quality.pair_sample_size == DEFAULT_PAIR_SAMPLE_SIZE


def test_task_summaries_missing_source(tmp_path: Path):
    empty = AnnotationStore(dpo_dir=tmp_path / "nope")
    summaries = {s.task_id: s for s in empty.task_summaries()}
    assert not summaries["eval_gold"].ready
    assert "页面" in summaries["eval_gold"].fix_hint


def test_eval_submit_list_and_exclude(store: AnnotationStore):
    progress = store.submit("eval_gold", eval_ann("psg_e00"))
    assert progress["annotated"] == 1
    store.submit("eval_gold", eval_ann("psg_e01", verdict="exclude"))

    pending = store.list_items("eval_gold", status="pending")
    excluded = store.list_items("eval_gold", status="excluded")
    assert len(pending) == 23
    assert excluded[0]["id"] == "psg_e01"


def test_submit_requires_reviewer_and_schema_version(store: AnnotationStore):
    with pytest.raises(ValidationError):
        store.submit(
            "eval_gold",
            {"id": "psg_e00", "sample_verdict": "gold", "expected_abstain": False, "gold": good_gold()},
        )


def test_eval_formal_export_requires_complete_and_min_gold(store: AnnotationStore):
    store.submit("eval_gold", eval_ann("psg_e00"))
    with pytest.raises(ValueError, match="formal export"):
        store.export("eval_gold", "formal")

    for i in range(20):
        store.submit("eval_gold", eval_ann(f"psg_e{i:02d}"))
    for i in range(20, 25):
        store.submit("eval_gold", eval_ann(f"psg_e{i:02d}", verdict="exclude"))

    result = store.export("eval_gold", "formal")
    assert result["exported"] == 20
    assert result["excluded"] == 5
    rows = [json.loads(line) for line in store.eval_export.read_text(encoding="utf-8").splitlines()]
    assert all("prompt" not in row for row in rows)
    assert rows[0]["meta"]["reviewer_id"] == REVIEWER


def test_eval_formal_blocks_bad_lines_and_legacy_reviewer(store: AnnotationStore):
    with store.eval_annotations.open("a", encoding="utf-8") as fh:
        fh.write("{bad json\n")
        fh.write(json.dumps({"id": "psg_e00", "expected_abstain": False, "gold": good_gold()}, ensure_ascii=False) + "\n")

    summary = store.task_summary("eval_gold")
    assert summary.quality.bad_annotation_lines == 1
    assert summary.quality.legacy_missing_reviewer == 1
    assert any("旧标注" in reason for reason in summary.quality.formal_blocking_reasons)


def test_eval_formal_blocks_train_eval_overlap(store: AnnotationStore):
    with store.eval_source.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "id": "psg_p00",
            "evidence_text": "阿特斯 CSIQ 15 元以下可入场",
            "signals": {"signal_score": 2},
        }, ensure_ascii=False) + "\n")
    store.submit("eval_gold", eval_ann("psg_p00", reviewer=REVIEWER))
    assert "psg_p00" in store.task_summary("eval_gold").quality.train_eval_overlap_ids


def test_pairs_edit_requires_valid_extraction(store: AnnotationStore):
    with pytest.raises(ValidationError):
        store.submit(
            "pairs_review",
            pair_ann("psg_p00", "edit", edited_chosen=json.dumps({"ticker": "CSIQ", "direction": "bad"})),
        )


def test_pairs_formal_export_requires_seeded_sample_complete(store: AnnotationStore):
    with pytest.raises(ValueError, match="默认抽样队列"):
        store.export("pairs_review", "formal")

    sampled = store.list_items(
        "pairs_review",
        sample_size=DEFAULT_PAIR_SAMPLE_SIZE,
        seed=DEFAULT_PAIR_SAMPLE_SEED,
    )
    for item in sampled:
        store.submit("pairs_review", pair_ann(item["pair_id"]))

    result = store.export("pairs_review", "formal")
    assert result["accept"] == DEFAULT_PAIR_SAMPLE_SIZE
    assert result["unreviewed"] == 40 - DEFAULT_PAIR_SAMPLE_SIZE
    assert result["exported"] == 40


def test_pairs_hq_mode_requires_full_review(tmp_path: Path):
    dpo = tmp_path / "dpo" / "hq_v1"
    pair_rows = [
        {
            "prompt": PROMPT_TMPL.format(evidence=f"阿特斯 CSIQ {15 + i} 元以下可入场"),
            "chosen": json.dumps({
                "ticker": "CSIQ",
                "direction": "bullish",
                "conviction": 0.8,
                "action_chain": [{"action_type": "long"}],
                "time_horizon": "medium_term",
                "rationale": "原文明确给出 CSIQ 入场条件",
            }),
            "rejected": json.dumps({
                "ticker": "CSIQ",
                "direction": "bullish",
                "action_chain": [{"action_type": "long", "target_price_low": 999}],
            }),
            "meta": {"passage_id": f"psg_hq{i:02d}", "creator": "kol_a"},
        }
        for i in range(3)
    ]
    write_jsonl(dpo / "pairs_draft.jsonl", pair_rows)
    store = AnnotationStore(
        dpo_dir=dpo,
        pairs_source_name="pairs_draft.jsonl",
        full_pair_review_required=True,
    )

    assert store.pairs_source.name == "pairs_draft.jsonl"
    with pytest.raises(ValueError, match="全量审核队列 0/3"):
        store.export("pairs_review", "formal")

    for item in store.list_items("pairs_review"):
        store.submit("pairs_review", pair_ann(item["pair_id"]))

    result = store.export("pairs_review", "formal")
    assert result["sample_size"] == 3
    assert result["unreviewed"] == 0
    assert result["exported"] == 3
    assert store.pairs_export.name == "pairs_cleaned.jsonl"


def test_rebuild_eval_source_writes_manifest_and_filters(tmp_path: Path):
    root = tmp_path / "project"
    dpo = root / "data" / "dpo"
    raw = root / "data" / "raw" / "custom"
    raw.mkdir(parents=True)
    good_a = "腾讯 0700.HK 目标价 400 元，可逢低建仓，近期业务恢复和利润改善都比较明确。"
    good_b = "阿特斯 CSIQ 15 元以下可入场，目标价 20 元，储能订单兑现后弹性会更大。"
    overlap = "英伟达 NVDA 跌破 800 美元要减仓，短期趋势转弱时需要先控制风险。"
    image = "先看图 [Image: img_x]"
    weak = "今天没什么特别的"
    (raw / "chat_history_20260610.md").write_text(
        "\n".join(
            [
                f"### [2026-06-10 10:00:00] u1 (text)\n{good_a}",
                f"### [2026-06-10 10:01:00] u1 (text)\n{good_b}",
                f"### [2026-06-10 10:02:00] u1 (text)\n{overlap}",
                f"### [2026-06-10 10:03:00] u1 (text)\n{image}",
                f"### [2026-06-10 10:04:00] u1 (text)\n{weak}",
            ]
        ),
        encoding="utf-8",
    )
    overlap_id = f"psg_{_content_hash(overlap)}"
    write_jsonl(
        dpo / "pairs.jsonl",
        [{
            "prompt": PROMPT_TMPL.format(evidence=overlap),
            "chosen": "{}",
            "rejected": "{\"bad\": true}",
            "meta": {"passage_id": overlap_id},
        }],
    )

    store = AnnotationStore(dpo_dir=dpo)
    result1 = store.rebuild_eval_source(src=str(root / "data"), limit=10, seed=7, min_signal=2)
    result2 = store.rebuild_eval_source(src=str(root / "data"), limit=10, seed=7, min_signal=2)
    rows = [json.loads(line) for line in store.eval_source.read_text(encoding="utf-8").splitlines()]

    assert result1["selected"] == result2["selected"] == 2
    assert [row["id"] for row in rows] == [row["id"] for row in rows if "[Image:" not in row["evidence_text"]]
    assert overlap_id not in {row["id"] for row in rows}
    assert all(row["signals"]["signal_score"] >= 2 for row in rows)
    assert store.eval_manifest.exists()


def test_evidence_from_prompt():
    assert evidence_from_prompt(PROMPT_TMPL.format(evidence="原文内容 ABC")) == "原文内容 ABC"
    assert evidence_from_prompt("没有标记的 prompt") == "没有标记的 prompt"


# ---------------------------------------------------------------------------
# v3: 版本策略 / context / alt_golds / drafts / 侧车
# ---------------------------------------------------------------------------

V2_VERSION = "2026-06-10.annotation.v2"


def test_v2_rows_readable_but_v2_submit_rejected(store: AnnotationStore):
    # 文件中的 v2 行：合法（不算 legacy / invalid），不阻断 formal
    v2_row = {**eval_ann("psg_e00"), "annotation_schema_version": V2_VERSION}
    with store.eval_annotations.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(v2_row, ensure_ascii=False) + "\n")
    quality = store.task_summary("eval_gold").quality
    assert quality.legacy_missing_reviewer == 0
    assert quality.invalid_annotations == 0

    # 新提交必须是当前版本
    with pytest.raises(ValueError, match="当前 schema 版本"):
        store.submit("eval_gold", {**eval_ann("psg_e01"), "annotation_schema_version": V2_VERSION})


def test_alt_golds_validation(store: AnnotationStore):
    ann = eval_ann("psg_e00")
    ann["alt_golds"] = [{"ticker": "2498.HK", "direction": "bullish", "action_chain": []}]
    store.submit("eval_gold", ann)

    # 与主 gold 重复的 alt ticker 拒绝
    dup = eval_ann("psg_e01")
    dup["alt_golds"] = [good_gold()]  # 同 0700.HK
    with pytest.raises(ValidationError, match="重复"):
        store.submit("eval_gold", dup)

    # exclude 不允许 alt_golds
    bad = eval_ann("psg_e02", verdict="exclude")
    bad["alt_golds"] = [{"ticker": "2498.HK", "direction": "bullish", "action_chain": []}]
    with pytest.raises(ValidationError, match="exclude"):
        store.submit("eval_gold", bad)


def test_export_merges_context_and_alt_golds(store: AnnotationStore):
    ann = eval_ann("psg_e00")
    ann["alt_golds"] = [{"ticker": "2498.HK", "direction": "bullish", "action_chain": []}]
    ann["context_blocks"] = [
        {"offset": -1, "timestamp": "2026-05-01", "content": "前一条消息：提到吉利"},
        {"offset": 1, "timestamp": "2026-05-01", "content": "后一条消息：补充速腾聚创"},
    ]
    store.submit("eval_gold", ann)
    result = store.export("eval_gold", "draft")
    assert result["exported"] == 1
    row = json.loads(store.eval_export.read_text(encoding="utf-8").splitlines()[0])
    assert row["evidence_text"].startswith("前一条消息：提到吉利\n")
    assert row["evidence_text"].endswith("\n后一条消息：补充速腾聚创")
    assert row["alt_golds"][0]["ticker"] == "2498.HK"
    assert row["meta"]["context_blocks_merged"] == 2


def test_context_blocks_offset_validation(store: AnnotationStore):
    ann = eval_ann("psg_e00")
    ann["context_blocks"] = [{"offset": 0, "content": "自己"}]
    with pytest.raises(ValidationError, match="offset=0"):
        store.submit("eval_gold", ann)
    ann["context_blocks"] = [
        {"offset": 1, "content": "a"},
        {"offset": 1, "content": "b"},
    ]
    with pytest.raises(ValidationError, match="offset 重复"):
        store.submit("eval_gold", ann)


@pytest.fixture
def context_store(tmp_path: Path) -> AnnotationStore:
    """eval source 指向真实 chat 文件的 store（context 定位用）。"""
    chat = tmp_path / "chat_history_20260611.md"
    blocks = [
        "第一条：大盘整体回顾，没有具体标的。",
        "第二条：腾讯 0700.HK 目标价 400 元，可逢低建仓。",
        "第三条：猫大说吉利和速腾都是长线配置，短期涨跌只是降成本机会。",
        "第四条：有人问阿特斯 CSIQ 怎么看。",
        "第五条：CSIQ 15 元以下可入场，目标 18-20 元。",
    ]
    chat.write_text(
        "\n".join(
            f"### [2026-06-11 10:0{i}:00] u1 (text)\n{content}"
            for i, content in enumerate(blocks)
        ),
        encoding="utf-8",
    )
    target = blocks[2]
    dpo = tmp_path / "dpo"
    write_jsonl(
        dpo / "eval" / "passages.jsonl",
        [{
            "id": f"psg_{_content_hash(target)}",
            "evidence_text": target,
            "creator": "maodaren",
            "source_file": str(chat),
            "timestamp": "2026-06-11 10:02:00",
            "signals": {"signal_score": 2},
        }],
    )
    write_jsonl(dpo / "pairs.jsonl", [])
    return AnnotationStore(dpo_dir=dpo)


def test_context_locates_neighbors(context_store: AnnotationStore):
    item_id = context_store._eval_source_rows()[0]["id"]
    result = context_store.context(item_id, before=2, after=2)
    assert result["block_index"] == 2
    assert result["total_blocks"] == 5
    offsets = [b["offset"] for b in result["blocks"]]
    assert offsets == [-2, -1, 0, 1, 2]
    self_block = next(b for b in result["blocks"] if b["position"] == "self")
    assert "吉利和速腾" in self_block["content"]
    assert result["blocks"][0]["content"].startswith("第一条")

    # 边界：before 超出文件头不报错
    result2 = context_store.context(item_id, before=10, after=1)
    assert [b["offset"] for b in result2["blocks"]] == [-2, -1, 0, 1]


def test_context_unknown_id_and_missing_file(context_store: AnnotationStore, tmp_path: Path):
    with pytest.raises(KeyError):
        context_store.context("psg_nonexistent")

    # 源文件被移走
    rows = context_store._eval_source_rows()
    rows[0]["source_file"] = str(tmp_path / "gone.md")
    write_jsonl(context_store.eval_source, rows)
    with pytest.raises(FileNotFoundError):
        context_store.context(rows[0]["id"])


def test_drafts_attached_to_items(store: AnnotationStore):
    draft_output = json.dumps({"ticker": "0700.HK", "direction": "bullish", "action_chain": []})
    write_jsonl(store.eval_drafts, [{"id": "psg_e00", "output": draft_output}])
    items = {item["id"]: item for item in store.list_items("eval_gold")}
    assert items["psg_e00"]["draft"] == draft_output
    assert items["psg_e01"]["draft"] is None


def test_registry_gap_and_kol_note(store: AnnotationStore, tmp_path: Path):
    result = store.append_registry_gap(
        alias="速腾聚创", suggested_ticker="2498.hk", market="hk",
        item_id="psg_e00", reviewer_id=REVIEWER,
    )
    assert result["total"] == 1
    row = json.loads(store.registry_gaps.read_text(encoding="utf-8").splitlines()[0])
    assert row["suggested_ticker"] == "2498.HK" and row["market"] == "HK"

    with pytest.raises(ValueError, match="alias"):
        store.append_registry_gap(alias="  ", reviewer_id=REVIEWER)

    notes_store = AnnotationStore(dpo_dir=store.dpo_dir, kol_notes_dir=tmp_path / "notes")
    note = notes_store.append_kol_note(
        creator="maodaren", category="style",
        text="非常左侧+短中长周期错配兑现逻辑的交易风格",
        source_item_id="psg_e00", source_file="data/raw/a.md", reviewer_id=REVIEWER,
    )
    assert note["total_for_creator"] == 1
    assert (tmp_path / "notes" / "maodaren.jsonl").exists()

    with pytest.raises(ValueError, match="category"):
        notes_store.append_kol_note(
            creator="maodaren", category="vibe", text="x", reviewer_id=REVIEWER,
        )
    # 路径安全：creator 含路径分隔符被清洗
    weird = notes_store.append_kol_note(
        creator="../evil", category="style", text="x", reviewer_id=REVIEWER,
    )
    assert ".." not in Path(weird["path"]).name
    assert (tmp_path / "notes" / "___evil.jsonl").exists()
